# API Integration Audit

**Date:** 2026-03-19
**Scope:** `src/dealsim_mvp/api/routes.py`, `src/dealsim_mvp/app.py`, `static/index.html`

---

## 1. Backend Endpoint Catalog

All routes are prefixed with `/api` (via `APIRouter(prefix="/api")`).

| # | Method | Path | Request Model | Response Model | Status Code |
|---|--------|------|--------------|----------------|-------------|
| 1 | POST | `/api/sessions` | `CreateSessionRequest` | `CreateSessionResponse` | 201 |
| 2 | POST | `/api/sessions/{id}/message` | `SendMessageRequest` | `SendMessageResponse` | 200 |
| 3 | POST | `/api/sessions/{id}/complete` | None (query param `user_id`) | `CompleteResponse` | 200 |
| 4 | GET | `/api/sessions/{id}` | None | `SessionStateResponse` | 200 |
| 5 | GET | `/api/sessions/{id}/debrief` | None | `DebriefResponse` | 200 |
| 6 | GET | `/api/sessions/{id}/playbook` | None | `PlaybookResponse` | 200 |
| 7 | POST | `/api/offers/analyze` | `OfferAnalyzeRequest` | `OfferAnalyzeResponse` | 200 |
| 8 | GET | `/api/market-data/{role}/{location}` | None | `MarketDataResponse` | 200 |
| 9 | GET | `/api/users/{id}/history` | None | `UserHistoryResponse` | 200 |
| 10 | GET | `/api/users/{id}/patterns` | None | `UserPatternsResponse` | 200 |
| 11 | GET | `/api/challenges/today` | None | `ChallengeResponse` | 200 |
| 12 | POST | `/api/challenges/today/submit` | `ChallengeSubmitRequest` | `ChallengeSubmitResponse` | 200 |
| 13 | POST | `/api/feedback` | `FeedbackRequest` | `{"status":"ok",...}` (untyped) | 200 |
| 14 | POST | `/api/events` | `EventRequest` | `{"status":"ok"}` (untyped) | 200 |
| 15 | GET | `/api/scenarios` | None | `list[ScenarioItem]` | 200 |
| 16 | POST | `/api/tools/earnings-calculator` | `EarningsCalcRequest` | `EarningsCalcResponse` | 200 |
| 17 | POST | `/api/tools/audit-email` | `AuditEmailRequest` | `AuditEmailResponse` | 200 |
| 18 | GET | `/api/admin/stats` | query `key` | untyped dict | 200 |
| 19 | GET | `/admin/stats` | query `key` | HTML | 200 |
| 20 | GET | `/health` | None | `{"status","version"}` | 200 |

---

## 2. Frontend Fetch Call Catalog

| # | Line | Method | URL | Request Body Fields | Response Fields Accessed |
|---|------|--------|-----|---------------------|--------------------------|
| F1 | 1328 | POST | `/api/sessions` | `scenario_type`, `target_value`, `difficulty`, `context`, **`opponent_params`** | `session_id`, `opponent_name`, `opponent_role`, `opening_message` |
| F2 | 1408 | POST | `/api/sessions/{id}/message` | `message` | `opponent_response`, `round_number`, `resolved` |
| F3 | 1470 | POST | `/api/sessions/{id}/complete` | *(empty body)* | `overall_score`, `dimensions`, `top_tips`, `outcome`, `agreed_value` |
| F4 | 1622 | GET | `/api/sessions/{id}/debrief` | None | `money_left_on_table` |
| F5 | 1671 | POST | `/api/feedback` | `session_id`, `rating`, `comment`, `email`, `final_score`, `scenario_type` | *(fire-and-forget)* |
| F6 | 1745 | POST | `/api/feedback` | `session_id`, `rating`, `comment` | *(fire-and-forget)* |
| F7 | 1764 | POST | `/api/events` | `event_type`, `properties` | *(fire-and-forget)* |
| F8 | 1813 | POST | `/api/sessions` | `scenario_type`, `target_value`, `difficulty`, `context`, **`demo_mode`** | `session_id`, `opening_message` |
| F9 | 1875 | POST | `/api/sessions/{id}/message` | `message` | `opponent_response`, `resolved` |
| F10 | 1903 | POST | `/api/sessions/{id}/complete` | *(empty body)* | `overall_score` |
| F11 | 2011 | POST | `/api/offers/analyze` | `offer_text`, `role`, `location` | `overall_score`, `overall_market_position`, `components[]`, `key_insights[]`, `counter_strategies[]` |
| F12 | 2111 | POST | `/api/tools/audit-email` | `email_text` | `overall_score`, `tone`, `strengths[]`, `issues[]`, `suggestions[]`, `rewrite_hints[]` |
| F13 | 2193 | GET | `/api/sessions/{id}/debrief` | None | `opponent_target`, `opponent_reservation`, `opponent_pressure`, `hidden_constraints[]`, `outcome_grade`, `money_left_on_table`, `key_moments[]`, `best_move`, `biggest_mistake`, `move_analysis[]` |
| F14 | 2297 | GET | `/api/sessions/{id}/playbook` | None | `style_profile`, `strengths[]`, `weaknesses[]`, `recommendations[]`, `practice_scenarios[]` |
| F15 | 2535 | GET | `/api/challenges/today` | None | `title`, `description`, `date` |

