import httpx
from dataclasses import replace
from bs4 import BeautifulSoup
from .base import NormalizedEvent
from .image_resolver import finalize_event_images

MOCK = [
    NormalizedEvent(
        slug="token2049-singapore",
        name="TOKEN2049 Singapore",
        category="Tech",
        city="Singapore",
        country="Singapore",
        starts_at="2026-10-07",
        ends_at="2026-10-08",
        description="The world's largest crypto event takes over all five floors of Marina Bay Sands for two days.",
        image_path="https://www.token2049.com/images/singapore-hero.jpg",
    ),
    NormalizedEvent(
        slug="token2049-dubai",
        name="TOKEN2049 Dubai",
        category="Tech",
        city="Dubai",
        country="United Arab Emirates",
        starts_at="2026-04-30",
        ends_at="2026-05-01",
        description="TOKEN2049 Dubai brings together the global crypto community at Madinat Jumeirah.",
        image_path="https://www.token2049.com/images/dubai-hero.jpg",
    ),
]

async def parse(client: httpx.AsyncClient | None = None) -> list[NormalizedEvent]:
    # Official https://www.token2049.com — curated events; every image_path is
    # validated (failures become None, never a broken link).
    page_url = "https://www.token2049.com"
    soup = None
    _client = client or httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": "WearbidsScraper/1.0"})
    try:
        try:
            resp = await _client.get(page_url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
        except: pass
        return await finalize_event_images([replace(ev) for ev in MOCK], soup, page_url, client=_client, source_name="token2049")
    finally:
        if client is None:
            await _client.aclose()
