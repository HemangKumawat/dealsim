# OWASP Top 10 (2021) Security Audit — DealSim MVP

**Auditor:** Application Security Review (Automated)
**Date:** 2026-03-19
**Scope:** All Python files in `src/dealsim_mvp/` and `static/index.html`
**Framework:** FastAPI 0.135 + Pydantic v2, single-page HTML frontend

---

## Executive Summary

DealSim is a negotiation training simulator with no authentication, no database, and no payment processing. The attack surface is relatively narrow: a FastAPI backend serving JSON APIs and static HTML, with JSONL file storage. The codebase already applies several good practices (Pydantic validation, UUID format enforcement, `html_escape` in admin HTML, `escapeHtml` in frontend JS, `secrets.compare_digest` for admin key, rate limiting).

**Critical findings: 0**
**High findings: 4**
**Medium findings: 8**
**Low findings: 5**

No SQL injection or command injection vectors exist (no SQL database, no shell calls). No SSRF vectors exist (no outbound HTTP requests from the backend).

---

## A01 — Broken Access Control

### FINDING A01-1: No Authorization on Session Endpoints (MEDIUM)

**File:** `src/dealsim_mvp/api/routes.py`, lines 394, 482, 511, 557
**Description:** Any client who knows (or guesses) a session UUID can read its transcript, debrief, and scorecard. There is no ownership check tying a session to its creator.
**Impact:** Session data (negotiation transcripts, scores) of other users can be read by anyone who obtains the UUID. UUIDs are v4 (random), which provides some protection, but they are returned in API responses and could be logged or leaked.
**Fix:**
```python
# In routes.py — add an optional user_id ownership check:
def _validate_session_ownership(session_id: str, user_id: str | None) -> None:
    """If user_id is provided, verify the session belongs to that user."""
    if not user_id:
        return  # Anonymous access allowed for MVP
    # Implement when user auth is added
```

### FINDING A01-2: User History Endpoint Has No Access Control (MEDIUM)

**File:** `src/dealsim_mvp/api/routes.py`, lines 672-674
**Description:** `GET /api/users/{user_id}/history` returns full session history for any `user_id` without authentication. The `user_id` parameter is a free-form string with no validation.
**Impact:** Any user can enumerate and read another user's negotiation history, scores, and patterns.
**Fix:**
```python
# Add user_id format validation (e.g., require UUID format):
_USER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

def _validate_user_id(user_id: str) -> str:
    if not _USER_ID_RE.match(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    return user_id
```

### FINDING A01-3: Admin Key Passed as Query Parameter (HIGH)

**File:** `src/dealsim_mvp/app.py`, lines 163-164
**Description:** The admin key is passed as a URL query parameter (`?key=...`). Query parameters are logged in web server access logs, browser history, HTTP Referer headers, and proxy logs.
**Impact:** Admin credential leakage through infrastructure logging.
**Fix:**
```python
# Use a header instead of query parameter:
from fastapi import Header

@app.get("/api/admin/stats", tags=["admin"])
def admin_stats_json(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    _verify_admin(x_admin_key)
    ...
```

---

## A02 — Cryptographic Failures

### FINDING A02-1: MD5 Used for Challenge Selection (LOW)

**File:** `src/dealsim_mvp/api/analytics.py`, line 310
**Description:** `hashlib.md5(today.encode())` is used to deterministically select the daily challenge. MD5 is cryptographically broken.
**Impact:** Minimal — this is not a security-sensitive operation (just selecting a challenge index from a pool of 7). No secrets or authentication tokens are derived from it.
**Fix (defense in depth):**
```python
import hashlib
idx = int(hashlib.sha256(today.encode()).hexdigest(), 16) % len(CHALLENGE_POOL)
```

### FINDING A02-2: No Encryption on Stored Data (LOW)

**File:** `src/dealsim_mvp/core/store.py`, `src/dealsim_mvp/analytics.py`, `src/dealsim_mvp/feedback.py`
**Description:** All JSONL data files and the session store JSON are written in plaintext. Feedback records may include user-provided email addresses.
**Impact:** If the server filesystem is compromised, all data (including optional email addresses from feedback) is readable.
**Fix:** For the MVP scope, document this as a known limitation. For production, encrypt JSONL files at rest or use a database with encryption.

---

## A03 — Injection

### FINDING A03-1: innerHTML Used with Server-Supplied Data in Frontend (MEDIUM)