---

## 3. Fetch-to-Endpoint Mapping & Contract Verification

| Frontend | Backend | URL Match | Request Fields Match | Response Fields Match | Verdict |
|----------|---------|-----------|---------------------|----------------------|---------|
| F1 | #1 | OK | **MISMATCH** | OK | WARN |
| F2 | #2 | OK | OK | OK | PASS |
| F3 | #3 | OK | OK (empty body ok) | OK | PASS |
| F4 | #5 | OK | OK | OK | PASS |
| F5 | #13 | OK | OK | OK | PASS |
| F6 | #13 | OK | OK (subset) | OK | PASS |
| F7 | #14 | OK | OK | OK | **WARN** |
| F8 | #1 | OK | **MISMATCH** | OK | WARN |
| F9 | #2 | OK | OK | OK | PASS |
| F10 | #3 | OK | OK | OK | PASS |
| F11 | #7 | OK | OK | OK | PASS |
| F12 | #17 | OK | OK | OK | PASS |
| F13 | #5 | OK | OK | OK | PASS |
| F14 | #6 | OK | OK | OK | PASS |
| F15 | #11 | OK | OK | OK | PASS |

---

## 4. Findings

### 4.1 Contract Mismatches (request body fields not in Pydantic model)

**ISSUE 1 -- `opponent_params` sent but not in `CreateSessionRequest` (F1, line 1325)**
The frontend sends `opponent_params: state.tunerParams` (an object with slider values) in the POST `/api/sessions` body. The `CreateSessionRequest` Pydantic model has no `opponent_params` field. FastAPI's default behavior with Pydantic v2 is to silently ignore extra fields, so this does not cause an error, but the tuner parameter data is silently discarded and never reaches the session engine.

- **Severity:** Medium -- user-facing feature (difficulty tuner sliders) has no backend effect.
- **Fix:** Either add `opponent_params: dict = Field(default_factory=dict)` to `CreateSessionRequest` and wire it into `create_session()`, or remove the tuner UI from the frontend.

**ISSUE 2 -- `demo_mode` sent but not in `CreateSessionRequest` (F8, line 1821)**
The demo flow sends `demo_mode: true`. Same silent-discard behavior. The backend treats demo sessions identically to normal sessions.

- **Severity:** Low -- cosmetic. If demo mode was intended to behave differently (shorter rounds, no history tracking), the backend has no awareness of it.
- **Fix:** Add `demo_mode: bool = Field(default=False)` if differentiated behavior is desired, or remove the field from the frontend.

### 4.2 Event Type Mismatch (F7)

**ISSUE 3 -- Frontend sends `audit_completed` but backend allowlist expects `email_audited`**
At line 2166, `trackEvent('audit_completed')` fires after a successful email audit. The backend's allowed event types (line 757-763 in routes.py) include `email_audited` but not `audit_completed`. This call will receive a **400 Bad Request** response every time. The error is silently swallowed by the `.catch(() => {})` in `trackEvent`.

- **Severity:** Medium -- analytics data for email audit usage is permanently lost.
- **Fix:** Change `trackEvent('audit_completed')` to `trackEvent('email_audited')` on line 2166 of index.html.

### 4.3 `user_id` Not Passed on Complete Endpoint

**ISSUE 4 -- Frontend never sends `user_id` query param to POST `/api/sessions/{id}/complete`**
The backend accepts an optional `user_id` query parameter to record the session in user history. Neither the main flow (F3, line 1470) nor the demo flow (F10, line 1903) passes this parameter. User history tracking via `record_session_for_user()` never fires.

- **Severity:** Medium -- the user progress features (`/users/{id}/history`, `/users/{id}/patterns`) will never accumulate data from the frontend.
- **Fix:** Pass `?user_id=...` in the complete URL if the user identity is available.

### 4.4 Dead Backend Endpoints (never called from frontend)

