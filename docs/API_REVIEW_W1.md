# DealSim API Quality Review — Week 1

**Reviewer:** API Quality Engineer (automated)
**Date:** 2026-03-19
**Files reviewed:** `src/dealsim_mvp/api/routes.py`, `static/index.html`

---

## 1. Endpoint Error Handling Audit

### 1.1 Sessions

| Endpoint | 404 | 409 | 422 | 500 leak? |
|----------|-----|-----|-----|-----------|
| `POST /sessions` | N/A | No | Pydantic auto | **YES — leaks `str(exc)` in 500 detail** |
| `POST /sessions/{id}/message` | Yes (KeyError) | Yes (ValueError/RuntimeError) | Pydantic auto | Unhandled exceptions propagate raw |
| `POST /sessions/{id}/complete` | Yes (KeyError) | No | Pydantic auto | Unhandled exceptions propagate raw |
| `GET /sessions/{id}` | Yes (KeyError) | No | N/A | Unhandled exceptions propagate raw |

**CRITICAL — `api_create_session` line 354:**
```python
raise HTTPException(status_code=500, detail=str(exc))
```
The bare `str(exc)` can leak internal tracebacks, file paths, and dependency details to the client. Should return a generic message.

**ISSUE — `api_complete_session`:** No 409 for already-completed sessions. If `complete_session()` is called twice, behavior is undefined — could silently re-score or throw an unhandled exception.

