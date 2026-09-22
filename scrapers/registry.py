# Official & relevant sources only — each must be the organiser's own domain
SOURCES = [
    {
        "id": "hyrox",
        "name": "HYROX",
        "base_url": "https://hyrox.com",
        "parser": "scrapers.hyrox.parse",
        "enabled": True,
        "official": True,
    },
    {
        "id": "token2049",
        "name": "TOKEN2049",
        "base_url": "https://www.token2049.com",
        "parser": "scrapers.token2049.parse",
        "enabled": True,
        "official": True,
    },
]

def get_enabled():
    return [s for s in SOURCES if s["enabled"] and s["official"]]

def get_by_id(source_id: str):
    return next((s for s in SOURCES if s["id"] == source_id), None)
