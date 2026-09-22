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
    # Official https://www.token2049.com — for now mock
    return MOCK
