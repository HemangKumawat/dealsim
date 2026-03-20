# P0 Security & Bug Fixes — Round 2

Applied: 2026-03-19
Test result: 310/310 passed (0.47s)

## Fix 1: Admin key moved from URL query parameter to Authorization header

**File:** `src/dealsim_mvp/app.py`

**Problem:** Admin key was passed as `?key=...` query parameter, which gets logged in server access logs, browser history, and proxy logs.

**Changes:**
- `_verify_admin()` now accepts a `Request` object and reads `request.headers.get("authorization")`
- Supports both raw key and `Bearer <key>` format
- Both `/api/admin/stats` and `/admin/stats` endpoints updated to pass `request` instead of a query param
- Removed HTML link that embedded `?key=YOUR_KEY` in the admin dashboard footer

## Fix 2: Rate limiter memory cap

**File:** `src/dealsim_mvp/app.py`

**Problem:** `_rate_store` was a `defaultdict(list)` that could grow unbounded under a DDoS with many unique IPs. The `del _rate_store[client_ip]` on line 65 was dead code because `defaultdict` recreates the key on the next access (line 67).

**Changes:**
- Replaced `defaultdict(list)` with a regular `dict`
- All accesses now use `.get()` instead of direct subscript to avoid auto-creation
- Added `_RATE_STORE_MAX_IPS = 10_000` cap; when exceeded, the oldest IP entry is evicted before adding a new one
- Eliminated the dead-code `del` pattern

## Fix 3: X-Forwarded-For support in rate limiter

**File:** `src/dealsim_mvp/app.py`

**Problem:** Behind nginx or a load balancer, `request.client.host` returns the proxy IP, not the real client. All clients share one rate limit bucket.

**Changes:**
- Rate limit middleware now reads `X-Forwarded-For` header first
- Takes only the leftmost (first) IP from the comma-separated list, which is the real client
- Falls back to `request.client.host` when the header is absent

## Fix 4: Global exception handler

**File:** `src/dealsim_mvp/app.py`

**Problem:** Unhandled exceptions could leak stack traces, file paths, and internal details to clients.

**Changes:**
- Added `@app.exception_handler(Exception)` that returns a generic `{"detail": "Internal server error"}` with HTTP 500
- Full traceback is logged server-side via `logger.error()` with `traceback.format_exc()`

## Fix 5: Session status bug

**File:** `src/dealsim_mvp/api/routes.py`

**Problem:** `api_get_session()` returned `state.persona.name` (the opponent's name, e.g. "Sarah Chen") in the `status` field instead of the actual session lifecycle status ("active", "completed", "abandoned").

**Changes:**
- Added `get_session_status()` call to retrieve the `SessionStatus` enum from the session object
- `status` field now returns `session_status.value` (the correct string)
