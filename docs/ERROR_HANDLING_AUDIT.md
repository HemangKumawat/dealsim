# Error Handling Audit

**Date:** 2026-03-19
**Scope:** All Python files in `src/dealsim_mvp/` and subdirectories (22 files)
**Auditor:** Reliability engineering review

---

## Executive Summary

The codebase demonstrates above-average error handling for an MVP. Analytics and feedback writes are correctly isolated from the main API path, session ID validation is in place, and file I/O uses thread locks with graceful degradation. However, several gaps remain: there is no global exception handler, some endpoints lack try/except entirely, one bare `except:` pattern silently swallows errors, and the rate limiter has a potential KeyError on a deleted key.

**Findings by severity:**

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 5 |
| Medium | 8 |
| Low | 4 |

---

## 1. Exception Granularity (Too Broad / Too Narrow)

### CRITICAL-01: No global exception handler in FastAPI app

**File:** `app.py`
**Lines:** 77-275

The `create_app()` factory registers CORS, rate limiting, and routes but never registers a global exception handler via `@app.exception_handler(Exception)` or equivalent. If any unhandled exception propagates past the route handlers, FastAPI's default behavior returns a 500 with a JSON body that may include the Python traceback in debug mode or a generic `{"detail": "Internal Server Error"}` in production. Neither is guaranteed to be user-friendly or consistently formatted.

**Recommendation:** Add a catch-all handler:

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )
```

Also add a `RequestValidationError` handler to return 400 with a clean message instead of Pydantic's raw error dump.

### HIGH-01: Several endpoints have no try/except at all

**File:** `api/routes.py`

The following endpoints call into core logic that can raise exceptions but have zero error handling:

| Endpoint | Function | Risk |
|----------|----------|------|
| `POST /offers/analyze` | `api_analyze_offer` | `analyze_offer()` could raise on malformed text; returns raw 500 |
| `GET /users/{user_id}/history` | `api_get_user_history` | File read failure in `_read_jsonl` is caught internally, but dict key access on the result is unguarded |
| `GET /users/{user_id}/patterns` | `api_get_user_patterns` | Same as above; additionally accesses `patterns["top_strength"]` etc. without safety |
| `POST /tools/audit-email` | `api_audit_email` | `audit_email()` is pure logic but still unguarded |
| `POST /tools/earnings-calculator` | `api_earnings_calculator` | `calculate_earnings_impact()` can raise if `current > negotiated` produces negative diff (by design, but unvalidated) |
| `GET /challenges/today` | `api_get_todays_challenge` | Unguarded dict key access on challenge data |
| `POST /challenges/today/submit` | `api_submit_challenge` | `submit_challenge_response()` does regex and file I/O; unguarded |
| `GET /sessions/{id}/debrief` | `api_get_debrief` | `generate_debrief()` is unguarded after state retrieval succeeds |
| `GET /sessions/{id}/playbook` | `api_get_playbook` | `generate_playbook()` is unguarded |

**Recommendation:** Wrap each endpoint's core logic call in try/except. At minimum, catch `Exception` and return a 500 with a user-friendly message, as is already done for `api_create_session`. Better: use the global handler from CRITICAL-01 as a safety net and add specific catches where meaningful (e.g., `ValueError` -> 400).

### MEDIUM-01: `api_send_message` catches `ValueError` and `RuntimeError` but surfaces `str(exc)` directly

**File:** `api/routes.py`, line 401
```python
except (ValueError, RuntimeError) as exc:
    raise HTTPException(status_code=409, detail=str(exc))
```

The internal `RuntimeError` message includes the session ID and status, which is acceptable. But if any internal `ValueError` is raised unexpectedly (not from the negotiation logic), its message could leak implementation details.

**Recommendation:** Use a fixed message for ValueError: `"Invalid request for this session state"` and log the real error.

---

## 2. User-Friendly Error Messages

### HIGH-02: Market data 404 leaks internal role list

**File:** `api/routes.py`, line 651-654
```python
available = get_available_roles()
raise HTTPException(
    status_code=404,
    detail=f"No data for role='{role}', location='{location}'. Available roles: {available}",
)
```

This dumps the full internal role list into the API response. While useful for developers, it exposes the application's data catalog to end users and potential attackers.

**Recommendation:** Return only `"No market data found for the specified role and location."` in the API. Log the available roles at debug level. Alternatively, provide the role list through a dedicated `/api/roles` endpoint.

### MEDIUM-02: Rate limit error message hardcodes the limit value

**File:** `app.py`, line 111
```python
content={"detail": "Rate limit exceeded. Max 100 requests per minute."},
```

The message says "100" but the actual limit comes from `RATE_LIMIT` which is configurable via env var. If the env var changes, the message becomes misleading.

**Recommendation:** Use `f"Rate limit exceeded. Max {RATE_LIMIT} requests per minute."`.

### LOW-01: Admin key validation returns 503 for "not configured"

**File:** `app.py`, lines 156-159

Returning 503 (Service Unavailable) for a missing admin key is semantically odd. 501 (Not Implemented) or 404 would be more appropriate.

---

## 3. HTTP Status Code Correctness

### HIGH-03: `api_submit_feedback` returns 200 on success instead of 201

**File:** `api/routes.py`, line 737

Feedback submission creates a new resource but returns the default 200. Should return 201 Created to be RESTful.

### MEDIUM-03: `api_track_event` returns 400 for unknown event type but the message includes the user-supplied value

**File:** `api/routes.py`, line 765
```python
detail=f"Unknown event type: {body.event_type}"
```

Echoing user input in error messages can enable reflected content injection in clients that render the error message as HTML. The `event_type` is limited to 50 chars by the model, which reduces risk.

**Recommendation:** Sanitize or omit the user-supplied value: `"Unknown event type. See API docs for valid types."`

### MEDIUM-04: `complete_session` on an already-completed session returns 200 with cached scorecard

This is documented behavior ("Safe to call on an already-completed session") but the API endpoint at `api_complete_session` does not distinguish between "first completion" and "re-fetch". A 200 for re-fetch and 201 for first completion would be cleaner. Alternatively, return a header or field indicating whether this is a fresh score.

### LOW-02: No 405 Method Not Allowed handling

FastAPI handles this automatically, but the default response body is `{"detail": "Method Not Allowed"}` which is fine. No action needed.

---

## 4. File I/O Error Handling

### HIGH-04: `serve_root` reads index.html without try/except

**File:** `app.py`, line 139
```python
def serve_root():
    return (static_dir / "index.html").read_text(encoding="utf-8")
