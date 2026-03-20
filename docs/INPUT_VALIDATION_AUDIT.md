# DealSim Input Validation & Injection Prevention Audit

**Date:** 2026-03-19
**Scope:** All Python files in `src/dealsim_mvp/` and `static/index.html`
**Auditor:** Security review (automated)

---

## Executive Summary

The codebase has **solid foundational validation** via Pydantic models and a dedicated `escapeHtml()` function on the frontend. However, there are **12 findings** across 4 severity levels. The most critical issues involve unvalidated path parameters for `user_id`, missing `max_length` on several free-text fields, an HTML injection surface in the admin dashboard, and a rate limiter that can be bypassed via proxy headers.

| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| HIGH     | 4     |
| MEDIUM   | 4     |
| LOW      | 2     |

---

## Finding 1 — CRITICAL: `user_id` Path Parameter Has No Validation

**File:** `src/dealsim_mvp/api/routes.py`, lines 672, 683
**Input path:** `GET /api/users/{user_id}/history`, `GET /api/users/{user_id}/patterns`
**Also:** `POST /api/sessions/{session_id}/complete?user_id=...` (line 424, query param)

**Issue:** `user_id` is a raw `str` path/query parameter with no format validation, no length limit, and no character restriction. It is passed directly to `get_user_history()` and `get_user_patterns()` in `api/analytics.py`, where it is compared against stored records and also written to JSONL files via `record_session_for_user()`.

**Attack vectors:**
- **Memory exhaustion:** A user_id of 10MB would be stored in the JSONL file and loaded into memory on every read.
- **JSONL injection:** While `json.dumps()` handles escaping, an extremely long user_id bloats the data files.
- **Enumeration:** No authentication means any user_id history is publicly accessible.

**Server-side validation:** None.
**Client-side validation:** None (user_id is generated client-side as `localStorage` key).

**Fix:**
```python
# In routes.py, add a validator function:
_USER_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

def _validate_user_id(user_id: str) -> str:
    if not _USER_ID_RE.match(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    return user_id

# Apply to all endpoints accepting user_id
```

---

## Finding 2 — CRITICAL: Rate Limiter Bypass via Proxy Headers

**File:** `src/dealsim_mvp/app.py`, lines 102-113
**Input path:** All HTTP requests (middleware)

**Issue:** The rate limiter uses `request.client.host` for IP identification. Behind a reverse proxy (nginx, Cloudflare, AWS ALB), this will always be the proxy's IP (e.g., `127.0.0.1`), meaning:
1. All users share one rate limit bucket.
2. OR a single attacker behind their own proxy can exhaust the shared limit (DoS for everyone).

Additionally, if the app were to trust `X-Forwarded-For` without validation, an attacker could rotate fake IPs to bypass rate limiting entirely.

**Fix:**
```python
# Use a trusted proxy configuration:
# 1. Accept X-Forwarded-For only from known proxy IPs
# 2. Use the rightmost untrusted IP from the chain
# Or use a library like slowapi that handles this correctly.
```

---

## Finding 3 — HIGH: `scenario_type` and `difficulty` Accept Arbitrary Strings

**File:** `src/dealsim_mvp/api/routes.py`, lines 96-99 (CreateSessionRequest)
**Input path:** `POST /api/sessions` body fields `scenario_type` and `difficulty`

**Issue:** Both fields are declared as `str` with no enum constraint at the API model level. While `generate_persona_for_scenario()` in `persona.py` falls back to defaults for unknown types, the raw values are:
- Written to analytics JSONL files (`scenario_type` in tracking events)
- Passed through without sanitization

The `models.py` mirror adds `max_length=500` for `context` but the **canonical model in routes.py** does not. `scenario_type` and `difficulty` have no `max_length` at all.

**Server-side validation:** Pydantic type check (must be `str`), but no enum or max_length.
**Client-side validation:** HTML `<select>` limits options, but trivially bypassed.

**Fix:**
```python
from typing import Literal

class CreateSessionRequest(BaseModel):
    scenario_type: Literal["salary", "freelance", "rent", "medical_bill",
                           "car_buying", "scope_creep", "raise", "vendor",
                           "counter_offer", "budget_request"] = "salary"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    context: str = Field(default="", max_length=500)
```