**File:** `static/index.html`, lines 1602, 2034, 2044, 2053, 2063, 2131, 2249, 2437
**Description:** Multiple places use `.innerHTML` to render server-returned data. The codebase defines and uses an `escapeHtml()` function in most places, which is good. However, several `innerHTML` assignments construct HTML from numeric server values (scores, percentiles) without escaping.
**Impact:** If a future code change introduces a string value where a numeric one is currently expected, or if the API response is tampered with (MITM without HTTPS), XSS is possible. Current risk is low because the values are numeric and the app uses `escapeHtml` for string data.
**Fix:** Use `textContent` for simple values; for complex HTML, ensure all interpolated values pass through `escapeHtml`:
```javascript
// Example — line 2034, use escapeHtml on ALL values:
contentEl.innerHTML += '...<div class="text-3xl font-extrabold">'
    + escapeHtml(String(data.overall_score)) + '</div>...';
```

### FINDING A03-2: No SQL/NoSQL Injection Surface (INFORMATIONAL)

The application uses no database — only JSONL flat files and in-memory dicts. There is no SQL injection, NoSQL injection, or ORM injection surface.

### FINDING A03-3: No Command Injection Surface (INFORMATIONAL)

The application makes no `subprocess`, `os.system`, `os.popen`, or `eval()` calls on user input.

---

## A04 — Insecure Design

### FINDING A04-1: No Authentication System (HIGH)

**File:** Application-wide
**Description:** DealSim has zero authentication. The `user_id` field is a client-provided string — there is no login, no token issuance, no session cookies. Any client can claim any `user_id`.
**Impact:** Users cannot be reliably identified. One user can impersonate another by sending the same `user_id` string. History and patterns for any user are publicly accessible.
**Fix (for production):**
```python
# Implement token-based auth. Minimum viable:
# 1. Issue a signed JWT or opaque token on first visit (stored in localStorage)
# 2. Validate token on every request via a dependency
from fastapi import Depends, Security
from fastapi.security import HTTPBearer

security = HTTPBearer(auto_error=False)

async def get_current_user(credentials = Security(security)):
    if not credentials:
        return None  # Anonymous
    # Validate JWT and extract user_id
    ...
```

### FINDING A04-2: In-Memory Rate Limiter Not Shared Across Workers (MEDIUM)

**File:** `src/dealsim_mvp/app.py`, lines 42-70
**Description:** The rate limiter uses a Python `defaultdict` in process memory. If the app is deployed with multiple Uvicorn workers (e.g., `--workers 4`), each worker has its own independent rate store, allowing an attacker to bypass the limit by distributing requests across workers.
**Impact:** Rate limit is effectively multiplied by the number of workers. An attacker gets `100 * N` requests per minute where N is the worker count.
**Fix:**
```python
# For multi-worker deployments, use Redis-backed rate limiting:
# pip install slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
# For production: storage_uri="redis://localhost:6379"
```

### FINDING A04-3: Unbounded In-Memory Session Growth (MEDIUM)

**File:** `src/dealsim_mvp/core/session.py`, line 81
**Description:** `_SESSIONS` dict grows without bound during the lifetime of a worker process. The file-based store cleans sessions older than 1 hour on load, but the in-memory dict is never pruned while the process runs.
**Impact:** Memory exhaustion DoS — an attacker creating sessions continuously will eventually exhaust server memory.
**Fix:**
```python
# Add periodic cleanup in _store_session:
import time

_last_memory_cleanup = 0.0

def _store_session(session: NegotiationSession) -> None:
    global _last_memory_cleanup
    with _sessions_lock:
        _SESSIONS[session.session_id] = session
        now = time.time()
        if now - _last_memory_cleanup > 300:  # every 5 minutes
            cutoff = now - 3600
            stale = [
                sid for sid, s in _SESSIONS.items()
                if s.created_at.timestamp() < cutoff
            ]
            for sid in stale:
                del _SESSIONS[sid]
            _last_memory_cleanup = now
        _persist_all()
```

---

## A05 — Security Misconfiguration

### FINDING A05-1: Swagger/OpenAPI Docs Enabled by Default (LOW)

**File:** `src/dealsim_mvp/app.py`, lines 82-83
**Description:** `/docs` (Swagger UI) and `/redoc` are enabled in all environments. These expose the full API schema including the admin endpoint.
**Impact:** Information disclosure — attackers can discover all endpoints, parameters, and response shapes.
**Fix:**
```python
import os
is_prod = os.environ.get("DEALSIM_ENV", "dev") == "production"
app = FastAPI(
    ...
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
)
```

### FINDING A05-2: No Security Headers (Content-Security-Policy, HSTS, etc.) (HIGH)

