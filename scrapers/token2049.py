import httpx
from .base import NormalizedEvent

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
        image_path="/events/token2049-singapore.avif",
    )
]

async def parse(client: httpx.AsyncClient | None = None) -> list[NormalizedEvent]:
    # Official https://www.token2049.com — for now mock
    return MOCK