---

## Finding 4 — HIGH: `offer_text` Has No `max_length` Constraint

**File:** `src/dealsim_mvp/api/routes.py`, lines 187-193 (OfferAnalyzeRequest)
**Input path:** `POST /api/offers/analyze` body field `offer_text`

**Issue:** `offer_text` has `min_length=5` but **no `max_length`**. The text is processed by multiple regex operations in `api/offer_analyzer.py` (`_parse_offer_components`, lines 395-519). A 10MB input would:
- Consume significant CPU in repeated regex scans
- Be held in memory for the duration of request processing

**Server-side validation:** `min_length=5` only.
**Client-side validation:** `<textarea>` with no maxlength attribute.

**Fix:**
```python
offer_text: str = Field(min_length=5, max_length=5000)
```

---

## Finding 5 — HIGH: `email_text` in Audit Endpoint Has No `max_length`

**File:** `src/dealsim_mvp/api/routes.py`, line 326 (AuditEmailRequest)
**Input path:** `POST /api/tools/audit-email` body field `email_text`

**Issue:** `email_text` has `min_length=10` but no `max_length`. The text is processed by `audit_email()` in `api/offer_analyzer.py` (lines 284-378), which runs multiple keyword searches and regex matches. Additionally, the core `email_audit.py` runs 15+ hedging phrase substring searches and 6 compiled regex patterns. A very large input amplifies all of these.

**Fix:**
```python
email_text: str = Field(min_length=10, max_length=10000)
```

---

## Finding 6 — HIGH: `context` Field Missing `max_length` in Canonical Model

**File:** `src/dealsim_mvp/api/routes.py`, line 99
**Input path:** `POST /api/sessions` body field `context`

**Issue:** The canonical `CreateSessionRequest` in `routes.py` declares `context: str = Field(default="")` with **no `max_length`**. The mirror model in `models.py` has `max_length=500`, but `models.py` is explicitly documented as "not used at runtime" (line 7-8). The `context` value is stored in session state and serialized to the JSON session store file.

**Fix:** Add `max_length=500` to the canonical model in `routes.py`.

---

## Finding 7 — MEDIUM: Admin Dashboard HTML Injection (Stored XSS Risk)

**File:** `src/dealsim_mvp/app.py`, lines 205-267
**Input path:** Admin HTML dashboard at `GET /admin/stats?key=...`

**Issue:** The admin dashboard correctly uses `html_escape()` for `fname`, `comment`, `ts`, and `stype` values (lines 186, 194-196, 203). However, **numeric values** like `stats['total_sessions']`, `stats['completion_rate']`, `stats['average_score']`, `fb['total_feedback']`, and `fb['average_rating']` are interpolated directly into the HTML f-string (lines 224-234) without escaping.

While these are currently derived from `int`/`float` computations and are not directly user-controllable, if the analytics aggregation logic ever changes to include user-supplied strings in these fields, this becomes an XSS vector. The pattern is fragile.

Additionally, `scenario_rows` at line 250 is interpolated with a ternary that could include the raw `scenario_rows` string, but individual values within are escaped at line 203.

**Fix:** Wrap all interpolated values in `html_escape(str(...))` for defense-in-depth, or use a proper template engine (Jinja2).

---

## Finding 8 — MEDIUM: `ChallengeSubmitRequest.response` Has No `max_length`

**File:** `src/dealsim_mvp/api/routes.py`, line 276
**Input path:** `POST /api/challenges/today/submit` body field `response`

**Issue:** The `response` field has `min_length=5` but no `max_length`. The response text is:
1. Processed by multiple regex and keyword searches in `submit_challenge_response()` (`api/analytics.py`, lines 316-377)
2. Written in full to the JSONL submissions file (line 368-375)

A 10MB response would be stored permanently and cause slow reads on every subsequent file parse.

**Fix:**
```python
response: str = Field(min_length=5, max_length=5000)
```

---

## Finding 9 — MEDIUM: `EventRequest.properties` Dict Has No Size Limit

