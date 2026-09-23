from dataclasses import dataclass, asdict
import os
import re
from datetime import date

@dataclass
class NormalizedEvent:
    slug: str
    name: str
    category: str
    city: str
    country: str
    starts_at: str | None  # YYYY-MM-DD
    ends_at: str | None
    description: str | None
    image_path: str | None
    source_type: str = "scraper"
    status: str = "pending"

def slugify(name: str, city: str | None = None) -> str:
    base = f"{name} {city or ''}".lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")
    return base[:80]

def parse_date(s: str | None) -> str | None:
    if not s: return None
    # try YYYY-MM-DD or DD MMM YYYY
    s = s.strip()
    # already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # try parse with dateutil fallback? simple
    try:
        from datetime import datetime
        for fmt in ("%Y-%m-%d","%d %b %Y","%d %B %Y","%b %d, %Y","%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except: pass
    except: pass
    return None

def serialize(events: list[NormalizedEvent]) -> list[dict]:
    return [asdict(e) for e in events]

def allow_curated_fallbacks() -> bool:
    return os.environ.get("ALLOW_CURATED_FALLBACKS", "1") != "0"
