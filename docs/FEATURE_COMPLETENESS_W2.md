# DealSim Feature Completeness Audit — Week 2

**Auditor:** Product Manager (automated)
**Date:** 2026-03-19
**Files reviewed:** `static/index.html`, `src/dealsim_mvp/api/routes.py`

---

## Summary

| # | Section | Verdict | Blocking Issues |
|---|---------|---------|-----------------|
| 1 | Landing/Setup | **PASS** | — |
| 2 | Instant Demo | **PASS** | — |
| 3 | Chat | **PASS** | — |
| 4 | Scorecard | **PASS** | — |
| 5 | Debrief | **FAIL** | Field name mismatches between frontend expectations and API response |
| 6 | Playbook | **FAIL** | Field name mismatches between frontend expectations and API response |
| 7 | Offer Analyzer | **FAIL** | Wrong endpoint URL; wrong request/response field names |
| 8 | Opponent Tuner | **PASS** | Minor: `opponent_params` sent but not in backend Pydantic model |
| 9 | Score History | **PASS** | — |
| 10 | Daily Challenge | **FAIL** | Frontend ignores the API entirely; uses hardcoded client-side array |
| 11 | Earnings Calculator | **PASS** | Client-side only; API endpoint exists but is unused |
| 12 | Email Audit | **FAIL** | Wrong endpoint URL; wrong request/response field names |

**Pass: 7 / Fail: 5**

---

## Detailed Section Audit

### 1. Landing/Setup — POST /api/sessions

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-landing` section with form, difficulty buttons, context textarea |
| Calls correct endpoint | PASS | `fetch('/api/sessions', { method: 'POST', ... })` |
| Endpoint exists | PASS | `@router.post("/sessions")` returns `CreateSessionResponse` |
| Field consistency | PASS | Frontend sends `scenario_type`, `target_value`, `difficulty`, `context` — all present in `CreateSessionRequest`. Response fields `session_id`, `opponent_name`, `opponent_role`, `opening_message` all consumed correctly. |
| Error handling | PASS | try/catch with `showFormError(err.message)` |
| Loading state | PASS | `setStartLoading(true/false)` toggles spinner and disables button |

**Minor note:** Frontend sends `opponent_params` (from the Tuner) but `CreateSessionRequest` does not declare this field. Pydantic will silently ignore it. The tuner parameters have no effect on session creation.

---

### 2. Instant Demo — POST /api/sessions (demo mode)

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-demo` section with start card, chat area, result card |
| Calls correct endpoint | PASS | Same `POST /api/sessions` with hardcoded demo params |
| Endpoint exists | PASS | Reuses session creation endpoint |
| Field consistency | PASS | Sends `scenario_type`, `target_value`, `difficulty`, `context`. Reads `session_id`, `opening_message`. Also sends `demo_mode: true` which backend silently ignores (harmless). |
| Error handling | PASS | try/catch with system bubble fallback |
| Loading state | PASS | Implicit — chat area shown after response |

---

### 3. Chat — POST /api/sessions/{id}/message

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-chat` with header, message area, input bar |
| Calls correct endpoint | PASS | `fetch('/api/sessions/' + id + '/message', { method: 'POST' })` |
| Endpoint exists | PASS | `@router.post("/sessions/{session_id}/message")` |
| Field consistency | PASS | Sends `{ message: text }` matching `SendMessageRequest.message`. Reads `opponent_response`, `round_number`, `resolved` — all in `SendMessageResponse`. |
| Error handling | PASS | try/catch with `appendSystemMsg('Error: ...')` and connection error fallback |
| Loading state | PASS | Typing indicator dots shown while waiting, removed on response |

---

### 4. Scorecard — POST /api/sessions/{id}/complete

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-scorecard` with overall score circle, dimension bars, coaching tips, action buttons, feedback form |
| Calls correct endpoint | PASS | `fetch('/api/sessions/' + id + '/complete', { method: 'POST' })` |
| Endpoint exists | PASS | `@router.post("/sessions/{session_id}/complete")` |
| Field consistency | PASS | Reads `overall_score`, `dimensions` (array with `.name`, `.score`), `top_tips`, `outcome`, `agreed_value` — all match `CompleteResponse` |
| Error handling | PASS | try/catch with `appendSystemMsg('Scoring error: ...')` |
| Loading state | PASS | Typing indicator shown in chat while scoring |