**File:** `src/dealsim_mvp/api/routes.py`, lines 303-305
**Input path:** `POST /api/events` body field `properties`

**Issue:** The `properties` field is an unrestricted `dict`. An attacker can submit a deeply nested or extremely large JSON object (e.g., 50MB) that will be:
1. Deserialized by Pydantic (memory allocation)
2. Serialized to JSONL via `json.dumps()` in the analytics tracker
3. Stored permanently on disk

The `event_type` is validated against an allowlist (line 757-765), which is good, but `properties` is completely unconstrained.

**Fix:**
```python
from pydantic import field_validator

class EventRequest(BaseModel):
    event_type: str = Field(..., max_length=50)
    properties: dict = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def limit_properties_size(cls, v):
        import json
        if len(json.dumps(v, default=str)) > 10000:
            raise ValueError("Properties payload too large (max 10KB)")
        return v
```

---

## Finding 10 — MEDIUM: `role` and `location` Path Parameters Have No Validation

**File:** `src/dealsim_mvp/api/routes.py`, lines 647-648
**Input path:** `GET /api/market-data/{role}/{location}`

**Issue:** `role` and `location` are raw string path parameters with no length or character constraints. They are passed to `get_market_data()` which normalizes them via `_normalize_role()` / `_normalize_location()`. The normalization uses `.lower().strip().replace()` which is safe, but the error response at line 653 reflects the raw `role` and `location` values back:

```python
detail=f"No data for role='{role}', location='{location}'. Available roles: {available}"
```

While FastAPI returns this as JSON (not HTML), if any downstream consumer renders this detail without escaping, it becomes an XSS vector. The reflected values have no length limit.

**Fix:**
```python
def api_get_market_data(role: str, location: str):
    if len(role) > 50 or len(location) > 50:
        raise HTTPException(status_code=400, detail="Invalid role or location")
```

---

## Finding 11 — LOW: `FeedbackRequest.session_id` Not Validated as UUID

**File:** `src/dealsim_mvp/api/routes.py`, line 295
**Input path:** `POST /api/feedback` body field `session_id`

**Issue:** Unlike session endpoints which validate session_id format via `_validate_session_id()`, the feedback endpoint accepts any string as `session_id`. This value is stored in the feedback JSONL file. While not exploitable for injection (JSON serialization handles escaping), it allows junk data.

**Fix:** Add the same UUID4 validation or at minimum a `max_length=36`.

---

## Finding 12 — LOW: In-Memory Session Store Has No Size Limit

**File:** `src/dealsim_mvp/core/session.py`, lines 81, 244-247
**Input path:** `POST /api/sessions` (creates new sessions)

**Issue:** The `_SESSIONS` dict grows without bound. While sessions auto-clean after 1 hour in the file store (`store.py`, line 31), the in-memory dict is only populated on load and never proactively evicted. An attacker creating sessions at 100/minute (within rate limit) would accumulate 6,000 sessions/hour in memory.

Each session holds the full transcript with all user messages, so memory grows proportionally to session count * message count.

**Fix:** Add a max session count with LRU eviction, or proactively evict completed sessions from memory after scoring.

---

## Checklist Results

### 1. eval(), exec(), subprocess calls
**Result:** NONE FOUND. No use of `eval()`, `exec()`, or `subprocess` anywhere in the Python codebase. The frontend uses `document.execCommand('copy')` (line 1786) which is a deprecated but harmless clipboard API call.

### 2. File paths with user-controllable components
**Result:** SAFE. Session IDs are generated server-side via `uuid.uuid4()` (session.py line 294) and are never used in file paths. Data files use fixed paths (`data/events.jsonl`, `data/feedback.jsonl`, etc.). The session store uses a fixed filename (`.dealsim_sessions.json`). No path traversal is possible.

### 3. User input interpolated into HTML without escaping
**Result:** MOSTLY SAFE. The admin dashboard (app.py) uses `html_escape()` for user-derived string values. The frontend `index.html` has a dedicated `escapeHtml()` function (line 1159) used for rendering tips, labels, and opponent names. However, several `innerHTML` assignments in the frontend build HTML strings with `escapeHtml()` applied inconsistently (see Finding 7 notes on the admin side).

