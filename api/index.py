import os, hmac, importlib, asyncio
from datetime import datetime, timedelta
import httpx
from fastapi import FastAPI, Request, Header, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
try:
    from scrapers.image_cache import get_cached, set_cached
except: 
    def get_cached(): return None
    def set_cached(e): pass

ADMIN_HASH = os.environ.get("ADMIN_ACCESS_HASH", "").strip()
SCRAPER_SECRET = os.environ.get("SCRAPER_SECRET", "").strip()
JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
JWT_ALGO = "HS256"
IS_PROD = bool(os.environ.get("VERCEL") or os.environ.get("PRODUCTION"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1" if IS_PROD else "0") == "1"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", os.environ.get("APP_ORIGIN", "")).split(",")
    if origin.strip()
]

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="milliondollar-scraper")
app.state.limiter = limiter

# in-memory last run
LAST_RUN: dict = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS or [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

def require_auth_config():
    missing = [name for name, value in (
        ("ADMIN_ACCESS_HASH", ADMIN_HASH),
        ("SCRAPER_SECRET", SCRAPER_SECRET),
        ("JWT_SECRET", JWT_SECRET),
    ) if not value]
    if missing:
        raise HTTPException(status_code=503, detail=f"missing auth config: {', '.join(missing)}")

def create_session_token():
    require_auth_config()
    exp = datetime.utcnow() + timedelta(hours=12)
    return jwt.encode({"sub":"admin","exp":exp}, JWT_SECRET, algorithm=JWT_ALGO)

def verify_session(request: Request) -> bool:
    if not JWT_SECRET:
        return False
    token = request.cookies.get("scraper_session")
    if not token: return False
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload.get("sub") == "admin"
    except: return False

def require_dashboard(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=401, detail="dashboard auth required")

def require_bearer_or_dashboard(request: Request, authorization: str | None = Header(default=None)):
    # allow either bearer or dashboard cookie
    expected = f"Bearer {SCRAPER_SECRET}"
    if authorization and SCRAPER_SECRET and hmac.compare_digest(authorization, expected):
        return True
    if verify_session(request):
        return True
    raise HTTPException(status_code=401, detail="unauthorized")

@app.get("/api/health")
async def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

@app.post("/api/login")
@limiter.limit("5/15 minutes")
async def login(request: Request):
    require_auth_config()
    body = await request.json()
    provided = str(body.get("hash","")).strip()
    # constant-time compare
    if not ADMIN_HASH or not hmac.compare_digest(provided, ADMIN_HASH):
        raise HTTPException(status_code=401, detail="invalid hash")
    token = create_session_token()
    resp = JSONResponse({"ok": True})
    resp.set_cookie("scraper_session", token, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=43200, path="/")
    return resp

@app.get("/api/sources")
async def list_sources(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=401, detail="unauthorized")
    from scrapers.registry import SOURCES
    # enrich with last_run
    out = []
    for s in SOURCES:
        out.append({**s, "last_run": LAST_RUN.get(s["id"])})
    return {"sources": out}

@app.get("/api/scrape")
async def scrape(
    request: Request,
    source: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    authorization: str | None = Header(default=None),
):
    # allow bearer or dashboard cookie
    require_bearer_or_dashboard(request, authorization)
    from scrapers.registry import get_enabled, get_by_id
    from scrapers.base import serialize

    targets = [get_by_id(source)] if source else get_enabled()
    targets = [s for s in targets if s]
    if source and not targets:
        raise HTTPException(status_code=404, detail="source not found")
    if any(not s["official"] for s in targets):
        raise HTTPException(status_code=400, detail="only official sources allowed")

    # Upstash cache for full scrape (no source filter). Admin-triggered POSTs can
    # pass refresh=1 to force fresh official data and avoid repeated stale output.
    if not source and not refresh:
        cached = get_cached()
        if cached:
            return {
                "events": cached,
                "errors": [],
                "meta": {
                    "ran": len(targets),
                    "succeeded": len(targets),
                    "total_events": len(cached),
                    "images": sum(1 for e in cached if e.get("image_path")),
                    "cached": True,
                },
            }

    events = []
    errors = []
    async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent":"WearbidsScraper/1.0"}) as client:
        async def run_source(src):
            try:
                mod_path, func_name = src["parser"].rsplit(".",1)
                mod = importlib.import_module(mod_path)
                func = getattr(mod, func_name)
                result = await func(client)
                LAST_RUN[src["id"]] = {"time": datetime.utcnow().isoformat(), "count": len(result), "error": None}
                return src, result, None
            except Exception as e:
                LAST_RUN[src["id"]] = {"time": datetime.utcnow().isoformat(), "count": 0, "error": str(e)}
                return src, [], e

        results = await asyncio.gather(*(run_source(src) for src in targets))
        for src, result, error in results:
            if error:
                errors.append({"source": src["id"], "error": str(error)})
            events.extend(result)

    # serialize to dicts — image_path now absolute scraped URL for card
    from scrapers.base import serialize
    serialized = serialize(events)
    if not source and not errors:
        set_cached(serialized)
    return {"events": serialized, "errors": errors, "meta": {"ran": len(targets), "succeeded": len(targets)-len(errors), "total_events": len(serialized), "images": sum(1 for e in serialized if e.get("image_path"))}}

# Dashboard HTML
LOGIN_HTML = """<!doctype html><html><head><meta charset=utf-8><title>Scraper Login</title><style>body{font-family:system-ui;padding:40px;max-width:480px;margin:auto}input{width:100%;padding:12px;margin:8px 0}button{padding:12px 20px;background:#000;color:#fff;border:0;cursor:pointer}</style></head><body><h1>Scraper Login</h1><p>Enter 10-digit hash</p><form id=f><input id=hash placeholder=hash><button>Login</button></form><p id=msg></p><script>document.getElementById('f').onsubmit=async e=>{e.preventDefault();const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hash:document.getElementById('hash').value})});const j=await r.json();if(r.ok)location.href='/dashboard';else document.getElementById('msg').textContent=j.detail||'failed'}</script></body></html>"""

DASHBOARD_HTML = """<!doctype html><html><head><meta charset=utf-8><title>Scraper Dashboard</title><style>body{font-family:system-ui;padding:24px;max-width:900px;margin:auto}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ddd;padding:8px;text-align:left}button{padding:6px 10px;cursor:pointer}pre{background:#f5f5f5;padding:12px;overflow:auto;max-height:400px}</style></head><body><h1>Sources</h1><table id=t><thead><tr><th>id</th><th>name</th><th>base_url</th><th>official</th><th>enabled</th><th>last run</th><th>action</th></tr></thead><tbody></tbody></table><h2>Result</h2><pre id=out>Run a source...</pre><script>async function load(){const r=await fetch('/api/sources');if(r.status==401){location.href='/login';return}const j=await r.json();const tb=document.querySelector('#t tbody');tb.innerHTML='';j.sources.forEach(s=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${s.id}</td><td>${s.name}</td><td>${s.base_url}</td><td>${s.official}</td><td>${s.enabled}</td><td>${s.last_run?JSON.stringify(s.last_run):'-'}</td><td><button onclick="run('${s.id}')">Run now</button></td>`;tb.appendChild(tr)});}async function run(id){const r=await fetch('/api/scrape?source='+id);const j=await r.json();document.getElementById('out').textContent=JSON.stringify(j,null,2)}load()</script></body></html>"""

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return LOGIN_HTML

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not verify_session(request):
        return RedirectResponse("/login")
    return DASHBOARD_HTML

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if verify_session(request):
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")