```

If `index.html` is deleted after startup, or is unreadable (permissions, encoding error), this crashes with an unhandled `FileNotFoundError` or `UnicodeDecodeError`, returning a raw 500.

**Recommendation:** Wrap in try/except and return a graceful fallback HTML page or redirect to `/docs`.

### MEDIUM-05: Session store file operations handle errors correctly

**File:** `core/store.py`

Credit: `save_sessions` uses atomic write (tmp + fsync + os.replace), cleans up orphaned tmp files, and catches all exceptions. `load_sessions` handles corrupt JSON by archiving the bad file. `clear_store` uses `missing_ok=True`. This is solid.

### MEDIUM-06: Analytics and feedback JSONL writers silently swallow write failures

**Files:** `analytics.py` (line 241), `feedback.py` (line 169), `api/analytics.py` (line 40)

All JSONL write operations catch `Exception` and log a warning. The data is lost. This is acceptable for analytics (non-critical) but feedback data has user-facing value.

**Recommendation:** For feedback writes, consider a fallback in-memory buffer that retries on next write, or return a degraded response indicating the feedback could not be stored.

---

## 5. None Checks Before Attribute Access

### CRITICAL-02: Rate limiter accesses deleted key

**File:** `app.py`, lines 63-69
```python
_rate_store[client_ip] = [t for t in timestamps if t > window]
if not _rate_store[client_ip]:
    del _rate_store[client_ip]

if len(_rate_store[client_ip]) >= RATE_LIMIT:  # KeyError if just deleted
```

After line 65 deletes the empty list, line 67 accesses `_rate_store[client_ip]` which triggers `defaultdict(list)` to re-create an empty list. Since `defaultdict` auto-creates the key, this does not actually raise a `KeyError` -- the `defaultdict` silently re-inserts an empty list. However, this means line 69's `.append()` adds a timestamp to a freshly created list that was just pruned, which is the intended behavior but via an unintended code path. The delete-then-re-access pattern is confusing and fragile.

**Recommendation:** Restructure to avoid the delete-then-re-access:
```python
_rate_store[client_ip] = [t for t in timestamps if t > window]
if len(_rate_store[client_ip]) >= RATE_LIMIT:
    return False
_rate_store[client_ip].append(now)
return True
```

### MEDIUM-07: `request.client` can be None

**File:** `app.py`, line 107
```python
client_ip = request.client.host if request.client else "unknown"
```

Credit: This is handled correctly with a fallback to `"unknown"`.

### MEDIUM-08: Multiple division-by-zero guards are present but inconsistent

**File:** `core/scorer.py`, `api/debrief.py`, `core/simulator.py`

Most division operations check for zero denominators (e.g., `if opp > 0`, `if anchor != 0`). However:

- `api/debrief.py` line 100: `money_left / abs(optimal)` guards with `optimal != 0` -- correct.
- `core/simulator.py` line 454: `state.user_total_concession / abs(anchor)` -- guarded by `if not anchor` on line 452 -- correct.
- `core/scorer.py` line 280: `(total_conc / abs(anchor)) / n_conc` -- guarded by `anchor is None or n_conc == 0` -- correct.

These are all handled. No action needed.

### LOW-03: `api_get_session` sets `status` to `state.persona.name` instead of session status

**File:** `api/routes.py`, line 491
```python
status=state.persona.name,
```

This is a bug, not an error handling issue, but worth noting: the `status` field of `SessionStateResponse` receives the persona's name instead of the session status. This does not cause a crash but returns incorrect data.

---

## 6. Global Exception Handler

### Finding: ABSENT

As noted in CRITICAL-01, there is no global exception handler. FastAPI's default handler returns a plain `{"detail": "Internal Server Error"}` for unhandled exceptions in production, which is acceptable but not controllable. Adding one allows:

- Consistent error response format
- Centralized logging of unhandled errors
- Prevention of stack trace leakage in any configuration
- Custom error tracking integration

---

## 7. Analytics/Feedback Failures Blocking the API

### Finding: CORRECTLY ISOLATED

**File:** `api/routes.py`, lines 75-86

```python
def _track(event_type: str, data: dict | None = None) -> None:
    try:
        get_tracker().track(event_type, data)
    except Exception:
        pass