**File:** `src/dealsim_mvp/app.py` — missing entirely
**Description:** The application sets no security headers. Missing: `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.
**Impact:** The application is vulnerable to clickjacking (no X-Frame-Options), MIME-sniffing attacks, and has no CSP to mitigate XSS impact. The HTML loads Tailwind CSS from `cdn.tailwindcss.com` and fonts from Google — without CSP, any injected script can exfiltrate data.
**Fix:**
```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response
```

### FINDING A05-3: CORS Allows All Methods and All Headers (MEDIUM)

**File:** `src/dealsim_mvp/app.py`, lines 92-98
**Description:** `allow_methods=["*"]` and `allow_headers=["*"]` are overly permissive. The application only needs GET and POST with standard headers.
**Impact:** Expands the attack surface for CORS-based attacks. While origins are restricted, the wildcard methods/headers weaken the defense.
**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials="*" not in allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)
```

---

## A06 — Vulnerable and Outdated Components

### FINDING A06-1: Tailwind CSS Loaded from CDN Without Integrity Hash (MEDIUM)

**File:** `static/index.html`, line 7
**Description:** `<script src="https://cdn.tailwindcss.com"></script>` loads JavaScript from a third-party CDN with no Subresource Integrity (SRI) hash. If the CDN is compromised, arbitrary JavaScript executes in the application context.
**Impact:** Supply chain attack vector — CDN compromise leads to full XSS on every page load.
**Fix:**
```html
<!-- Option A: Pin version and add SRI hash -->
<script src="https://cdn.tailwindcss.com/3.4.1"
  integrity="sha384-<HASH>"
  crossorigin="anonymous"></script>

<!-- Option B (recommended for production): Bundle Tailwind at build time -->
<!-- Use Tailwind CLI to generate a static CSS file, eliminating runtime JS -->
```

### FINDING A06-2: Google Fonts Loaded Without SRI (LOW)

**File:** `static/index.html`, line 25
**Description:** Google Fonts CSS loaded without integrity verification.
**Impact:** Lower risk than JS (CSS injection is less powerful), but still a supply chain consideration.
**Fix:** For production, self-host the Inter font files.

---

## A07 — Identification and Authentication Failures

### FINDING A07-1: Admin Authentication via Static API Key (HIGH)

**File:** `src/dealsim_mvp/app.py`, lines 152-161
**Description:** Admin access is protected by a single static API key from an environment variable. There is no key rotation mechanism, no brute-force protection on the admin endpoint, and no audit logging of admin access.
**Impact:** If the key is leaked (query parameter logging per A01-3, env var exposure), an attacker gains full read access to all analytics and feedback data including user email addresses. The rate limiter applies but 100 attempts/minute allows brute-forcing short keys.
**Fix:**
```python
# 1. Move key to header (see A01-3)
# 2. Add failed-attempt logging:
def _verify_admin(key: str) -> None:
    if not admin_key:
        raise HTTPException(status_code=503, ...)
    if not secrets.compare_digest(key, admin_key):
        logger.warning("Failed admin auth attempt")
        raise HTTPException(status_code=403, detail="Invalid admin key")

# 3. Require minimum key length at startup:
admin_key = os.environ.get("DEALSIM_ADMIN_KEY", "")
if admin_key and len(admin_key) < 32:
    logger.warning("DEALSIM_ADMIN_KEY is shorter than 32 chars — increase key length")
```

---

## A08 — Software and Data Integrity Failures

### FINDING A08-1: No Verification of CDN-Loaded Scripts (MEDIUM)

**File:** `static/index.html`, line 7
**Description:** Same as A06-1 — the Tailwind CDN script has no SRI hash. This is also an integrity failure: there is no mechanism to verify the loaded code matches expected content.
**Impact:** Covered in A06-1.

### FINDING A08-2: Session Store Has No Integrity Verification (LOW)

**File:** `src/dealsim_mvp/core/store.py`
**Description:** The JSON session store file (`.dealsim_sessions.json`) has no checksum or HMAC. A local attacker who can write to the filesystem could manipulate session data (e.g., set `agreed_value` to an extreme number, alter transcripts).
**Impact:** Low — requires filesystem access, and the data is only used for training feedback (not financial transactions).
**Fix:** Accept the risk for MVP. For production, use a database with access controls.

---

## A09 — Security Logging and Monitoring Failures

### FINDING A09-1: No Audit Logging for Admin Access (MEDIUM)

**File:** `src/dealsim_mvp/app.py`, lines 163-172
**Description:** Successful admin authentication is not logged. Neither successful nor failed admin access attempts are recorded in the analytics or application logs.
**Impact:** Cannot detect or investigate unauthorized admin access.
**Fix:**
```python
@app.get("/api/admin/stats", tags=["admin"])
def admin_stats_json(key: str = FastQuery(...)):
    _verify_admin(key)
    logger.info("Admin stats accessed successfully")
    ...
```

