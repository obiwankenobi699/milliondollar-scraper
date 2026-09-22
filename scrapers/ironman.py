import httpx
from .base import NormalizedEvent

MOCK = [
    NormalizedEvent(
        slug="ironman-703-goa",
        name="IRONMAN 70.3 Goa",
        category="Race",
        city="Goa",
        country="India",
        starts_at="2026-11-08",
        ends_at="2026-11-08",
        description="India's premier IRONMAN 70.3 on the Goan coastline — swim, bike, run with global athletes.",
        image_path="https://www.ironman.com/sites/default/files/styles/hero/public/ironman-goa-hero.jpg",
    ),
    NormalizedEvent(
        slug="ironman-world-championship-kona",
        name="IRONMAN World Championship Kona",
        category="Race",
        city="Kailua-Kona",
        country="United States",
        starts_at="2026-10-10",
        ends_at="2026-10-10",
        description="The ultimate IRONMAN World Championship on the Big Island of Hawaii.",
        image_path="https://www.ironman.com/sites/default/files/styles/hero/public/kona-hero.jpg",
    ),
]

async def parse(client: httpx.AsyncClient | None = None) -> list[NormalizedEvent]:
    # Official https://www.ironman.com/races — image scraping would parse <img> on race pages
    # For now return curated official events with absolute hero images for cards
    if client:
        try:
            resp = await client.get("https://www.ironman.com/races", timeout=10)
            if resp.status_code == 200:
                # best-effort image scrape could go here; keeping mock enriched
                pass
        except: pass
    return MOCK
