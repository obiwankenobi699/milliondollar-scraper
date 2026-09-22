"""Shared event-image resolution for all source parsers.

Every parser calls into this module instead of hand-rolling image logic, so that
all returned ``image_path`` values are *validated* absolute URLs — never a guess
that 404s and renders as a broken-image icon in the admin dashboard.

Strategy order per event (first validated win):
  1. ``og_meta``     — Open Graph / Twitter Card / JSON-LD / microdata image fields
                       (via ``extruct``, with a hand-parsed meta-tag fallback).
  2. ``selector``     — source-specific CSS selector passed in by the calling parser.
  3. ``fallback_img`` — scan of all <img> tags, skipping chrome (logos, icons, …).
  4. ``none``         — nothing validated; caller must store ``image_path = None``.

This module only returns a URL or None — it never touches the database.
"""

import asyncio
import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

try:
    import extruct  # type: ignore
except ImportError:  # pragma: no cover - deploy installs it via requirements.txt
    extruct = None  # type: ignore

log = logging.getLogger("image_resolver")

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
VALIDATE_TIMEOUT = 8.0
MIN_IMAGE_BYTES = 3000  # filters 1x1 tracking pixels that slip past filename checks
MAX_VALIDATION_CONCURRENCY = 5

_sem = asyncio.Semaphore(MAX_VALIDATION_CONCURRENCY)

# Sources whose images are hotlink-protected beyond what a Referer header fixes.
# Events from these sources should later be routed through a re-hosting step
# (download once, re-upload to our own Cloudinary storage). Extension point only.
NEEDS_REHOST: set[str] = set()

_SKIP_SUBSTRINGS = ("logo", "icon", "sprite", "pixel", "avatar", "placeholder", "blank", "1x1")


def _is_skippable(src: str) -> bool:
    s = src.lower()
    if not s or s.startswith("data:"):
        return True
    if ".svg" in s:
        return True
    return any(token in s for token in _SKIP_SUBSTRINGS)


def _referer(page_url: str | None, image_url: str) -> str:
    if page_url:
        return page_url
    p = urlparse(image_url)
    return f"{p.scheme}://{p.netloc}/" if p.netloc else image_url


async def validate_image_url(
    raw_url: str | None,
    page_url: str | None,
    client: httpx.AsyncClient,
) -> str | None:
    """Return the absolute URL if it is a real, loadable raster image, else None.

    - Relative URLs are resolved against ``page_url``.
    - HEAD first (with UA + Referer for hotlink-protected hosts), ranged-GET
      fallback when HEAD is not allowed (405/501).
    - Accept only HTTP 200 (+206 for ranged GET), ``content-type: image/*``
      (excluding SVG), and ``content-length`` above ``MIN_IMAGE_BYTES`` when the
      server sends one. A missing length header is treated as inconclusive
      (keep), while a definitive failure (4xx, non-image type, tiny body) is None.
    - Network errors/timeouts are inconclusive → keep the original URL rather
      than wiping a possibly-good image on a flaky check.
    """
    if not raw_url:
        return None
    absolute = urljoin(page_url or "", raw_url.strip()) if page_url else raw_url.strip()
    if _is_skippable(absolute):
        return None
    headers = {"User-Agent": BROWSER_UA, "Referer": _referer(page_url, absolute)}

    async with _sem:
        try:
            resp = await client.head(absolute, headers=headers, timeout=VALIDATE_TIMEOUT, follow_redirects=True)
            if resp.status_code in (405, 501):
                # HEAD not allowed — ranged GET avoids downloading the whole file.
                async with client.stream(
                    "GET", absolute,
                    headers={**headers, "Range": "bytes=0-0"},
                    timeout=VALIDATE_TIMEOUT, follow_redirects=True,
                ) as stream:
                    return _verdict(absolute, stream.status_code, stream.headers, ranged=True)
            return _verdict(absolute, resp.status_code, resp.headers)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            return absolute  # inconclusive — don't wipe on a flaky check
        except Exception:
            log.debug("image validation error for %s", absolute, exc_info=True)
            return absolute


def _verdict(url: str, status: int, headers: httpx.Headers, ranged: bool = False) -> str | None:
    ctype = (headers.get("content-type") or "").lower()
    if status in (401, 403):
        log.warning("image %s rejected with %s — hotlink protection? consider NEEDS_REHOST", url, status)
        return None
    if status == 404:
        return None
    if status not in (200, 206):
        # 5xx / unexpected: inconclusive, keep rather than wipe.
        return url if status >= 500 else None
    if not ctype.startswith("image/") or "svg" in ctype:
        return None
    length = headers.get("content-length")
    if length is not None and not headers.get("content-range"):
        try:
            if int(length) < MIN_IMAGE_BYTES:
                return None
        except ValueError:
            pass
    _ = ranged
    return url


