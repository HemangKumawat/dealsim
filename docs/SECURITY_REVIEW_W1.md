# DealSim Security Review — Week 1

**Auditor:** Claude (automated security review)
**Date:** 2026-03-19
**Scope:** All Python files in `src/dealsim_mvp/`
**Severity scale:** CRITICAL / HIGH / MEDIUM / LOW

---

## Executive Summary

The DealSim backend is a FastAPI application with no SQL database, no authentication for normal users, and file-based persistence (JSON/JSONL). The attack surface is moderate. No CRITICAL vulnerabilities were found. The most significant issues are: a hardcoded default admin key, XSS in the admin HTML dashboard, admin key leakage in rendered HTML, missing session ID validation, rate limiter memory leak, and several medium-severity gaps in input validation and concurrency safety.

**Finding count:** 4 HIGH, 8 MEDIUM, 5 LOW

---

## 1. Input Validation

### 1.1 — Missing `session_id` format validation (MEDIUM)

**File:** `src/dealsim_mvp/api/routes.py`, lines 380, 407, 466, 494, 539
**File:** `src/dealsim_mvp/core/session.py`, line 243

Session IDs are generated as UUID4 (good) but are accepted from the URL path without any format validation. An attacker can pass arbitrary strings (including very long strings or strings with special characters) as session_id. While this only hits a dict lookup and raises KeyError -> 404, the lack of validation means:
- Unbounded-length strings are passed through logging (`logger.exception`) which could flood log files
- No protection against path segments that could confuse reverse proxies

**Fix:**
```python
# routes.py — add a dependency or inline check at the top of each session endpoint
import re

_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

def _validate_session_id(session_id: str) -> str:
    if not _UUID4_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    return session_id

# Then at the top of each endpoint:
# session_id = _validate_session_id(session_id)
```

### 1.2 — `scenario_type` not validated against enum (LOW)

**File:** `src/dealsim_mvp/api/routes.py`, line 82

`CreateSessionRequest.scenario_type` is a free `str` field. Unknown scenario types silently fall back to salary negotiation templates in `persona.py` line 612. This is safe but could confuse users and pollutes analytics with arbitrary type strings.

**Fix:**
```python
# routes.py, CreateSessionRequest
from typing import Literal

scenario_type: Literal["salary", "freelance", "rent", "medical_bill", "car_buying",
                        "scope_creep", "raise", "vendor", "counter_offer", "budget_request"] = Field(
    default="salary"
)
```

### 1.3 — `difficulty` not validated against enum (LOW)

**File:** `src/dealsim_mvp/api/routes.py`, line 84

Same issue as above — `difficulty` accepts any string. Invalid values silently produce a "medium" persona.

**Fix:**
```python
difficulty: Literal["easy", "medium", "hard"] = Field(default="medium")
```

### 1.4 — `user_id` unbounded in routes and analytics (MEDIUM)

**File:** `src/dealsim_mvp/api/routes.py`, lines 86, 261, 409
**File:** `src/dealsim_mvp/api/analytics.py`, lines 97, 142

`user_id` has no length constraint or character validation. An attacker can:
- Send arbitrarily long user_id strings that get written to JSONL files
- Use user_ids with newline characters to inject malformed JSONL lines
- Enumerate other users' history via `/api/users/{user_id}/history` since there is no authentication

**Fix:**
```python
# routes.py, CreateSessionRequest and ChallengeSubmitRequest
user_id: str = Field(default="", max_length=100, pattern=r"^[a-zA-Z0-9_\-]*$")

# routes.py, api_complete_session and api_get_user_history
from fastapi import Path as FastPath
user_id: str = FastPath(..., max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
```

### 1.5 — `event_type` allowlist is good but `properties` dict is unbounded (LOW)

**File:** `src/dealsim_mvp/api/routes.py`, lines 737-748

The `/api/events` endpoint correctly validates `event_type` against an allowlist. However, `properties` is an arbitrary dict with no size limit. An attacker can send megabytes of nested JSON that gets written to the JSONL analytics file.