### 4. Regex patterns vulnerable to catastrophic backtracking (ReDoS)
**Result:** LOW RISK. The regex patterns in `core/offer_analyzer.py` and `api/offer_analyzer.py` use patterns like `[\d,]+(?:\.\d{1,2})?` and `[A-Za-z\s/&]{2,40}?` which are bounded. The `{2,40}?` lazy quantifier with a character class that includes `\s` inside a pattern that also matches `\s` externally (e.g., line 796) could theoretically cause some backtracking on adversarial input, but the bounded repetition `{2,40}` limits the worst case. The `_MONEY_RE` pattern in `simulator.py` (`\$?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(k)?`) is safe. No catastrophic backtracking patterns found.

### 5. Offer text parser safety against adversarial inputs
**Result:** SAFE WITH CAVEAT. The parser in `api/offer_analyzer.py` (`_parse_offer_components`) uses `re.search()` which stops at the first match and does not process the entire string repeatedly. The core parser in `core/offer_analyzer.py` (`parse_offer_text`) iterates a fixed set of patterns with `break` after first match. Both are safe against adversarial content. **Caveat:** No `max_length` on input (see Finding 4).

### 6. Rate limiter bypass via header manipulation
**Result:** VULNERABLE (see Finding 2). The rate limiter does not account for `X-Forwarded-For` or reverse proxy configurations.

### 7. Memory issues from extremely long inputs
**Result:** VULNERABLE for fields without `max_length` (Findings 4, 5, 6, 8, 9). Pydantic will deserialize and hold arbitrarily large strings in memory.

### 8. Client-side validation
**Result:** PARTIAL.
- HTML `<select>` for scenario_type and difficulty (bypassed trivially)
- `type="number"` on target-value input
- `novalidate` attribute on the form (line 267) explicitly disables HTML5 validation
- No `maxlength` attributes on any `<textarea>` elements
- The `escapeHtml()` function is properly used for rendering dynamic content

---

## Positive Security Controls Already in Place

1. **Session ID validation:** `_validate_session_id()` uses a strict UUID4 regex (routes.py line 29-39). Applied to all session endpoints.
2. **Admin key comparison:** Uses `secrets.compare_digest()` (app.py line 160), preventing timing attacks.
3. **Pydantic models:** All request bodies go through Pydantic with type enforcement.
4. **Event type allowlist:** The `/api/events` endpoint validates `event_type` against a fixed set (routes.py line 757-765).
5. **CORS configuration:** Defaults to localhost-only; configurable via environment variable (app.py lines 87-98).
6. **HTML escaping:** Both server-side (`html_escape`) and client-side (`escapeHtml`) functions exist and are used.
7. **No PII storage by default:** Analytics are privacy-respecting with no cookies.
8. **Feedback comment truncation:** `FeedbackCollector.submit()` truncates comment to 1000 chars and email to 200 chars (feedback.py lines 58-62).
9. **`encodeURIComponent()`:** Frontend properly encodes session IDs in URL paths (e.g., line 1408).
10. **File store atomic writes:** Uses `os.replace()` for atomic file updates (store.py line 68).

---

## Recommended Priority Order

1. **Add `max_length` to all text fields** (Findings 4, 5, 6, 8) -- 15 minutes, prevents memory/disk abuse
2. **Validate `user_id` format** (Finding 1) -- 10 minutes, prevents data pollution and enumeration
3. **Constrain `scenario_type` and `difficulty` to enums** (Finding 3) -- 10 minutes
4. **Add size limit to `EventRequest.properties`** (Finding 9) -- 10 minutes
5. **Fix rate limiter for proxy environments** (Finding 2) -- 30 minutes, deploy-dependent
6. **Add max session count** (Finding 12) -- 20 minutes
7. **Validate `role`/`location` length** (Finding 10) -- 5 minutes
8. **Validate feedback `session_id`** (Finding 11) -- 5 minutes
9. **Harden admin dashboard HTML** (Finding 7) -- 15 minutes, or adopt Jinja2