---

### 5. Debrief — GET /api/sessions/{id}/debrief

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-debrief` with "What They Were Thinking", "Money Left on Table", "Move-by-Move" sections |
| Calls correct endpoint | PASS | `fetch('/api/sessions/' + id + '/debrief', { method: 'GET' })` |
| Endpoint exists | PASS | `@router.get("/sessions/{session_id}/debrief")` returns `DebriefResponse` |
| **Field consistency** | **FAIL** | See mismatches below |
| Error handling | PASS | try/catch with fallback text |
| Loading state | FAIL | No loading/spinner state while fetching debrief |

**Field mismatches (BLOCKING):**

| Frontend expects | Backend returns | Status |
|-----------------|-----------------|--------|
| `data.opponent_thoughts` (array of strings) | `opponent_pressure` (string), `hidden_constraints` (list[str]) | MISMATCH — frontend will get `undefined`, rendering nothing |
| `data.move_analysis[].grade` | `move_analysis[].strength` | MISMATCH — frontend reads `.grade`, backend sends `.strength` |
| `data.move_analysis[].text` | `move_analysis[].analysis` | PARTIAL — frontend tries `.analysis || .text`, so `.analysis` works |
| `data.money_left_on_table` | `money_left_on_table` | MATCH |

**Impact:** "What They Were Thinking" section will always show nothing. Move grades will be blank. The debrief is functionally broken for its most important content.

---

### 6. Playbook — GET /api/sessions/{id}/playbook

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-playbook` with Opening Moves, Key Phrases, Rebuttals, Walk-Away sections |
| Calls correct endpoint | PASS | `fetch('/api/sessions/' + id + '/playbook', { method: 'GET' })` |
| Endpoint exists | PASS | `@router.get("/sessions/{session_id}/playbook")` returns `PlaybookResponse` |
| **Field consistency** | **FAIL** | See mismatches below |
| Error handling | PASS | try/catch with fallback text |
| Loading state | PARTIAL | Shows "Generating..." text, but no spinner |

**Field mismatches (BLOCKING):**

| Frontend expects | Backend returns | Status |
|-----------------|-----------------|--------|
| `data.opening_moves` (string) | Not a field — backend returns `recommendations` (list of objects with `category`, `title`, `description`, `priority`) | MISMATCH |
| `data.key_phrases` (string) | Not a field | MISMATCH |
| `data.rebuttals` (string) | Not a field | MISMATCH |
| `data.walk_away` (string) | Not a field | MISMATCH |
| — | `style_profile` (string) | NOT CONSUMED |
| — | `strengths` (list[str]) | NOT CONSUMED |
| — | `weaknesses` (list[str]) | NOT CONSUMED |
| — | `practice_scenarios` (list[str]) | NOT CONSUMED |

**Impact:** All four playbook sections will render as empty strings or "Not available." The entire playbook page is non-functional. The backend returns structured data (recommendations, strengths, weaknesses, style profile) that the frontend completely ignores. Frontend expects flat strings; backend returns structured objects.

---