| Endpoint | Path | Notes |
|----------|------|-------|
| #4 | `GET /api/sessions/{id}` | Session state retrieval -- not used by frontend |
| #8 | `GET /api/market-data/{role}/{location}` | Market salary data -- not exposed in UI |
| #9 | `GET /api/users/{id}/history` | User history -- not called (and has no data; see Issue 4) |
| #10 | `GET /api/users/{id}/patterns` | User pattern analysis -- not called |
| #12 | `POST /api/challenges/today/submit` | Challenge submission -- frontend starts challenge via sim, never posts to this endpoint |
| #15 | `GET /api/scenarios` | Scenario listing -- frontend hardcodes scenario options in HTML |
| #16 | `POST /api/tools/earnings-calculator` | Earnings calculator -- frontend computes client-side (lines 2358-2391), never calls API |
| #18 | `GET /api/admin/stats` | Admin-only, intentionally not in frontend |
| #19 | `GET /admin/stats` | Admin-only HTML dashboard |
| #20 | `GET /health` | Infrastructure endpoint |

**7 non-admin endpoints are dead** (4, 8, 9, 10, 12, 15, 16). Of these, the most notable:
- The **earnings calculator** has a full backend implementation but the frontend does all math client-side. The two implementations could drift.
- The **challenge submit** endpoint exists but the frontend redirects challenges to the main simulation flow instead of using the dedicated scoring endpoint.
- **Market data** is fetched server-side during offer analysis but never exposed directly to the UI.

### 4.5 Dead Frontend Calls

None found. Every fetch URL in the frontend matches a valid backend endpoint.

### 4.6 Error Handling Assessment

| Fetch | Checks `res.ok`? | Handles error body? | Handles network error (catch)? | User feedback? | Verdict |
|-------|-------------------|--------------------|---------------------------------|----------------|---------|
| F1 (create session) | Yes | Yes (`err.detail`) | Yes (catch) | Yes (form error) | GOOD |
| F2 (send message) | Yes | Yes (`err.detail`) | Yes (catch) | Yes (system msg) | GOOD |
| F3 (complete) | Yes | Yes (`err.detail`) | Yes (catch) | Yes (system msg) | GOOD |
| F4 (debrief/scorecard) | Yes (`r.ok ? ...`) | No | Yes (`.catch(()=>{})`) | Silent fail | ACCEPTABLE (non-critical enrichment) |
| F5 (feedback) | **No** | **No** | Yes (catch + toast) | Partial | WEAK -- no `res.ok` check |
| F6 (modal feedback) | **No** | **No** | Yes (catch + toast) | Partial | WEAK -- no `res.ok` check |
| F7 (events) | **No** | **No** | Yes (`.catch(()=>{})`) | Silent | ACCEPTABLE (fire-and-forget telemetry) |
| F8 (demo create) | Yes | No (generic "Server error") | Yes (catch + toast) | Yes | GOOD |
| F9 (demo message) | Yes | No (generic) | Yes (catch) | Yes | GOOD |
| F10 (demo complete) | Yes | No (generic) | Yes (catch) | Yes | GOOD |
| F11 (offer analyze) | Yes | Yes (`err.detail`) | Yes (catch) | Yes | GOOD |
| F12 (audit email) | Yes | Yes (`err.detail`) | Yes (catch) | Yes | GOOD |
| F13 (debrief detail) | Yes | Graceful fallback | Yes (catch) | Yes | GOOD |
| F14 (playbook) | Yes | Generic "Not available" | Yes (catch) | Yes | GOOD |
| F15 (challenge) | Yes | Fallback to static | Yes (catch + fallback) | Yes | GOOD |

**ISSUE 5 -- Feedback submissions (F5, F6) do not check `res.ok`**
If the server returns 400 (e.g., missing `session_id`), the frontend shows "Thank you" regardless. The user believes feedback was submitted when it was rejected.

- **Severity:** Low-Medium -- feedback could silently fail.
- **Fix:** Add `if (!res.ok) throw new Error(...)` before the success UI transition.

### 4.7 Content-Type & CORS

**Content-Type headers:**
- All POST requests correctly set `Content-Type: application/json`. PASS.
- GET requests at F4/F13/F14 unnecessarily set `Content-Type: application/json`. This is harmless but technically incorrect for requests with no body.

**CORS configuration (`app.py` lines 87-98):**
- Default origins: `http://localhost:3000`, `http://localhost:8000`.
- Configurable via `DEALSIM_CORS_ORIGINS` env var.
- `allow_methods=["*"]`, `allow_headers=["*"]` -- permissive but standard for an API serving its own frontend.
- `allow_credentials` is `True` unless origins contain `"*"` -- correct pattern.
- **No issue found.** Preflight (OPTIONS) requests are handled automatically by FastAPI's CORSMiddleware.

### 4.8 Pydantic Validation Coverage