**Fix:**
```python
# routes.py, EventRequest
class EventRequest(BaseModel):
    event_type: str = Field(..., max_length=50)
    properties: dict = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def limit_properties_size(cls, v):
        import json
        if len(json.dumps(v, default=str)) > 4096:
            raise ValueError("Properties payload too large (max 4KB)")
        return v
```

### 1.6 — No ReDoS risk detected (INFORMATIONAL)

All regex patterns in `simulator.py` (line 248), `core/offer_analyzer.py` (line 172), `api/offer_analyzer.py` (lines 669-753), and `email_audit.py` (lines 64-71, 87, 349) were reviewed. None contain the nested quantifier patterns that cause catastrophic backtracking. The money regex `\$?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(k)?` is safe. The offer text parsing regexes in `api/offer_analyzer.py` use anchored groups and non-greedy quantifiers appropriately.

---

## 2. Session Security

### 2.1 — Session IDs are cryptographically random (OK)

**File:** `src/dealsim_mvp/core/session.py`, line 286

Uses `uuid.uuid4()` which is backed by `os.urandom()` on all platforms. This is cryptographically secure and not enumerable.

### 2.2 — Sessions are enumerable via in-memory dict (MEDIUM)

**File:** `src/dealsim_mvp/core/session.py`, lines 372-385

`list_sessions()` returns metadata for ALL sessions. While this function is not exposed via an API route currently, it exists as a public function and could be accidentally wired up. Any future admin or debug endpoint that calls it would leak all active session IDs.

**Fix:** Either remove `list_sessions()` or ensure it is only callable from authenticated contexts. Add a comment:
```python
def list_sessions() -> list[dict]:
    """Return lightweight metadata for all sessions.

    WARNING: This exposes all session IDs. Only call from authenticated admin contexts.
    """
```

### 2.3 — Session store file has default OS permissions (MEDIUM)

**File:** `src/dealsim_mvp/core/store.py`, lines 51-57

The `.dealsim_sessions.json` file is written with default OS permissions. On shared hosting or multi-user systems, other users could read session data including full negotiation transcripts and persona hidden state.

**Fix:**
```python
# store.py, save_sessions function, after creating the tmp file:
import stat

tmp = str(_STORE_FILE) + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, default=str)

# Restrict permissions to owner only (Unix; no-op on Windows)
try:
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
except OSError:
    pass
```

### 2.4 — Race condition on concurrent session writes (MEDIUM)

**File:** `src/dealsim_mvp/core/session.py`, lines 210-218, 238-240