### 7. Offer Analyzer — POST /api/offers/analyze

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-offer` with role, salary, bonus, equity, location fields, and offer text area |
| **Calls correct endpoint** | **FAIL** | Frontend calls `POST /api/analyze-offer`; backend defines `POST /api/offers/analyze` |
| Endpoint exists | PASS | `@router.post("/offers/analyze")` exists |
| **Field consistency** | **FAIL** | See mismatches below |
| Error handling | PASS | try/catch with error element |
| Loading state | PASS | Button text changes to "Analyzing...", spinner shown |

**Endpoint URL mismatch (BLOCKING):**
- Frontend: `/api/analyze-offer`
- Backend: `/api/offers/analyze`
- Result: 404 on every request.

**Request field mismatches (BLOCKING):**

| Frontend sends | Backend expects (`OfferAnalyzeRequest`) | Status |
|---------------|----------------------------------------|--------|
| `role` | `role` | MATCH |
| `salary` | — | NOT IN MODEL |
| `bonus` | — | NOT IN MODEL |
| `equity` | — | NOT IN MODEL |
| `location` | `location` | MATCH |
| `full_text` | `offer_text` | MISMATCH — backend requires `offer_text`, frontend sends `full_text` |

**Response field mismatches (BLOCKING):**

| Frontend expects | Backend returns (`OfferAnalyzeResponse`) | Status |
|-----------------|------------------------------------------|--------|
| `data.analysis` (string) | `components`, `overall_market_position`, `overall_score`, `counter_strategies`, `key_insights` | MISMATCH — frontend looks for a single `analysis` string; backend returns structured objects |

**Impact:** Total failure. Wrong URL = 404. Even if URL is fixed, wrong field names on both request and response. The offer analyzer does not work.

---

### 8. Opponent Tuner — Client-side (params sent to session create)

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-tuner` with 6 sliders: Aggressiveness, Flexibility, Patience, Knowledge, Emotion, Budget |
| Calls correct endpoint | N/A | Client-side only; state stored in `state.tunerParams` |
| Endpoint exists | N/A | Params are sent along with session creation |
| Field consistency | PASS (client-side) | Sliders update `state.tunerParams` correctly. Values sent as `opponent_params` in session create body. |
| Error handling | N/A | No API call |
| Loading state | N/A | No API call |

**Minor issue:** `opponent_params` is sent to `POST /api/sessions` but `CreateSessionRequest` does not include this field. Pydantic's default `model_config` will silently discard extra fields. The tuner has zero backend effect. This is a feature gap, not a crash bug.

---

### 9. Score History — localStorage

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-history` with canvas chart, score list, clear button |
| Calls correct endpoint | N/A | Pure localStorage |
| Endpoint exists | N/A | `GET /api/users/{id}/history` exists but is not used |
| Field consistency | PASS | `saveScoreToHistory()` stores `{ date, score, outcome, scenario }` and `renderHistory()` reads the same fields |
| Error handling | PASS | try/catch on localStorage parse |
| Loading state | N/A | Synchronous |

**Note:** Backend has `GET /api/users/{user_id}/history` and `GET /api/users/{user_id}/patterns` endpoints that could provide server-side history. Currently unused. This is acceptable for MVP (localStorage is simpler).

---

### 10. Daily Challenge — GET /api/challenges/today

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-challenge` with title, description, date, accept button |
| **Calls correct endpoint** | **FAIL** | Frontend does NOT call `GET /api/challenges/today`. Uses hardcoded `DAILY_CHALLENGES` array with 7 entries. |
| Endpoint exists | PASS | `@router.get("/challenges/today")` returns `ChallengeResponse` with `id`, `title`, `description`, `scenario_prompt`, `scoring_criteria`, `max_score`, `category`, `date` |
| **Field consistency** | **FAIL** | Frontend uses `challenge.title` and `challenge.desc` from local array. Backend returns `title`, `description` (not `desc`), `scenario_prompt`, `scoring_criteria`. Frontend ignores all the richer backend data. |
| Error handling | N/A | No API call to fail |
| Loading state | N/A | Synchronous from local array |

**Additional:** Backend has `POST /api/challenges/today/submit` for scoring challenge responses with detailed breakdowns. Frontend never calls it. The "Accept Challenge" button merely prefills the main simulation form with the challenge description.

**Impact:** The daily challenge is a degraded client-side stub. It works (shows a challenge, lets you start a sim), but ignores the purpose-built backend with proper scoring, criteria breakdown, and rotating content.

---

