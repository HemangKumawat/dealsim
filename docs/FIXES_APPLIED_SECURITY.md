# Security Fixes Applied — 2026-03-19

Based on findings from `SECURITY_REVIEW_W1.md` and `DEPLOYMENT_REVIEW_W1.md`.

---

## CRITICAL Fixes

### 1. CORS environment variable name mismatch (CRITICAL)
**File:** `src/dealsim_mvp/app.py` line 71
**Problem:** App read `CORS_ORIGINS` but all deployment configs set `DEALSIM_CORS_ORIGINS`. CORS defaulted to `*` on every deployment.
**Fix:** Changed to read `DEALSIM_CORS_ORIGINS`. When unset, defaults to localhost origins with a warning log instead of wildcard.

### 2. XSS in admin HTML dashboard (HIGH)
**File:** `src/dealsim_mvp/app.py` lines 161, 169-171, 178
**Problem:** Feedback comments, feature names, scenario types, and timestamps were interpolated into HTML without escaping. Malicious feedback could execute JavaScript in the admin's browser.
**Fix:** Added `from html import escape as html_escape` and applied `html_escape()` to all user-controlled strings before HTML interpolation: `fname`, `comment`, `ts`, `stype`.

### 3. Admin key: insecure default + timing-vulnerable comparison (HIGH)
**File:** `src/dealsim_mvp/app.py` lines 132-136
**Problem:** Default admin key was `"change-this-secret"` — admin dashboard fully accessible on any deployment that forgot to set the env var. Key comparison used `!=` which is vulnerable to timing attacks.
**Fix:** Default changed to empty string `""`. When unset, admin endpoints return 503 "Admin dashboard disabled". Comparison changed to `secrets.compare_digest()` for timing-safe equality check. Added `import secrets`.

### 4. Admin key leaked in HTML source (HIGH)
**File:** `src/dealsim_mvp/app.py` line 239
**Problem:** The admin key was embedded in an `<a href>` tag in the HTML dashboard, exposing it in page source, browser history, and proxy logs.
**Fix:** Replaced `key={admin_key}` with static placeholder text `key=YOUR_KEY`.

### 5. Rate limiter memory leak (HIGH)
**File:** `src/dealsim_mvp/app.py` lines 40-54
**Problem:** `_rate_store` dict keys were never evicted. An attacker rotating IPs would cause unbounded memory growth.
**Fix:** Two-layer cleanup:
- Per-request: delete IP key when its timestamp list becomes empty after pruning.
- Periodic sweep: every 60 seconds, scan all keys and evict any with no timestamps within the active window.

---

## HIGH Fixes

### 6. Docker container runs as root (HIGH)
**File:** `Dockerfile` lines 17-18
**Problem:** All processes ran as root inside the container. A uvicorn compromise would give full container access.
**Fix:** Added `RUN useradd --create-home --shell /bin/bash dealsim`, `chown` on the data directory, and `USER dealsim` directive before `EXPOSE`.

### 7. docker-compose health check uses missing `curl` (HIGH)
**File:** `docker-compose.yml` line 16
**Problem:** `python:3.12-slim` does not include `curl`. The health check always failed.
**Fix:** Changed to `["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]`, matching the Dockerfile's own HEALTHCHECK pattern.

### 8. CORS wildcard + credentials combination (HIGH)
**File:** `src/dealsim_mvp/app.py` lines 72-78
**Problem:** `allow_origins=["*"]` combined with `allow_credentials=True` allows any website to make credentialed cross-origin requests.
**Fix:** `allow_credentials` is now conditional: `True` only when origins are explicitly listed, `False` when wildcard `*` is present.

### 9. Raw exception strings leaked in 500 responses (HIGH)
**File:** `src/dealsim_mvp/api/routes.py` line 354
**Problem:** `detail=str(exc)` exposed internal error messages (file paths, class names, config) to clients.
**Fix:** Changed to generic `detail="Internal server error"`. The exception is still logged server-side via `logger.exception()`.

### 10. Session ID format validation (MEDIUM, upgraded to HIGH scope)
**File:** `src/dealsim_mvp/api/routes.py`
**Problem:** Session IDs accepted arbitrary strings from URL paths. Attackers could pass very long strings or special characters that flood logs or confuse proxies.
**Fix:** Added `_validate_session_id()` function with UUID4 regex validation. Applied to all 5 session endpoints: `api_send_message`, `api_complete_session`, `api_get_session`, `api_get_debrief`, `api_get_playbook`. Invalid IDs return 400 before any business logic executes.

---

## Test Impact

- 3 existing tests that used `"fake-id"` as a session ID now correctly receive 400 (format validation) instead of 404. Tests updated to verify both the 400 (bad format) and 404 (valid format, nonexistent session) cases.
- 3 new test cases added: `test_400_for_invalid_session_id_format` in `TestSendMessage`, `TestCompleteSession`, and `TestGetSession`.
- **Result: 300/301 tests pass.** The 1 failure (`test_no_deal_money_left`) is a pre-existing issue in the debrief module unrelated to security changes.

---

## Files Modified

| File | Changes |
|------|---------|
| `src/dealsim_mvp/app.py` | Fixes 1-5, 8 (CORS, XSS, admin key, rate limiter) |
| `src/dealsim_mvp/api/routes.py` | Fixes 9-10 (error masking, session ID validation) |
| `Dockerfile` | Fix 6 (non-root user) |
| `docker-compose.yml` | Fix 7 (health check) |
| `tests/test_api.py` | Updated 3 tests + added 3 new validation tests |