def _meta_candidates(soup: BeautifulSoup, raw_html: str | None) -> list[str]:
    """og_meta strategy: extruct first (OG + Twitter + JSON-LD + microdata)."""
    found: list[str] = []

    def _add(value: object) -> None:
        vals = value if isinstance(value, list) else [value]
        for v in vals:
            if isinstance(v, str) and v.strip() and v.strip() not in found:
                found.append(v.strip())

    if extruct is not None and raw_html:
        try:
            data = extruct.extract(raw_html, syntaxes=["opengraph", "json-ld", "microdata"])
            for item in data.get("opengraph", []) or []:
                props = item.get("properties", {}) if isinstance(item, dict) else {}
                for key in ("image:secure_url", "image"):
                    _add(props.get(key))
            for blob in (data.get("json-ld", []) or []) + (data.get("microdata", []) or []):
                _add(_deep_find_image(blob))
        except Exception:
            log.debug("extruct parse failed, falling back to meta tags", exc_info=True)
    # hand-parsed tags (covers twitter:image which extruct skips, plus no-extruct installs)
    for attr in (
        ("property", "og:image:secure_url"),
        ("property", "og:image"),
        ("name", "twitter:image"),
    ):
        tag = soup.find("meta", attrs={attr[0]: attr[1]})
        if tag:
            _add(tag.get("content", ""))
    return found


def _deep_find_image(node: object) -> str | None:
    if isinstance(node, dict):
        image = node.get("image")
        if isinstance(image, str) and image.strip():
            return image.strip()
        for value in node.values():
            found = _deep_find_image(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _deep_find_image(value)
            if found:
                return found
    return None


def _selector_candidates(soup: BeautifulSoup, selector: str) -> list[str]:
    out: list[str] = []
    for tag in soup.select(selector):
        img = tag if tag.name == "img" else tag.find("img")
        if img is None:
            continue
        for attr in ("src", "data-src", "data-lazy-src", "srcset"):
            val = (img.get(attr) or "").strip()
            if not val:
                continue
            if attr == "srcset":
                val = val.split(",")[0].strip().split(" ")[0]
            if val:
                out.append(val)
    return out


def _fallback_candidates(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src"):
            val = (img.get(attr) or "").strip()
            if val and not _is_skippable(val):
                out.append(val)
    # de-dupe, preserve order
    return list(dict.fromkeys(out))


async def resolve_event_image(
    soup_or_html: BeautifulSoup | str | None,
    page_url: str | None,
    source_selector: str | None = None,
    client: httpx.AsyncClient | None = None,
    source_name: str = "",
) -> str | None:
    """Resolve one validated image URL for an event page (or None).

    Tries og_meta → source selector → fallback <img> scan, validating every
    candidate with :func:`validate_image_url` and stopping at the first success.
    Logs which strategy won as ``og_meta / selector / fallback_img / none``.
    """
    if soup_or_html is None:
        log.info("image resolve [%s] %s -> none (no page parsed)", source_name, page_url)
        return None
    soup = soup_or_html if isinstance(soup_or_html, BeautifulSoup) else BeautifulSoup(soup_or_html, "lxml")
    raw_html = soup_or_html if isinstance(soup_or_html, str) else None

    strategies: list[tuple[str, list[str]]] = [("og_meta", _meta_candidates(soup, raw_html))]
    if source_selector:
        strategies.append(("selector", _selector_candidates(soup, source_selector)))
    strategies.append(("fallback_img", _fallback_candidates(soup)))

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": BROWSER_UA})
    try:
        for name, candidates in strategies:
            for candidate in candidates:
                resolved = await validate_image_url(candidate, page_url, client)
                if resolved:
                    log.info("image resolve [%s] %s -> %s (%s)", source_name, page_url, resolved, name)
                    return resolved
    finally:
        if own_client:
            await client.aclose()
    log.info("image resolve [%s] %s -> none", source_name, page_url)
    return None


async def finalize_event_images(
    events: list,
    soup: BeautifulSoup | None = None,
    page_url: str | None = None,
    source_selector: str | None = None,
    client: httpx.AsyncClient | None = None,
    source_name: str = "",
    page_fallback: bool = True,
) -> list:
    """Validate every event's ``image_path``; fill gaps via page-level resolve.

    - Keeps an existing ``image_path`` only if it validates.
    - Otherwise sets it to None, or — when ``page_fallback`` and a soup was
      passed — to the page-level resolved image (e.g. a source homepage hero).
    - Pass ``page_fallback=False`` for listing pages whose images are mapped
      per-event (a generic page image on every card looks worse than none).
    """
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": BROWSER_UA})
    try:
        page_image: str | None = None
        page_tried = False
        for ev in events:
            if ev.image_path and await validate_image_url(ev.image_path, page_url, client):
                continue
            ev.image_path = None
            if page_fallback and soup is not None:
                if not page_tried:
                    page_tried = True
                    page_image = await resolve_event_image(soup, page_url, source_selector, client, source_name)
                ev.image_path = page_image
    finally:
        if own_client:
            await client.aclose()
    return events