### 11. Earnings Calculator — Client-side (POST /api/tools/earnings-calculator unused)

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-calculator` with current salary, negotiated salary, years, raise % inputs, and lifetime/year1/year10/year30 outputs |
| Calls correct endpoint | N/A | Pure client-side `recalcEarnings()` function |
| Endpoint exists | PASS | `POST /api/tools/earnings-calculator` exists, accepts `current_offer` and `negotiated_offer`, returns `difference_annual`, `difference_5yr`, `difference_10yr`, `difference_career`, `compounding_note` |
| Field consistency | PASS (client-side) | All calculation fields are self-consistent within the frontend |
| Error handling | N/A | No API call |
| Loading state | N/A | Instant recalculation on input change |

**Note:** Client-side implementation is actually richer than the API (supports configurable years and raise %). The API endpoint exists but is unused. This is acceptable — client-side calc provides better UX (instant feedback, no latency). Backend endpoint could be used for analytics tracking.

---

### 12. Email Audit — POST /api/tools/audit-email

| Check | Status | Detail |
|-------|--------|--------|
| UI renders | PASS | `sec-audit` with context input, email text area, result area |
| **Calls correct endpoint** | **FAIL** | Frontend calls `POST /api/audit-negotiation`; backend defines `POST /api/tools/audit-email` |
| Endpoint exists | PASS | `@router.post("/tools/audit-email")` exists |
| **Field consistency** | **FAIL** | See mismatches below |
| Error handling | PASS | try/catch with error element |
| Loading state | PASS | Button text changes to "Analyzing...", spinner shown |

**Endpoint URL mismatch (BLOCKING):**
- Frontend: `/api/audit-negotiation`
- Backend: `/api/tools/audit-email`
- Result: 404 on every request.

**Request field mismatches (BLOCKING):**

| Frontend sends | Backend expects (`AuditEmailRequest`) | Status |
|---------------|---------------------------------------|--------|
| `context` | — | NOT IN MODEL |
| `thread_text` | `email_text` | MISMATCH |

**Response field mismatches (BLOCKING):**

| Frontend expects | Backend returns (`AuditEmailResponse`) | Status |
|-----------------|----------------------------------------|--------|
| `data.feedback` (string) | `overall_score`, `tone`, `strengths`, `issues`, `suggestions`, `rewrite_hints` | MISMATCH — frontend looks for single `feedback` string; backend returns structured analysis |

**Impact:** Total failure. Wrong URL = 404. Even if URL is fixed, wrong field names on both request and response.

---

## Critical Path to Fix

### Priority 1 — Broken features (users will see errors)

1. **Offer Analyzer (Section 7):** Fix frontend URL from `/api/analyze-offer` to `/api/offers/analyze`. Rewrite request payload to send `offer_text` instead of `full_text`. Rewrite response handler to consume `components`, `counter_strategies`, `key_insights` instead of a single `analysis` string.

2. **Email Audit (Section 12):** Fix frontend URL from `/api/audit-negotiation` to `/api/tools/audit-email`. Rewrite request payload to send `email_text` instead of `thread_text`. Rewrite response handler to consume `overall_score`, `tone`, `strengths`, `issues`, `suggestions`, `rewrite_hints` instead of a single `feedback` string.

3. **Debrief (Section 5):** Rewrite "What They Were Thinking" to consume `opponent_pressure`, `hidden_constraints`, `opponent_target`, `opponent_reservation` from `DebriefResponse`. Fix move analysis to use `.strength` instead of `.grade`.

4. **Playbook (Section 6):** Rewrite entire playbook renderer to consume `PlaybookResponse` fields: `style_profile`, `strengths`, `weaknesses`, `recommendations[]` (with `.category`, `.title`, `.description`, `.priority`), `practice_scenarios`.

### Priority 2 — Degraded features (work but miss backend value)

5. **Daily Challenge (Section 10):** Replace hardcoded `DAILY_CHALLENGES` array with `fetch('/api/challenges/today')`. Wire "Accept Challenge" to call the API. Add submission flow using `POST /api/challenges/today/submit` to show scored results.

6. **Opponent Tuner (Section 8):** Add `opponent_params` field to `CreateSessionRequest` Pydantic model so tuner values actually reach the session creation logic.

### Priority 3 — Nice to have

7. Add loading spinners to Debrief and Playbook sections.
8. Consider wiring Earnings Calculator to backend for analytics tracking.
9. Consider wiring Score History to `GET /api/users/{id}/history` for cross-device persistence.