**ISSUE — `api_get_session` line 474:** The `status` field is mapped to `state.persona.name` (the opponent's name), NOT the session status. This is almost certainly a bug — the response model says `status: str` but it returns the persona name (e.g., "Sarah Chen") instead of a status like "active" or "completed".

### 1.2 Debrief & Playbook

| Endpoint | 404 | 409 | 422 | 500 leak? |
|----------|-----|-----|-----|-----------|
| `GET /sessions/{id}/debrief` | Yes | No | N/A | Unhandled from `generate_debrief()` |
| `GET /sessions/{id}/playbook` | Yes | No | N/A | Unhandled from `generate_playbook()` |

**ISSUE — `api_get_playbook` line 542:** Calls `complete_session(session_id)` which may have side effects (re-completing an already-completed session). Should instead read the stored scorecard. No 409 if session is still active.

**ISSUE — `api_get_debrief`:** No guard that session is actually completed. Calling debrief on an active session will produce nonsensical results rather than a 409.

### 1.3 Offer Analysis

| Endpoint | 404 | 409 | 422 | 500 leak? |
|----------|-----|-----|-----|-----------|
| `POST /offers/analyze` | N/A | N/A | Pydantic auto | Unhandled from `analyze_offer()` |
| `GET /market-data/{role}/{location}` | Yes (with helpful detail) | N/A | N/A | Clean |

**OK:** Market data endpoint is well-handled — returns available roles on 404.

### 1.4 User Progress

| Endpoint | 404 | 409 | 422 | 500 leak? |
|----------|-----|-----|-----|-----------|
| `GET /users/{id}/history` | **NO** | N/A | N/A | Unhandled |
| `GET /users/{id}/patterns` | **NO** | N/A | N/A | Unhandled |

**ISSUE:** Neither user endpoint validates that the user exists or returns 404. `get_user_history()` and `get_user_patterns()` likely return empty data for unknown users rather than raising KeyError. This is not necessarily wrong but should be documented — a consumer cannot distinguish "user has no history" from "user does not exist."

### 1.5 Challenges

| Endpoint | 404 | 409 | 422 | 500 leak? |
|----------|-----|-----|-----|-----------|
| `GET /challenges/today` | N/A | N/A | N/A | Unhandled |
| `POST /challenges/today/submit` | N/A | N/A | Pydantic auto | Unhandled |

**OK:** These are deterministic — always return a challenge. No 404 needed.

### 1.6 Feedback & Events

| Endpoint | 404 | 409 | 422 | 500 leak? |
|----------|-----|-----|-----|-----------|
| `POST /feedback` | N/A | N/A | Pydantic auto | Unhandled from `get_collector().submit()` |
| `POST /events` | N/A | N/A | 400 for unknown type | Clean |

**ISSUE — `api_submit_feedback`:** No response model defined. Returns bare `{"status": "ok", "message": ...}` dict. Should have a formal response model for OpenAPI docs.

**ISSUE — `api_track_event`:** Same — no response model, returns bare dict.

### 1.7 Tools

| Endpoint | 404 | 409 | 422 | 500 leak? |
|----------|-----|-----|-----|-----------|
| `POST /tools/earnings-calculator` | N/A | N/A | Pydantic auto | Unhandled |
| `POST /tools/audit-email` | N/A | N/A | Pydantic auto | Unhandled |
| `GET /scenarios` | N/A | N/A | N/A | Clean (static data) |

---

## 2. Request/Response Contract Mismatches (Frontend vs API)

### 2.1 CRITICAL — Offer Analyzer: Completely Wrong Endpoint and Payload

**Frontend calls:** `POST /api/analyze-offer`
**API provides:** `POST /api/offers/analyze`

The frontend will get a **404** on every offer analysis attempt. The URL does not match.

**Frontend sends:**
```json
{
  "role": "...",
  "salary": 85000,
  "bonus": 5000,
  "equity": 10000,
  "location": "...",
  "full_text": "..."
}
```

**API expects (`OfferAnalyzeRequest`):**
```json
{
  "offer_text": "...",
  "role": "...",
  "location": "..."
}
```

Field mismatches:
- `full_text` (frontend) vs `offer_text` (API) — **name mismatch**
- `salary`, `bonus`, `equity` — **sent by frontend, not accepted by API** (silently ignored by Pydantic)
- Frontend expects `data.analysis` (a single string) — API returns `components`, `overall_market_position`, `overall_score`, `counter_strategies`, `key_insights` (structured data) — **completely different response shape**

### 2.2 CRITICAL — Negotiation Audit: Completely Wrong Endpoint and Payload

**Frontend calls:** `POST /api/audit-negotiation`
**API provides:** `POST /api/tools/audit-email`

The frontend will get a **404** on every audit attempt. The URL does not match.

**Frontend sends:**
```json
{
  "context": "...",
  "thread_text": "..."
}
```

**API expects (`AuditEmailRequest`):**
```json
{
  "email_text": "..."
}
```

Field mismatches:
- `thread_text` (frontend) vs `email_text` (API) — **name mismatch**
- `context` — **sent by frontend, not accepted by API**
- Frontend expects `data.feedback` (a single string) — API returns `overall_score`, `tone`, `strengths`, `issues`, `suggestions`, `rewrite_hints` (structured data) — **completely different response shape**

### 2.3 CRITICAL — Debrief: Frontend Reads Non-Existent Fields

**Frontend expects:** `data.opponent_thoughts` (array of strings), `data.move_analysis[].grade`, `data.move_analysis[].text`

**API returns (`DebriefResponse`):**
- `opponent_thoughts` does NOT exist. API returns `opponent_target`, `opponent_reservation`, `opponent_pressure`, `hidden_constraints`.
- `move_analysis[].grade` does NOT exist. API returns `move_analysis[].strength`.
- `move_analysis[].text` does NOT exist. API returns `move_analysis[].analysis`.

Result: The "What they were thinking" section will always be empty. Move analysis will show empty text. The debrief page is non-functional.

### 2.4 CRITICAL — Playbook: Frontend Reads Non-Existent Fields

**Frontend expects:** `data.opening_moves`, `data.key_phrases`, `data.rebuttals`, `data.walk_away`

**API returns (`PlaybookResponse`):** `session_id`, `overall_score`, `style_profile`, `strengths`, `weaknesses`, `recommendations` (array of objects), `practice_scenarios`

**Zero field overlap.** The playbook page will display "Not available" for every field.

### 2.5 MINOR — Create Session: Extra Field Sent

**Frontend sends:** `opponent_params` (from tuner UI)
**API accepts (`CreateSessionRequest`):** `scenario_type`, `target_value`, `difficulty`, `context`, `user_id`

`opponent_params` is silently ignored by Pydantic. The opponent tuner UI has no effect.

### 2.6 MINOR — Create Session (Demo): Extra Field Sent

**Frontend sends:** `demo_mode: true`
**API accepts:** No `demo_mode` field. Silently ignored. Demo mode has no server-side distinction.

### 2.7 OK — Verified Working Contracts

These endpoints have correct frontend-to-API alignment:
- `POST /api/sessions` — core fields match (session_id, opponent_name, opponent_role, opening_message)
- `POST /api/sessions/{id}/message` — request (`message`) and response (`opponent_response`, `round_number`, `resolved`) match
- `POST /api/sessions/{id}/complete` — response (`overall_score`, `dimensions`, `top_tips`, `outcome`, `agreed_value`) match the scorecard renderer
- `POST /api/feedback` — request fields match
- `POST /api/events` — request fields match

---

## 3. API Completeness

### 3.1 Frontend Features Missing API Endpoints

| Frontend Feature | Expected Endpoint | Status |
|-----------------|-------------------|--------|
| Offer Analyzer | `POST /api/analyze-offer` | **MISSING** (exists as `/api/offers/analyze`) |
| Negotiation Audit | `POST /api/audit-negotiation` | **MISSING** (exists as `/api/tools/audit-email`) |
| Earnings Calculator | Client-side only | OK — no API call needed (calculated in JS) |
| Daily Challenge | Client-side only | OK — hardcoded in JS, no API call to `/api/challenges/today` |
| Score History | `localStorage` only | OK — no API call needed |

### 3.2 API Endpoints Nothing Calls

| Endpoint | Called By Frontend? | Notes |
|----------|-------------------|-------|
| `POST /api/offers/analyze` | **NO** | Frontend calls wrong URL `/api/analyze-offer` |
| `POST /api/tools/audit-email` | **NO** | Frontend calls wrong URL `/api/audit-negotiation` |
| `POST /api/tools/earnings-calculator` | **NO** | Frontend calculates client-side |
| `GET /api/scenarios` | **NO** | Scenario list is hardcoded in HTML |
| `GET /api/users/{id}/history` | **NO** | Frontend uses localStorage, not server history |
| `GET /api/users/{id}/patterns` | **NO** | Not referenced in frontend |
| `GET /api/challenges/today` | **NO** | Frontend uses hardcoded challenge array |
| `POST /api/challenges/today/submit` | **NO** | Frontend has no submit-to-server logic |
| `GET /api/market-data/{role}/{location}` | **NO** | Not referenced in frontend |

**9 of 17 endpoints are unreachable from the frontend.** Only session CRUD, feedback, events, debrief, and playbook are called — and debrief/playbook have broken contracts.

### 3.3 Frontend Features with No Server Counterpart

| Feature | Implementation | Issue |
|---------|---------------|-------|
| Opponent Tuner | Sends `opponent_params` | Server ignores it — tuner has no effect |
| Demo Mode | Sends `demo_mode: true` | Server ignores it — no demo-specific behavior |
| Daily Challenge | Hardcoded JS array | Server has a richer challenge system (`/api/challenges/today`) but frontend never calls it |

---

## 4. Input Validation Audit

### 4.1 String Fields Missing `max_length`

| Model | Field | Has max_length? | Risk |
|-------|-------|----------------|------|
| `CreateSessionRequest.scenario_type` | No | Low (enum-like) |
| `CreateSessionRequest.difficulty` | No | Low (enum-like) |
| `CreateSessionRequest.context` | **No** | **HIGH** — unbounded string goes to LLM/simulator |
| `CreateSessionRequest.user_id` | **No** | Medium — stored in history |
| `OfferAnalyzeRequest.role` | **No** | Low |
| `OfferAnalyzeRequest.location` | **No** | Low |
| `ChallengeSubmitRequest.user_id` | **No** | Low |
| `ChallengeSubmitRequest.response` | **No max** (has min=5) | **HIGH** — unbounded string submitted for scoring |
| `AuditEmailRequest.email_text` | **No max** (has min=10) | **HIGH** — unbounded string for analysis |

**Good:** `SendMessageRequest.message` has `max_length=2000`. `FeedbackRequest.comment` has `max_length=1000`. `FeedbackRequest.email` has `max_length=200`. `EventRequest.event_type` has `max_length=50`.

### 4.2 Numeric Fields Missing Bounds

| Model | Field | Has bounds? | Risk |
|-------|-------|------------|------|
| `CreateSessionRequest.target_value` | **No min/max** | **MEDIUM** — negative or astronomically large values |
| `FeedbackRequest.rating` | Yes (ge=1, le=5) | OK |
| `EarningsCalcRequest.current_offer` | Yes (gt=0) | OK |
| `EarningsCalcRequest.negotiated_offer` | Yes (gt=0) | OK — but no max |
| `FeedbackRequest.final_score` | **No bounds** | Low (optional) |

### 4.3 Enum-Like Fields Without Validation

| Model | Field | Values in Code | Validated? |
|-------|-------|---------------|-----------|
| `CreateSessionRequest.scenario_type` | "salary", "freelance" | **NO** — any string accepted |
| `CreateSessionRequest.difficulty` | "easy", "medium", "hard" | **NO** — any string accepted |
| `EventRequest.event_type` | Allowlist in handler | **YES** — 400 on unknown |

**ISSUE:** `scenario_type` and `difficulty` should use `Literal["salary", "freelance"]` or `Enum` types. Currently any garbage string is accepted and passed to the simulator.

### 4.4 Optional Fields Handling

- `CreateSessionRequest.user_id` defaults to `""` — OK but empty string is truthy in Python. Line 360 checks `body.user_id or None` which handles it.
- `CreateSessionRequest.context` defaults to `""` — OK.
- `OfferAnalyzeRequest.role` and `location` default to `""` — OK, checked with `bool()` at line 587.
- `FeedbackRequest.final_score` is `Optional[int]` with `default=None` — OK.

---

## 5. Summary of Issues by Severity

### CRITICAL (4)
1. **Offer Analyzer URL mismatch:** Frontend calls `/api/analyze-offer`, API serves `/api/offers/analyze` — feature is broken
2. **Offer Analyzer payload mismatch:** Frontend sends `full_text`/`salary`/`bonus`/`equity`, API expects `offer_text` — even if URL were fixed, request would fail
3. **Audit URL mismatch:** Frontend calls `/api/audit-negotiation`, API serves `/api/tools/audit-email` — feature is broken
4. **Audit payload mismatch:** Frontend sends `thread_text`/`context`, API expects `email_text` — even if URL were fixed, request would fail

### HIGH (4)
5. **Debrief field mismatch:** Frontend reads `opponent_thoughts`, `grade`, `text` — API returns `opponent_target`/`opponent_reservation`/`opponent_pressure`, `strength`, `analysis` — debrief page shows empty data
6. **Playbook field mismatch:** Frontend reads `opening_moves`, `key_phrases`, `rebuttals`, `walk_away` — API returns `style_profile`, `strengths`, `weaknesses`, `recommendations` — playbook page shows "Not available"
7. **Session status bug:** `GET /sessions/{id}` returns persona name as `status` field (line 474) instead of actual session status
8. **500 error leaks internals:** `api_create_session` returns raw `str(exc)` as 500 detail

### MEDIUM (5)
9. **9 of 17 endpoints unreachable:** Over half the API surface is dead code from the frontend's perspective
10. **No max_length on `context`, `response`, `email_text`:** Unbounded strings could cause DoS or excessive LLM token usage
11. **No target_value bounds:** Negative or extreme values accepted
12. **No enum validation on `scenario_type`, `difficulty`:** Invalid values silently accepted
13. **Playbook calls `complete_session()` with side effects:** Re-completes sessions on each playbook request

### LOW (4)
14. **No response models for `/feedback` and `/events`:** Returns bare dicts
15. **`opponent_params` silently ignored:** Tuner UI has no effect
16. **`demo_mode` silently ignored:** No server-side demo behavior
17. **User endpoints don't distinguish "no user" from "no data":** Acceptable but undocumented

---

## 6. Recommended Fixes (Priority Order)

1. **Fix the 4 URL/payload mismatches** (items 1-4) — either update frontend fetch URLs and payloads to match the API, or add route aliases. This blocks two entire features.
2. **Fix debrief and playbook field mapping** (items 5-6) — update frontend JS to read correct API field names.
3. **Fix session status bug** (item 7) — return `state.status.value` not `state.persona.name`.
4. **Sanitize 500 errors** (item 8) — return generic "Internal server error" instead of `str(exc)`.
5. **Add max_length to unbounded string fields** (item 10).
6. **Add Literal/Enum validation for scenario_type and difficulty** (item 12).
7. **Wire up unused endpoints** or document them as future/API-only features (item 9).
