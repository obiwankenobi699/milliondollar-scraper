import os, json
try:
    from upstash_redis import Redis
    redis = Redis(url=os.environ.get("UPSTASH_REDIS_REST_URL",""), token=os.environ.get("UPSTASH_REDIS_REST_TOKEN","")) if os.environ.get("UPSTASH_REDIS_REST_URL") else None
except: redis = None

CACHE_KEY = "scraper:events"
TTL = int(os.environ.get("SCRAPER_CACHE_TTL_SECONDS", "1800"))

def get_cached():
    if not redis: return None
    try:
        v = redis.get(CACHE_KEY)
        if not v:
            return None
        if isinstance(v, str):
            return json.loads(v)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            return v.get("events") if isinstance(v.get("events"), list) else None
        return None
    except Exception:
        return None

def set_cached(events: list[dict]):
    if not redis: return
    try: redis.set(CACHE_KEY, json.dumps(events), ex=TTL)
    except Exception: pass