`_persist_all()` serializes ALL sessions and writes the entire file on every state change. With concurrent requests (uvicorn workers), two requests modifying different sessions can race:
1. Worker A reads all sessions, serializes
2. Worker B reads all sessions, serializes
3. Worker A writes file
4. Worker B writes file (overwrites A's changes)

The `store.py` atomic-rename pattern mitigates corruption but not lost updates.

**Fix:** For the MVP, add a threading lock around persist:
```python
# session.py, add at module level:
import threading
_persist_lock = threading.Lock()

def _persist_all() -> None:
    with _persist_lock:
        try:
            serialized = {
                sid: _serialize_session(sess) for sid, sess in _SESSIONS.items()
            }
            save_sessions(serialized)
        except Exception:
            logger.debug("Failed to persist sessions to file", exc_info=True)
```
Note: This only helps within a single process. Multi-worker uvicorn deployments need Redis or a database.

---

## 3. Rate Limiting

### 3.1 — Rate limiter memory leak (HIGH)

**File:** `src/dealsim_mvp/app.py`, lines 40-54

`_rate_store` is a `defaultdict(list)` that grows unboundedly. While timestamps older than 60 seconds are pruned from each IP's list, the dict keys themselves are never removed. An attacker sending one request per minute from millions of spoofed IPs (or behind a rotating proxy) causes the dict to grow indefinitely, eventually exhausting server memory.

**Fix:**
```python
# app.py, replace _check_rate_limit:
def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the request should be allowed."""
    now = time.time()
    window = now - 60.0
    timestamps = _rate_store[client_ip]
    _rate_store[client_ip] = [t for t in timestamps if t > window]

    # Evict stale IPs entirely to prevent memory leak
    if not _rate_store[client_ip]:
        del _rate_store[client_ip]
        _rate_store[client_ip] = []

    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        return False
    _rate_store[client_ip].append(now)
    return True

# Also add periodic cleanup (e.g., every 1000 requests):
_request_count = 0

# Inside rate_limit_middleware, before the check:
_request_count += 1
if _request_count % 1000 == 0:
    cutoff = time.time() - 60.0
    stale_keys = [k for k, v in _rate_store.items() if not v or max(v) < cutoff]
    for k in stale_keys:
        del _rate_store[k]
```

### 3.2 — Rate limiter uses `request.client.host` directly (MEDIUM)

**File:** `src/dealsim_mvp/app.py`, line 87

Behind a reverse proxy (nginx, Cloudflare, AWS ALB), `request.client.host` is the proxy's IP, not the real client. All users share one rate limit bucket, or one user can exhaust the limit for everyone.

However, blindly trusting `X-Forwarded-For` is also dangerous (easy to spoof). The fix depends on deployment context.

**Fix:**
```python
# app.py, rate_limit_middleware:
# Only trust X-Forwarded-For if behind a known proxy
TRUSTED_PROXIES = os.environ.get("TRUSTED_PROXIES", "").split(",")

async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"

    # Only use X-Forwarded-For if the direct client is a trusted proxy
    if client_ip in TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

    if not _check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Max 100 requests per minute."},
        )
    return await call_next(request)
```

### 3.3 — Expensive endpoints share the same rate limit (MEDIUM)

**File:** `src/dealsim_mvp/app.py`, lines 81-93

All endpoints share a single 100 req/min limit. Expensive operations like offer analysis (regex parsing), debrief generation (full transcript analysis), and playbook generation should have lower limits.

**Fix:** Implement tiered rate limiting:
```python
# Separate limits per endpoint category
RATE_LIMITS = {
    "default": 100,
    "expensive": 20,  # /offers/analyze, /sessions/{id}/debrief, /sessions/{id}/playbook
    "write": 30,      # POST /sessions, POST /feedback
}

EXPENSIVE_PATHS = {"/api/offers/analyze", "/api/sessions/", "/api/tools/audit-email"}

# In middleware, select the appropriate limit based on path
```

---

## 4. Data Exposure

### 4.1 — Admin key hardcoded with insecure default (HIGH)

**File:** `src/dealsim_mvp/app.py`, line 132

```python
admin_key = os.environ.get("DEALSIM_ADMIN_KEY", "change-this-secret")
```

If the environment variable is not set, the admin dashboard is accessible with the well-known key `change-this-secret`. This exposes all analytics data, feedback (including user emails), session counts, and feature usage.

**Fix:**
```python
# app.py, line 132:
admin_key = os.environ.get("DEALSIM_ADMIN_KEY", "")

def _verify_admin(key: str) -> None:
    if not admin_key:
        raise HTTPException(
            status_code=503,
            detail="Admin dashboard disabled — DEALSIM_ADMIN_KEY not configured"
        )
    if not secrets.compare_digest(key, admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key")
```
Also add `import secrets` at the top. Using `secrets.compare_digest` prevents timing attacks on the key comparison.

### 4.2 — Admin key leaked in HTML response (HIGH)

**File:** `src/dealsim_mvp/app.py`, line 239

The admin HTML dashboard embeds the admin key directly in the page:
```python
f'JSON API: <a href="/api/admin/stats?key={admin_key}" ...'
```

Anyone who views the HTML source (e.g., via browser dev tools, or if the page is cached by a CDN/proxy) can extract the admin key. This also means the key appears in browser history and server access logs.

**Fix:**
```python
# Replace line 239 with:
f'JSON API: <a href="/api/admin/stats?key=YOUR_KEY" style="color:#f95c5c;">/api/admin/stats?key=...</a>'
```

### 4.3 — Admin key passed as query parameter (MEDIUM)

**File:** `src/dealsim_mvp/app.py`, lines 139, 150

The admin key is passed as a URL query parameter (`?key=...`). This means:
- The key appears in browser history
- The key appears in HTTP server access logs
- The key may be logged by reverse proxies, CDNs, and WAFs
- The key is visible in the URL bar

**Fix (long-term):** Move to `Authorization` header:
```python
from fastapi import Header

def _verify_admin(authorization: str = Header(...)) -> None:
    if not admin_key:
        raise HTTPException(status_code=503, detail="Admin disabled")
    expected = f"Bearer {admin_key}"
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=403, detail="Invalid admin key")
```

### 4.4 — Error responses may leak internal details (MEDIUM)

**File:** `src/dealsim_mvp/api/routes.py`, line 354

```python
raise HTTPException(status_code=500, detail=str(exc))
```

On session creation failure, the raw exception string is returned to the client. This could leak internal paths, class names, or configuration details.

**Fix:**
```python
raise HTTPException(status_code=500, detail="Failed to create session. Please try again.")
```

### 4.5 — Analytics and feedback JSONL files not protected from direct access (LOW)

**File:** `src/dealsim_mvp/analytics.py`, line 28
**File:** `src/dealsim_mvp/feedback.py`, line 23

Data files are written to `data/events.jsonl` and `data/feedback.jsonl` relative to CWD (or `DEALSIM_DATA_DIR`). If the `data/` directory happens to fall under the static file mount path, these files become directly downloadable.

Currently the static mount is at `/static` pointing to a different directory, so this is not exploitable in the default configuration. But it is a latent risk if someone changes `STATIC_DIR` to the project root.

**Fix:** Add a check or use a path outside the static root:
```python
# analytics.py — ensure data dir is not under static dir
_DATA_DIR = Path(os.environ.get("DEALSIM_DATA_DIR",
    str(Path(__file__).resolve().parent.parent.parent.parent / "data")))
```

### 4.6 — XSS in admin HTML dashboard (HIGH)

**File:** `src/dealsim_mvp/app.py`, lines 159-171

Feedback comments and feature names are interpolated directly into HTML without escaping:
```python
comment = (item.get("comment", "") or "\u2014")[:80]
# ... later:
feedback_rows += f"<tr><td>{ts}</td><td>{stars}</td><td>{comment}</td></tr>\n"
```

A user submitting feedback with `<script>alert(1)</script>` as the comment will execute JavaScript when an admin views the dashboard.

Similarly, `fname` in feature usage rows (line 161) comes from analytics data and is unescaped.

**Fix:**
```python
# app.py, add at top of file:
from html import escape

# Then in admin_stats_html, escape all user-controlled content:
comment = escape((item.get("comment", "") or "\u2014")[:80])
ts = escape(item.get("submitted_at", "")[:19])
# ... and for feature names:
feature_rows += f"<tr><td>{escape(fname)}</td><td>{count}</td></tr>\n"
# ... and for scenario names:
scenario_rows += f"<tr><td>{escape(stype)}</td><td>{count}</td></tr>\n"
```

---

## 5. Dependency Audit

### 5.1 — Dependency versions are loosely pinned (LOW)

**File:** `pyproject.toml`, lines 10-14

```toml
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "pydantic>=2.0",
]
```

Using `>=` without upper bounds means `pip install` will pull the latest version, which could introduce breaking changes or vulnerabilities in production.

**Fix:** Pin to known-good ranges:
```toml
dependencies = [
    "fastapi>=0.110,<0.116",
    "uvicorn[standard]>=0.27,<0.35",
    "pydantic>=2.0,<3.0",
]
```

### 5.2 — No known CVEs in declared dependencies (OK)

As of the audit date, FastAPI 0.110+, uvicorn 0.27+, and pydantic 2.0+ have no outstanding critical CVEs. The project has a minimal dependency footprint which is a security positive.

### 5.3 — No `requirements.txt` lock file (LOW)

There is no lock file (`requirements.txt` with pinned hashes or `uv.lock`). Builds are not reproducible, and supply-chain attacks via dependency confusion are theoretically possible.

**Fix:** Generate a lock file:
```bash
pip freeze > requirements.lock
# Or use: uv pip compile pyproject.toml -o requirements.lock
```

---

## 6. Additional Findings

### 6.1 — `hashlib.md5` used for challenge rotation (LOW)

**File:** `src/dealsim_mvp/api/analytics.py`, line 310

```python
idx = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(CHALLENGE_POOL)
```

MD5 is used only for deterministic date-to-index mapping, not for security. This is acceptable but will trigger security scanners. Consider using `hashlib.sha256` as a drop-in replacement to avoid false positives.

### 6.2 — Docs endpoint exposed in production (LOW)

**File:** `src/dealsim_mvp/app.py`, lines 66-67

```python
docs_url="/docs",
redoc_url="/redoc",
```

The OpenAPI docs are enabled in all environments. While useful for development, they reveal the full API schema to anyone in production.

**Fix:**
```python
import os
_is_prod = os.environ.get("ENVIRONMENT", "").lower() == "production"

app = FastAPI(
    title="DealSim API",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
)
```

### 6.3 — CORS allows all origins by default (MEDIUM)

**File:** `src/dealsim_mvp/app.py`, lines 71-78

```python
allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
```

The default CORS policy is `*` (allow all origins) with `allow_credentials=True`. This combination means any website can make authenticated cross-origin requests to the API. While there's no cookie-based auth currently, this is a dangerous default if auth is added later.

**Fix:**
```python
allowed_origins = os.environ.get("CORS_ORIGINS", "").split(",")
allowed_origins = [o.strip() for o in allowed_origins if o.strip()]

if not allowed_origins:
    logger.warning("CORS_ORIGINS not set — defaulting to localhost only")
    allowed_origins = ["http://localhost:3000", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if "*" not in allowed_origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Summary Table

| # | Severity | Category | File | Description |
|---|----------|----------|------|-------------|
| 4.6 | HIGH | XSS | app.py:159-171 | Unescaped user content in admin HTML |
| 4.1 | HIGH | Auth | app.py:132 | Default admin key `change-this-secret` |
| 4.2 | HIGH | Auth | app.py:239 | Admin key embedded in HTML response |
| 3.1 | HIGH | DoS | app.py:40-54 | Rate limiter dict never evicts stale IPs |
| 1.1 | MEDIUM | Validation | routes.py:380+ | No session_id format validation |
| 1.4 | MEDIUM | Validation | routes.py:86+ | user_id unbounded, no auth on history |
| 2.2 | MEDIUM | Session | session.py:372 | list_sessions() exposes all session IDs |
| 2.3 | MEDIUM | Session | store.py:51 | Session file has default OS permissions |
| 2.4 | MEDIUM | Session | session.py:210 | Race condition on concurrent writes |
| 3.2 | MEDIUM | RateLimit | app.py:87 | Proxy-unaware IP detection |
| 3.3 | MEDIUM | RateLimit | app.py:81 | Uniform limit for all endpoint tiers |
| 4.4 | MEDIUM | DataExpose | routes.py:354 | Raw exception in 500 response |
| 6.3 | MEDIUM | CORS | app.py:71-78 | Wildcard CORS + credentials |
| 1.2 | LOW | Validation | routes.py:82 | scenario_type not enum-validated |
| 1.3 | LOW | Validation | routes.py:84 | difficulty not enum-validated |
| 1.5 | LOW | Validation | routes.py:290 | Unbounded event properties dict |
| 4.5 | LOW | DataExpose | analytics.py:28 | Data files potentially under static root |
| 5.1 | LOW | Deps | pyproject.toml:10 | Loose version pins |
| 5.3 | LOW | Deps | (missing) | No lock file for reproducible builds |
| 6.1 | LOW | Crypto | api/analytics.py:310 | MD5 usage (non-security, scanner noise) |
| 6.2 | LOW | Exposure | app.py:66 | API docs exposed in production |

---

## Recommended Priority

1. **Immediate (before any public deploy):** Fix items 4.6, 4.1, 4.2, 3.1
2. **Before beta users:** Fix items 1.4, 4.4, 6.3, 3.2
3. **Before production:** Fix items 2.3, 2.4, 3.3, 1.1, 5.1
4. **Hardening (nice to have):** All LOW items
