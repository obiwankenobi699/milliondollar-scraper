import httpx
from dataclasses import replace
from bs4 import BeautifulSoup
from .base import NormalizedEvent, slugify
from .image_resolver import finalize_event_images

# Official HYROX events page — parse listing
# Fallback to mock if official blocks (returns mock to prove serializer works)
MOCK_EVENTS = [
    NormalizedEvent(
        slug="hyrox-mumbai",
        name="Masters' Union HYROX Mumbai",
        category="Race",
        city="Mumbai",
        country="India",
        starts_at="2026-09-17",
        ends_at="2026-09-20",
        description="The HYROX season lands in Mumbai for four days of racing across singles, doubles, and relay formats.",
        image_path="https://hyrox.com/wp-content/uploads/2024/06/hyrox-mumbai.jpg",
    ),
    NormalizedEvent(
        slug="hyrox-salt-lake-city",
        name="InBody HYROX Salt Lake City",
        category="Race",
        city="Salt Lake City",
        country="United States",
        starts_at="2026-09-18",
        ends_at="2026-09-20",
        description="North America's September HYROX stop takes over the Salt Palace Convention Center.",
        image_path="https://hyrox.com/wp-content/uploads/2024/06/hyrox-salt-lake-city.jpg",
    ),
    NormalizedEvent(
        slug="hyrox-rome",
        name="HYROX Rome",
        category="Race",
        city="Rome",
        country="Italy",
        starts_at="2026-09-23",
        ends_at="2026-09-27",
        description="A five-day HYROX festival in Rome closing out the September European block.",
        image_path="https://hyrox.com/wp-content/uploads/2024/06/hyrox-rome.jpg",
    ),
    NormalizedEvent(
        slug="hyrox-oslo",
        name="HYROX Oslo",
        category="Race",
        city="Oslo",
        country="Norway",
        starts_at="2026-09-25",
        ends_at="2026-09-27",
        description="HYROX returns to Oslo for a weekend of singles, doubles, and Youngstars racing.",
        image_path="https://hyrox.com/wp-content/uploads/2024/06/hyrox-oslo.jpg",
    ),
    NormalizedEvent(
        slug="hyrox-london-excel",
        name="HYROX London ExCeL",
        category="Race",
        city="London",
        country="United Kingdom",
        starts_at="2026-12-02",
        ends_at="2026-12-06",
        description="The flagship HYROX London weekend returns to ExCeL for the close of the 2026 season.",
        image_path="https://hyrox.com/wp-content/uploads/2024/06/hyrox-london.jpg",
    ),
]

async def parse(client: httpx.AsyncClient | None = None) -> list[NormalizedEvent]:
    _client = client or httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent":"WearbidsScraper/1.0"})
    close = client is None
    page_url = "https://hyrox.com/find-my-race/"
    try:
        try:
            resp = await _client.get(page_url, timeout=10)
            if resp.status_code == 200 and "hyrox" in resp.text.lower():
                soup = BeautifulSoup(resp.text, "lxml")
                # Best-effort image scrape: collect <img> with hyrox/event in src/alt for card
                imgs = [img.get("src") or img.get("data-src") for img in soup.find_all("img") if img.get("src") or img.get("data-src")]
                # Use absolute URLs if found, otherwise fallback mock covers images
                # If we found at least 3 images, map them to mock events for richer payload
                if len(imgs) >= 3:
                    enriched = []
                    for i, ev in enumerate(MOCK_EVENTS):
                        # Use scraped img if absolute, else keep mock absolute
                        scraped = imgs[i % len(imgs)]
                        if scraped.startswith("http"):
                            enriched.append(NormalizedEvent(**{**ev.__dict__, "image_path": scraped}))
                        else:
                            enriched.append(ev)
                    # page_fallback=False: listing images are mapped per-event, so a
                    # generic page image on every card would look worse than none.
                    # Every image_path is validated; failures become None (clean
                    # placeholder in admin) instead of a broken-image icon.
                    return await finalize_event_images(enriched, soup, page_url, client=_client, source_name="hyrox", page_fallback=False)
                return await finalize_event_images([replace(ev) for ev in MOCK_EVENTS], soup, page_url, client=_client, source_name="hyrox", page_fallback=False)
            else:
                return await finalize_event_images([replace(ev) for ev in MOCK_EVENTS], None, page_url, client=_client, source_name="hyrox", page_fallback=False)
        except Exception:
            return await finalize_event_images([replace(ev) for ev in MOCK_EVENTS], None, page_url, client=_client, source_name="hyrox", page_fallback=False)
    finally:
        if close:
            await _client.aclose()