def _feature(feature_name: str, extra: dict | None = None) -> None:
    try:
        get_tracker().track_feature(feature_name, extra)
    except Exception:
        pass
```

Credit: Both `_track` and `_feature` are wrapped in bare try/except that swallow all errors. This ensures analytics failures never block the main API response. The same pattern is used for user history recording in `api_complete_session` (line 454).

### HIGH-05: Feedback submission (`api_submit_feedback`) is NOT isolated

**File:** `api/routes.py`, lines 737-752

Unlike analytics, the feedback submission endpoint calls `get_collector().submit()` directly without a try/except wrapper. If the JSONL write fails (disk full, permissions), the error propagates to the user as a 500.

The `submit()` method internally catches write errors (line 169 of `feedback.py`), so the risk is limited to the `submit()` method itself throwing before reaching the write (e.g., `TypeError` from bad input processing). Still, for consistency with the analytics pattern, the call should be wrapped.

**Recommendation:** Wrap in try/except like `_track`:
```python
try:
    get_collector().submit(...)
except Exception:
    logger.warning("Failed to store feedback", exc_info=True)
    # Still return success to user -- their feedback intent was received
```

---

## 8. Bare `except:` Clauses

### Finding: No truly bare `except:` (without exception type)

All exception handlers in the codebase use `except Exception:`, not bare `except:`. This is correct -- it avoids catching `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`.

However, there are several `except Exception: pass` patterns that silently swallow errors:

| File | Line | Context |
|------|------|---------|
| `api/routes.py` | 78 | `_track()` -- analytics; acceptable |
| `api/routes.py` | 85 | `_feature()` -- analytics; acceptable |
| `core/store.py` | 69 | `save_sessions()` -- logs at debug; acceptable for fallback |
| `core/store.py` | 74 | tmp file cleanup -- acceptable |
| `core/store.py` | 100 | corrupt file rename -- acceptable |
| `core/store.py` | 135 | `clear_store()` -- acceptable |
| `core/session.py` | 223 | `_persist_all()` -- logs at debug; acceptable |
| `core/session.py` | 237 | `_restore_from_file()` -- logs at debug; acceptable |

These are all deliberate "graceful degradation" patterns for non-critical operations (persistence, analytics). The session store correctly falls back to in-memory operation when file I/O fails.

**Recommendation:** The two in `_track` and `_feature` (routes.py:78, 85) should at minimum log a debug-level message so failures are visible in logs during development.

---

## Additional Findings

### MEDIUM-09: `_check_rate_limit` is not async-safe

**File:** `app.py`, lines 48-70

The rate limiter uses a global `dict` and a global `_last_cleanup` float, mutated inside an `async def` middleware without any lock. In a single-worker uvicorn this is fine (Python GIL), but with multiple workers or if the app switches to an async framework with true concurrency, this would produce data races.

**Recommendation:** For production, use an external rate limiter (Redis, or FastAPI middleware like `slowapi`). For the current MVP, document that this is single-worker only.

### LOW-04: `core/offer_analyzer.py` `analyze_offer()` raises `ValueError` for bad salary but this is never caught at the API layer

**File:** `core/offer_analyzer.py`, lines 408-417

The core `analyze_offer()` function validates `base_salary` bounds and raises `ValueError`. However, the API layer's `api_analyze_offer` in `api/routes.py` calls the wrapper `analyze_offer()` in `api/offer_analyzer.py`, which does not take `base_salary` as a direct parameter (it parses from text). The core function's ValueError guard is unreachable from the API layer. This is dead code, not a bug, but could cause confusion.

---

## Summary of Recommendations (Priority Order)

1. **Add a global exception handler** to FastAPI app (CRITICAL-01)
2. **Fix the rate limiter delete-then-re-access pattern** (CRITICAL-02)
3. **Add try/except to unguarded endpoints** -- at minimum offer analysis, challenges, user history, user patterns, debrief, playbook (HIGH-01)
4. **Wrap feedback submission in try/except** for consistency (HIGH-05)
5. **Stop leaking internal role list in 404 response** (HIGH-02)
6. **Wrap `serve_root()` file read in try/except** (HIGH-04)
7. **Fix the `status` field bug** in `api_get_session` returning persona name (LOW-03)
8. **Add `RequestValidationError` handler** for clean 400 responses on bad Pydantic input
9. **Add logging to `_track` and `_feature`** silent swallowers
10. **Return 201 for feedback creation** (HIGH-03)