### FINDING A09-2: Exception Handling Silences Errors in Analytics (LOW)

**File:** `src/dealsim_mvp/api/routes.py`, lines 76-79
**Description:** The `_track()` helper catches all exceptions silently (`except Exception: pass`). If the analytics system fails, there is zero visibility.
**Impact:** Analytics failures are invisible. More critically, this pattern could mask errors that indicate an attack (e.g., disk full from a DoS writing sessions).
**Fix:**
```python
def _track(event_type: str, data: dict | None = None) -> None:
    try:
        get_tracker().track(event_type, data)
    except Exception:
        logger.debug("Analytics tracking failed for %s", event_type, exc_info=True)
```

---

## A10 — Server-Side Request Forgery (SSRF)

### No SSRF Findings

The application makes no outbound HTTP requests from the backend. All market data is bundled statically. No user-supplied URLs are fetched. SSRF is not applicable.

---

## Summary Table

| ID | Category | Severity | File | Line(s) | Status |
|---|---|---|---|---|---|
| A01-1 | Broken Access Control | MEDIUM | routes.py | 394, 482, 511 | Open |
| A01-2 | Broken Access Control | MEDIUM | routes.py | 672-674 | Open |
| A01-3 | Broken Access Control | HIGH | app.py | 163-164 | Open |
| A02-1 | Cryptographic Failures | LOW | api/analytics.py | 310 | Open |
| A02-2 | Cryptographic Failures | LOW | store.py, analytics.py, feedback.py | various | Open |
| A03-1 | Injection (XSS) | MEDIUM | index.html | 2034, 2131, etc. | Open |
| A04-1 | Insecure Design | HIGH | Application-wide | — | Open |
| A04-2 | Insecure Design | MEDIUM | app.py | 42-70 | Open |
| A04-3 | Insecure Design | MEDIUM | session.py | 81 | Open |
| A05-1 | Security Misconfiguration | LOW | app.py | 82-83 | Open |
| A05-2 | Security Misconfiguration | HIGH | app.py | missing | Open |
| A05-3 | Security Misconfiguration | MEDIUM | app.py | 92-98 | Open |
| A06-1 | Vulnerable Components | MEDIUM | index.html | 7 | Open |
| A06-2 | Vulnerable Components | LOW | index.html | 25 | Open |
| A07-1 | Auth Failures | HIGH | app.py | 152-161 | Open |
| A08-1 | Data Integrity | MEDIUM | index.html | 7 | Open |
| A08-2 | Data Integrity | LOW | store.py | — | Open |
| A09-1 | Logging Failures | MEDIUM | app.py | 163-172 | Open |
| A09-2 | Logging Failures | LOW | routes.py | 76-79 | Open |

---

## Positive Security Controls Already in Place

1. **Pydantic input validation** — All request bodies are validated with type constraints, min/max lengths, and `ge`/`le` bounds (routes.py).
2. **UUID4 format validation** — Session IDs are validated against a strict regex before use (`_validate_session_id`, routes.py line 35-39).
3. **HTML escaping in admin dashboard** — Server-side HTML uses `html_escape()` on all user-supplied values (app.py line 186-196).
4. **Frontend XSS protection** — `escapeHtml()` function is defined and used consistently for string values rendered via `innerHTML` (index.html line 1159).
5. **Timing-safe admin key comparison** — `secrets.compare_digest()` prevents timing attacks on the admin key (app.py line 160).
6. **Rate limiting** — Per-IP rate limiter with periodic cleanup prevents basic DoS (app.py lines 42-70).
7. **Event type allowlist** — The `/api/events` endpoint restricts accepted event types to a hardcoded set (routes.py lines 757-765).
8. **No PII collection by default** — Analytics explicitly avoids cookies and PII; email is optional and user-initiated.
9. **Atomic file writes** — Session persistence uses `fsync` + `os.replace` for crash safety (store.py lines 63-68).
10. **Message length limits** — User messages are capped at 2000 characters via Pydantic (routes.py line 112).

---

## Recommended Priority Order

1. **A05-2** — Add security headers (quick win, high impact)
2. **A01-3** — Move admin key from query param to header
3. **A07-1** — Add admin auth logging and key length enforcement
4. **A06-1/A08-1** — Add SRI hash to CDN script or bundle Tailwind
5. **A04-1** — Design authentication system for production
6. **A04-3** — Add in-memory session cleanup
7. **A05-3** — Restrict CORS methods/headers
8. **A04-2** — Plan for distributed rate limiting before multi-worker deployment