| Model | Field | Validation | Assessment |
|-------|-------|-----------|------------|
| `CreateSessionRequest.scenario_type` | `str` | No enum constraint | **MISSING** -- should validate against `{"salary","freelance"}` |
| `CreateSessionRequest.difficulty` | `str` | No enum constraint | **MISSING** -- should validate against `{"easy","medium","hard"}` |
| `CreateSessionRequest.target_value` | `float` | No range | **MISSING** -- should have `gt=0` at minimum |
| `CreateSessionRequest.context` | `str` | No max_length | **WEAK** -- could accept unbounded text |
| `CreateSessionRequest.user_id` | `str` | No max_length | **WEAK** |
| `SendMessageRequest.message` | `str` | `min_length=1, max_length=2000` | GOOD |
| `OfferAnalyzeRequest.offer_text` | `str` | `min_length=5`, no max | **WEAK** -- no upper bound |
| `OfferAnalyzeRequest.role` | `str` | No validation | ACCEPTABLE (optional enrichment) |
| `FeedbackRequest.session_id` | `str` | Required, no format check | **WEAK** -- should validate UUID format |
| `FeedbackRequest.rating` | `int` | `ge=1, le=5` | GOOD |
| `FeedbackRequest.comment` | `str` | `max_length=1000` | GOOD |
| `FeedbackRequest.email` | `str` | `max_length=200`, no format | **WEAK** -- no email format validation |
| `EventRequest.event_type` | `str` | `max_length=50` | OK (also validated against allowlist in handler) |
| `ChallengeSubmitRequest.response` | `str` | `min_length=5`, no max | **WEAK** |
| `EarningsCalcRequest.current_offer` | `float` | `gt=0` | GOOD |
| `EarningsCalcRequest.negotiated_offer` | `float` | `gt=0` | GOOD |
| `AuditEmailRequest.email_text` | `str` | `min_length=10`, no max | **WEAK** |

**ISSUE 6 -- `scenario_type` and `difficulty` lack enum validation**
Any string is accepted. A typo like `"salry"` or `"insane"` would pass validation and potentially cause downstream errors or undefined behavior in the session engine.

- **Severity:** Medium.
- **Fix:** Use `Literal["salary", "freelance"]` or a `StrEnum` for `scenario_type`; `Literal["easy", "medium", "hard"]` for `difficulty`.

**ISSUE 7 -- Several text fields have no `max_length`**
`offer_text`, `challenge response`, `email_text`, `context`, and `user_id` can accept arbitrarily large payloads. Combined with the LLM-backed analysis, this could cause expensive API calls or timeouts.

- **Severity:** Low-Medium.
- **Fix:** Add `max_length` constraints (e.g., 5000 for offer_text, 10000 for email_text, 500 for context).

### 4.9 Untyped Response Models

**ISSUE 8 -- `POST /api/feedback` and `POST /api/events` return plain dicts**
These endpoints return `{"status": "ok", ...}` without a `response_model`. This means:
- No automatic OpenAPI schema generation for the response.
- No Pydantic serialization filtering (if internal fields were accidentally added, they would leak).

- **Severity:** Low.
- **Fix:** Create simple response models (e.g., `class OkResponse(BaseModel): status: str; message: str = ""`).

---

## 5. Summary of Issues by Severity

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| 1 | Medium | `opponent_params` silently discarded -- tuner UI has no effect | F1 -> #1 |
| 3 | Medium | `trackEvent('audit_completed')` rejected by backend (expects `email_audited`) | F7 line 2166 |
| 4 | Medium | `user_id` never passed on complete -- user history never populated | F3/F10 -> #3 |
| 6 | Medium | `scenario_type` and `difficulty` lack enum validation | `CreateSessionRequest` |
| 2 | Low | `demo_mode` silently discarded | F8 -> #1 |
| 5 | Low-Med | Feedback POST does not check `res.ok` | F5/F6 |
| 7 | Low-Med | Unbounded `max_length` on several text fields | Multiple models |
| 8 | Low | Feedback/events endpoints lack response models | #13, #14 |

**Dead endpoints (7 non-admin):** `GET /sessions/{id}`, `GET /market-data/{role}/{location}`, `GET /users/{id}/history`, `GET /users/{id}/patterns`, `POST /challenges/today/submit`, `GET /scenarios`, `POST /tools/earnings-calculator`.

**Dead frontend calls:** None.

**Overall assessment:** The core simulation loop (create -> message -> complete -> debrief -> playbook) is correctly wired. The main gaps are in the peripheral feature integration (user history, challenge submit, earnings calculator) and validation strictness. The event tracking mismatch (`audit_completed` vs `email_audited`) is a silent data loss bug that should be fixed immediately.
