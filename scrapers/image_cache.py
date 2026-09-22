import os, json
try:
    from upstash_redis import Redis
    redis = Redis(url=os.environ.get("UPSTASH_REDIS_REST_URL",""), token=os.environ.get("UPSTASH_REDIS_REST_TOKEN","")) if os.environ.get("UPSTASH_REDIS_REST_URL") else None
except: redis = None

CACHE_KEY = "scraper:events"
TTL = 3600  # 1h

def get_cached():
    if not redis: return None
    try:
        v = redis.get(CACHE_KEY)
        return json.loads(v) if v else None
    except: return None

def set_cached(events: list[dict]):
    if not redis: return
    try: redis.set(CACHE_KEY, json.dumps(events), ex=TTL)
    except: pass
