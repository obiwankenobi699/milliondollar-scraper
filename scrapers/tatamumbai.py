import httpx
from .base import NormalizedEvent

MOCK = [
    NormalizedEvent(
        slug="tata-mumbai-marathon",
        name="Tata Mumbai Marathon",
        category="Race",
        city="Mumbai",
        country="India",
        starts_at="2026-01-18",
        ends_at="2026-01-18",
        description="Asia's premier marathon — World Athletics Gold Label race through Mumbai's iconic streets.",
        image_path="https://tatamumbaimarathon.procam.in/images/hero-tmm.jpg",
    ),
    NormalizedEvent(
        slug="tcs-world-10k-bengaluru",
        name="TCS World 10K Bengaluru",
        category="Race",
        city="Bengaluru",
        country="India",
        starts_at="2026-04-26",
        ends_at="2026-04-26",
        description="Bengaluru's iconic 10K — elite and amateur runners on the city's racing circuit.",
        image_path="https://tcsworld10k.procam.in/images/hero-10k.jpg",
    ),
    NormalizedEvent(
        slug="airtel-delhi-half-marathon",
        name="Airtel Delhi Half Marathon",
        category="Race",
        city="New Delhi",
        country="India",
        starts_at="2026-10-26",
        ends_at="2026-10-26",
        description="Delhi's half marathon — a fast, flat course attracting global elite fields.",
        image_path="https://adhm.procam.in/images/hero-adhm.jpg",
    ),
]

async def parse(client: httpx.AsyncClient | None = None) -> list[NormalizedEvent]:
    if client:
        try:
            resp = await client.get("https://tatamumbaimarathon.procam.in", timeout=10)
            # image scraping would extract hero <img> here
        except: pass
    return MOCK
