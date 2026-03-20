# DealSim Test Plan

Pre-deployment checklist. Every section is a pass/fail gate.

---

## 1. Unit Tests (Backend)

### 1.1 Existing Test Coverage

The following test files exist and cover the core modules:

| Test File | Module Under Test | Status |
|---|---|---|
| `test_api.py` | FastAPI endpoints (health, sessions, feedback) | Exists |
| `test_session.py` | Session lifecycle (create, negotiate, complete, transcript) | Exists |
| `test_simulator.py` | Rule-based engine (offer extraction, move classification, opponent response) | Exists |
| `test_scorer.py` | 6-dimension scoring system | Exists |
| `test_debrief.py` | Debrief generation (core + API layer) | Exists |
| `test_playbook.py` | Playbook generation (core) | Exists |
| `test_offer_analyzer.py` | Offer analysis, text parsing, market data, earnings, email audit | Exists |
| `test_challenges.py` | Daily challenge system (core + API) | Exists |
| `test_integration.py` | Full negotiation flows (5-round, aggressive, passive, deal/no-deal) | Exists |
| `test_tools.py` | Earnings calculator, email audit (core modules) | Exists |
| `test_persona.py` | Persona generation, difficulty adjustment, scenario differentiation | Exists |

### 1.2 API Endpoint Test Checklist

Every endpoint must have at least one happy-path and one error-path test.

**Sessions**

- [ ] `POST /api/sessions` -- creates session, returns 201 with session_id, opponent_name, opening_message
- [ ] `POST /api/sessions` -- default values (scenario_type, difficulty) work
- [ ] `POST /api/sessions` -- returns opening_offer > 0
- [ ] `POST /api/sessions` -- with opponent_params slider overrides
- [ ] `POST /api/sessions/{id}/message` -- returns opponent_response, round_number, session_status
- [ ] `POST /api/sessions/{id}/message` -- 400 for invalid session ID format (non-UUID)
- [ ] `POST /api/sessions/{id}/message` -- 404 for nonexistent UUID session
- [ ] `POST /api/sessions/{id}/message` -- 409 for completed session
- [ ] `POST /api/sessions/{id}/message` -- 422 for empty message (Pydantic min_length=1)
- [ ] `POST /api/sessions/{id}/message` -- message at max_length=2000 boundary
- [ ] `POST /api/sessions/{id}/complete` -- returns scorecard with 6 dimensions, overall_score, outcome
- [ ] `POST /api/sessions/{id}/complete` -- 400 for invalid session ID format
- [ ] `POST /api/sessions/{id}/complete` -- 404 for nonexistent session
- [ ] `POST /api/sessions/{id}/complete` -- with user_id records to history
- [ ] `POST /api/sessions/{id}/complete` -- idempotent on repeated calls
- [ ] `GET /api/sessions/{id}` -- returns session state with transcript
- [ ] `GET /api/sessions/{id}` -- 400 for invalid session ID format
- [ ] `GET /api/sessions/{id}` -- 404 for nonexistent session

**Debrief & Playbook**

- [ ] `GET /api/sessions/{id}/debrief` -- returns debrief with opponent_target, move_analysis, money_left_on_table
- [ ] `GET /api/sessions/{id}/debrief` -- 404 for nonexistent session
- [ ] `GET /api/sessions/{id}/debrief` -- 409 for active (not yet completed) session
- [ ] `GET /api/sessions/{id}/playbook` -- returns playbook with strengths, weaknesses, recommendations
- [ ] `GET /api/sessions/{id}/playbook` -- 404 for nonexistent session

**Offer Analysis**

- [ ] `POST /api/offers/analyze` -- parses offer text, returns components and counter_strategies
- [ ] `POST /api/offers/analyze` -- with role and location enriches market_position
- [ ] `POST /api/offers/analyze` -- 422 for offer_text shorter than min_length=5
- [ ] `GET /api/market-data/{role}/{location}` -- returns percentile data for known role/location
- [ ] `GET /api/market-data/{role}/{location}` -- 404 for unknown role or location

**User Progress**

- [ ] `GET /api/users/{id}/history` -- returns sessions list, average_score, score_trend
- [ ] `GET /api/users/{id}/history` -- for user with no sessions (empty history)
- [ ] `GET /api/users/{id}/patterns` -- returns patterns, style_profile, top_strength
- [ ] `GET /api/users/{id}/patterns` -- for user with no sessions

**Daily Challenges**

- [ ] `GET /api/challenges/today` -- returns challenge with id, title, scoring_criteria
- [ ] `POST /api/challenges/today/submit` -- returns total score and breakdown
- [ ] `POST /api/challenges/today/submit` -- 422 for response shorter than min_length=5

**Feedback & Events**

- [ ] `POST /api/feedback` -- accepts valid feedback, returns status ok
- [ ] `POST /api/feedback` -- 422 for rating outside 1-5 range
- [ ] `POST /api/feedback` -- 422 for missing session_id
- [ ] `POST /api/events` -- accepts known event_type, returns status ok
- [ ] `POST /api/events` -- 400 for unknown event_type

**Tools**

- [ ] `POST /api/tools/earnings-calculator` -- returns difference_annual, difference_career, compounding_note
- [ ] `POST /api/tools/earnings-calculator` -- 422 for current_offer <= 0
- [ ] `POST /api/tools/audit-email` -- returns overall_score, tone, strengths, issues
- [ ] `POST /api/tools/audit-email` -- 422 for email_text shorter than min_length=10

**Utility & System**

- [ ] `GET /api/scenarios` -- returns list of 10 scenario types
- [ ] `GET /health` -- returns status, version, uptime_seconds, active_sessions
- [ ] `GET /api/health` -- alias returns same payload as /health
- [ ] `GET /api/admin/stats` -- 403 without valid admin key
- [ ] `GET /api/admin/stats` -- 503 when DEALSIM_ADMIN_KEY not configured
- [ ] `GET /api/admin/stats` -- returns stats with valid Bearer token

### 1.3 Identified Gaps

Tests that do NOT currently exist and should be written:

- [ ] **`POST /api/sessions` with invalid scenario_type** -- verify fallback behavior
- [ ] **`POST /api/sessions` with negative target_value** -- verify 422
- [ ] **`POST /api/sessions` with opponent_params** -- verify slider overrides apply to persona
- [ ] **`POST /api/sessions/{id}/message` with message at exactly 2000 chars** -- boundary test
- [ ] **`POST /api/sessions/{id}/complete` with user_id** -- verify history recording via API
- [ ] **`GET /api/sessions/{id}/debrief` on active session** -- verify 409 (exists in routes but not in test_api.py)
- [ ] **`GET /api/sessions/{id}/playbook` on nonexistent session** -- verify 404 via API
- [ ] **`POST /api/offers/analyze` with role + location enrichment** -- verify market_position populated
- [ ] **`GET /api/users/{id}/history` and `/patterns`** -- no API-level tests exist at all
- [ ] **`POST /api/events` with each allowed event type** -- verify all 13 types accepted
- [ ] **`POST /api/feedback` with all optional fields** -- email, final_score, scenario_type
- [ ] **`GET /api/admin/stats`** -- no tests for admin endpoints
- [ ] **`GET /admin/stats`** -- HTML dashboard variant
- [ ] **Rate limiter** -- verify 429 after 100 requests in 1 minute
- [ ] **CORS headers** -- verify correct origins returned
- [ ] **Global exception handler** -- verify 500 returns {"detail": "Internal server error"}, no stack leak
- [ ] **`POST /api/sessions` with all 10 scenario types** -- verify each creates a valid session
- [ ] **Store persistence** -- verify session data survives across store operations (core/store.py)
- [ ] **Analytics tracker** -- verify _track and _feature never raise even on internal failure
- [ ] **Monitoring middleware** -- verify access.jsonl written, error tracking captures exceptions

### 1.4 Edge Cases per Endpoint

| Endpoint | Edge Case |
|---|---|
| `POST /sessions` | target_value = 0.01 (near-zero) |
| `POST /sessions` | target_value = 999,999,999 (extreme high) |
| `POST /sessions` | context = 500 chars (max_length boundary) |
| `POST /sessions/{id}/message` | Unicode/emoji in message body |
| `POST /sessions/{id}/message` | XSS payload in message: `<script>alert(1)</script>` |
| `POST /sessions/{id}/message` | SQL injection: `'; DROP TABLE sessions; --` |
| `POST /sessions/{id}/complete` | Complete with zero messages sent |
| `GET /sessions/{id}/debrief` | Debrief after single-message negotiation |
| `POST /offers/analyze` | Offer text with no dollar amounts |
| `POST /offers/analyze` | Offer text with biweekly/monthly pay formats |
| `POST /offers/analyze` | Offer text with EUR/GBP currency symbols |
| `POST /tools/earnings-calculator` | current_offer == negotiated_offer |
| `POST /tools/earnings-calculator` | negotiated_offer < current_offer (took a pay cut) |
| `POST /tools/audit-email` | Email with only emoji |
| `POST /tools/audit-email` | Email in non-English language |
| `POST /challenges/today/submit` | Response with 10,000+ characters |
| `POST /feedback` | rating = 1 and rating = 5 (boundaries) |
| `POST /feedback` | comment at max_length=1000 |
| `POST /events` | properties dict with nested objects |

---

## 2. Integration Tests

### 2.1 Full Negotiation Flow

- [ ] **Happy path**: `POST /sessions` -> 5x `POST /sessions/{id}/message` -> `POST /sessions/{id}/complete` -> `GET /sessions/{id}/debrief` -> `GET /sessions/{id}/playbook`
- [ ] Verify session_id is consistent across all calls
- [ ] Verify transcript grows by 2 after each message (user + opponent)
- [ ] Verify scorecard has 6 dimensions with weights summing to 1.0
- [ ] Verify debrief reveals opponent_target and opponent_reservation
- [ ] Verify playbook includes strengths, weaknesses, and recommendations
- [ ] Verify overall_score is 0-100

### 2.2 Feedback Submission Flow

- [ ] Create session -> send 1 message -> complete -> submit feedback with rating + comment
- [ ] Verify feedback endpoint returns `{"status": "ok"}`
- [ ] Verify feedback appears in admin stats (if admin key set)
- [ ] Submit feedback with all optional fields (email, final_score, scenario_type)

### 2.3 Offer Analysis Flow

- [ ] `POST /offers/analyze` with full offer text including salary, bonus, equity, PTO
- [ ] Verify components list includes each parsed component
- [ ] Verify counter_strategies has conservative, balanced, aggressive
- [ ] Verify market enrichment when role + location provided
- [ ] Follow up with `GET /market-data/software_engineer/san_francisco` and verify consistency

### 2.4 Daily Challenge Flow

- [ ] `GET /challenges/today` -> `POST /challenges/today/submit` with response text
- [ ] Verify challenge id matches between GET and submit response
- [ ] Verify scoring breakdown sums to total
- [ ] Verify total is 0-100
- [ ] Submit same challenge twice (verify no crash, idempotent or additive)

### 2.5 User History Flow

- [ ] Create 3 sessions with user_id -> complete each -> `GET /users/{user_id}/history`
- [ ] Verify total_sessions = 3
- [ ] Verify average_score is between min and max of individual scores
- [ ] `GET /users/{user_id}/patterns` -- verify patterns detected after 3+ sessions

### 2.6 Multi-Session Independence

- [ ] Create 2 sessions simultaneously
- [ ] Send messages to session A, verify session B transcript unchanged
- [ ] Complete session A, verify session B still active and negotiable

### 2.7 Session Lifecycle Guards

- [ ] Cannot send message to completed session (409)
- [ ] Cannot send message to resolved (deal reached) session (409)
- [ ] Debrief unavailable on active session (409)
- [ ] Complete is idempotent (same scorecard on repeated calls)

### 2.8 All 10 Scenario Types

- [ ] salary -- create + 1 message + complete
- [ ] freelance -- create + 1 message + complete
- [ ] rent -- create + 1 message + complete
- [ ] medical_bill -- create + 1 message + complete
- [ ] car_buying -- create + 1 message + complete
- [ ] scope_creep -- create + 1 message + complete
- [ ] raise -- create + 1 message + complete
- [ ] vendor -- create + 1 message + complete
- [ ] counter_offer -- create + 1 message + complete
- [ ] budget_request -- create + 1 message + complete

---

## 3. Frontend Tests (Manual Test Script)

### 3.1 Theme Switching

Three themes: Arena, Coach, Lab. Each has distinct color palette.

- [ ] Default theme is Arena on fresh load (no localStorage)
- [ ] Click theme switcher icon in nav -- expands to show 3 options
- [ ] Switch to Coach theme -- verify background changes to #1a1147, accent to #f5a623
- [ ] Switch to Lab theme -- verify background changes to #0d1117, accent to #58a6ff
- [ ] Switch back to Arena -- verify #0f0f23 background, #f95c5c accent
- [ ] Refresh page -- verify selected theme persists (localStorage `dealsim_theme`)
- [ ] Verify all cards, buttons, inputs, scrollbar update with theme
- [ ] Verify chat bubble colors match theme accent
- [ ] Verify nav bar background and border match theme
- [ ] Open in incognito -- verify Arena default

### 3.2 Gamification Modules

All modules use `window.DealSimGamification` and `localStorage` key `dealsim_profile`.

**Stats Bar (`stats-bar.js`)**
- [ ] Shows XP, level, streak, total sessions on page load
- [ ] Updates XP after completing a negotiation
- [ ] Level number increases when XP threshold crossed
- [ ] Streak increments on consecutive daily play
- [ ] Streak resets after skipping a day

**Radar Chart (`radar-chart.js`)**
- [ ] Renders 6-axis radar chart after score recording
- [ ] Axes labeled: Opening Strategy, Information Gathering, Concession Pattern, BATNA Usage, Emotional Control, Value Creation
- [ ] Chart fills proportionally to dimension scores (0-100)
- [ ] Chart visible in all 3 themes

**Achievements (`achievements.js`)**
- [ ] "First Blood" unlocks after first completed negotiation
- [ ] "High Roller" unlocks on score >= 90
- [ ] "3-Day Streak" unlocks on streak = 3
- [ ] "Diversified" unlocks after playing 5 different scenario types
- [ ] Achievement toast/notification appears on unlock
- [ ] Achievement panel lists all 12 achievements with locked/unlocked state

**Celebrations (`celebrations.js`)**
- [ ] Confetti or animation on deal_reached outcome
- [ ] Level-up celebration animation when XP crosses threshold
- [ ] Achievement unlock visual feedback

**Score Trends (`score-trends.js`)**
- [ ] Line chart shows score history over sessions
- [ ] X-axis shows session number or date
- [ ] Y-axis 0-100
- [ ] Chart updates after each new completed session

**Daily Challenge Card (`daily-challenge-card.js`)**
- [ ] Card appears with today's challenge title and description
- [ ] Submit button sends response to API
- [ ] Score breakdown displayed after submission

**Scenario Cards (`scenario-cards.js`)**
- [ ] All 10 scenario types rendered as selectable cards
- [ ] Each card shows name, description, default target
- [ ] Selecting a card pre-fills the session creation form

**Learning Path (`learning-path.js`)**
- [ ] Progress indicators for each negotiation skill dimension
- [ ] Visual progression (locked/unlocked steps)

**Onboarding (`onboarding.js`)**
- [ ] Onboarding flow shows on first visit (no localStorage profile)
- [ ] Onboarding can be dismissed
- [ ] Does not show on subsequent visits

**Quick Match (`quick-match.js`)**
- [ ] One-click session creation with random scenario and medium difficulty
- [ ] Immediately enters negotiation chat

**Engine Peek (`engine-peek.js`)**
- [ ] Shows simulation engine state during or after negotiation
- [ ] Displays opponent persona traits after completion

### 3.3 Core UI Flows

**Session Creation**
- [ ] Select scenario type from cards
- [ ] Enter target value
- [ ] Choose difficulty (easy/medium/hard)
- [ ] Optional context text
- [ ] Click start -- opponent opening message appears

**Negotiation Chat**
- [ ] User types message in input, presses Enter or Send button
- [ ] Opponent response appears in chat bubble
- [ ] Offer amounts highlighted or extracted
- [ ] Round counter updates
- [ ] Chat scrolls to latest message automatically
- [ ] Send button disabled while waiting for API response

**Completion & Scoring**
- [ ] "End Negotiation" button available during chat
- [ ] Scorecard screen shows overall score and 6 dimensions
- [ ] Each dimension shows score, weight, explanation, tips
- [ ] "View Debrief" button loads debrief section
- [ ] "Get Playbook" button loads playbook section
- [ ] Score recorded to gamification profile

**Debrief Section**
- [ ] Shows opponent's hidden target and reservation price
- [ ] Shows money left on table
- [ ] Move-by-move analysis with strength ratings
- [ ] Key moments highlighted
- [ ] Best move and biggest mistake identified

### 3.4 Keyboard Shortcuts

- [ ] Enter sends message in chat input
- [ ] Escape closes modals/overlays (if any)
- [ ] Tab navigation through form elements follows logical order
- [ ] No focus traps in chat or forms

### 3.5 Mobile Responsive Breakpoints

Test at these widths: 320px, 375px, 414px, 768px, 1024px, 1440px.

- [ ] **320px** -- Chat input and send button usable; no horizontal scroll
- [ ] **375px** -- Scenario cards stack vertically; stats bar condensed
- [ ] **414px** -- Chat bubbles fill width with padding
- [ ] **768px** -- Two-column layout for scenario cards (if applicable)
- [ ] **1024px** -- Side panels visible (if applicable)
- [ ] **1440px** -- Max-width container centered
- [ ] Nav bar collapses to hamburger or stays compact on mobile
- [ ] Theme switcher accessible on mobile
- [ ] Radar chart scales to available width
- [ ] Score trends chart readable on mobile
- [ ] Touch targets >= 44x44px for all interactive elements

### 3.6 Error States

- [ ] **API unreachable** -- show error message, not blank screen; retry button visible
- [ ] **Session creation fails (500)** -- show "Something went wrong" with retry option
- [ ] **Message send fails** -- show error in chat area; allow retry
- [ ] **Invalid session (404)** -- redirect to home or show "Session not found"
- [ ] **Rate limited (429)** -- show "Too many requests, please wait" message
- [ ] **Malformed API response** -- graceful degradation, no JS console errors
- [ ] **localStorage unavailable** -- gamification features degrade gracefully (no crash)
- [ ] **Slow API response (>5s)** -- loading spinner visible; timeout message if >30s

---

## 4. Performance Tests

### 4.1 Page Load Targets

| Metric | Target | How to Measure |
|---|---|---|
| First Contentful Paint | < 1.5s | Lighthouse / Chrome DevTools |
| Largest Contentful Paint | < 2.5s | Lighthouse |
| Time to Interactive | < 3.0s | Lighthouse |
| Total page weight | < 500 KB | Network tab (no external fonts loaded) |
| JS bundle size | < 200 KB combined | Sum of all static/*.js |
| CSS size | < 50 KB | themes.css + Tailwind CDN |

### 4.2 API Response Time Targets

| Endpoint | Target (p95) | Notes |
|---|---|---|
| `GET /health` | < 50ms | No computation |
| `POST /sessions` | < 200ms | Persona generation + opening statement |
| `POST /sessions/{id}/message` | < 300ms | Rule-based simulator, no LLM call |
| `POST /sessions/{id}/complete` | < 200ms | Score calculation |
| `GET /sessions/{id}/debrief` | < 200ms | Debrief generation |
| `GET /sessions/{id}/playbook` | < 200ms | Playbook generation |
| `POST /offers/analyze` | < 300ms | Text parsing + analysis |
| `POST /tools/earnings-calculator` | < 50ms | Pure math |
| `POST /tools/audit-email` | < 200ms | Regex + rule-based analysis |
| `GET /challenges/today` | < 50ms | Lookup only |
| `POST /challenges/today/submit` | < 200ms | Scoring |
| `GET /api/scenarios` | < 50ms | Static list |

### 4.3 Concurrent Load Testing

**Approach**: Use `locust` or `k6` against a staging instance.

```
Scenario: Sustained negotiation load
- Ramp to 50 concurrent users over 2 minutes
- Each user: create session -> 5 messages -> complete -> debrief
- Hold for 5 minutes
- Pass criteria:
  - p95 response time < 500ms for all endpoints
  - Error rate < 0.1%
  - No memory leak (RSS stable within 20% over test duration)
  - Rate limiter correctly returns 429 for users exceeding 100 req/min
```

```
Scenario: Burst traffic
- Spike to 200 concurrent users for 30 seconds
- Verify server recovers gracefully (no crash, no stuck sessions)
- Pass criteria:
  - Server returns 200 or 429 (rate limited) -- never 500
  - Recovery to normal response times within 60 seconds after spike
```

### 4.4 Memory & Storage

- [ ] In-memory session store (`_SESSIONS`) does not grow unbounded -- verify cleanup or TTL
- [ ] Rate limiter store (`_rate_store`) capped at 10,000 IPs with eviction
- [ ] `data/events.jsonl` does not grow unbounded -- verify rotation or size cap
- [ ] `data/feedback.jsonl` does not grow unbounded

---

## 5. Security Tests

### 5.1 XSS Injection

Test each user-input field with these payloads:

```
<script>alert('XSS')</script>
<img src=x onerror=alert(1)>
javascript:alert(1)
"><svg/onload=alert(1)>
{{constructor.constructor('alert(1)')()}}
```

- [ ] `POST /sessions` -- context field with XSS payload
- [ ] `POST /sessions/{id}/message` -- message field with XSS payload
- [ ] `POST /feedback` -- comment field with XSS payload
- [ ] `POST /offers/analyze` -- offer_text with XSS payload
- [ ] `POST /tools/audit-email` -- email_text with XSS payload
- [ ] `POST /challenges/today/submit` -- response field with XSS payload
- [ ] Verify: API responses return raw text (JSON escaped), never rendered as HTML
- [ ] Verify: Frontend renders user/opponent text as textContent, not innerHTML
- [ ] Verify: Admin dashboard HTML-escapes all dynamic values (uses `html_escape`)

### 5.2 API Rate Limiting

- [ ] Send 100 requests within 60 seconds from same IP -- all succeed
- [ ] Send 101st request -- returns 429 with `"Rate limit exceeded"` message
- [ ] Wait 60 seconds, send again -- returns 200 (window expired)
- [ ] `/health` endpoint is exempt from rate limiting
- [ ] X-Forwarded-For header is respected (test with proxy)
- [ ] Rate limiter memory cap at 10,000 IPs -- does not cause OOM

### 5.3 Session Security

- [ ] Session IDs are UUID4 format -- reject non-UUID session IDs with 400
- [ ] Cannot access session created by another user (no auth, but UUID4 is unguessable)
- [ ] Completed sessions cannot be modified (409 on message to completed session)
- [ ] Session data not leaked in error messages (500 returns generic "Internal server error")

### 5.4 Admin Endpoint Protection

- [ ] `GET /api/admin/stats` without Authorization header -- returns 403
- [ ] `GET /api/admin/stats` with wrong key -- returns 403
- [ ] `GET /api/admin/stats` with correct Bearer token -- returns 200
- [ ] `GET /api/admin/stats` with correct raw key (no Bearer prefix) -- returns 200
- [ ] `GET /admin/stats` (HTML variant) -- same auth requirements
- [ ] When `DEALSIM_ADMIN_KEY` env var not set -- returns 503
- [ ] Timing-safe comparison used (secrets.compare_digest) -- no timing attack

### 5.5 Input Validation

- [ ] All Pydantic models enforce min_length, max_length, ge, le constraints
- [ ] session_id validated as UUID4 regex before any DB/store lookup
- [ ] event_type validated against allowlist (13 types) -- rejects arbitrary strings
- [ ] No path traversal possible via session_id or user_id
- [ ] Rating field enforced as integer 1-5 (ge=1, le=5)
- [ ] target_value enforced as positive float (gt=0 in EarningsCalcRequest)

### 5.6 Information Leakage

- [ ] Stack traces never returned to client (global exception handler returns generic 500)
- [ ] Opponent's reservation_price and hidden_constraints not in session state response (only in debrief after completion)
- [ ] `/docs` and `/redoc` accessible (intentional -- verify acceptable for production)
- [ ] No debug mode in production (LOG_LEVEL not set to DEBUG)

### 5.7 CORS

- [ ] When `DEALSIM_CORS_ORIGINS` not set, only localhost origins allowed
- [ ] When set, only specified origins get Access-Control-Allow-Origin
- [ ] Wildcard `*` disables credentials (`allow_credentials=False`)
- [ ] Preflight OPTIONS requests handled correctly

### 5.8 Dependency Security

- [ ] Run `pip audit` or `safety check` against requirements
- [ ] No known CVEs in FastAPI, Pydantic, uvicorn, starlette versions
- [ ] Review `pyproject.toml` for pinned vs unpinned dependencies

---

## 6. Run Commands

```bash
# Run all unit + integration tests
cd /path/to/dealsim && python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=dealsim_mvp --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_api.py -v

# Run security checks
pip audit

# Performance profiling (single endpoint)
python -c "
from dealsim_mvp.app import app
from fastapi.testclient import TestClient
import time
c = TestClient(app)
times = []
for _ in range(100):
    t0 = time.time()
    c.post('/api/sessions', json={'target_value': 100000})
    times.append(time.time() - t0)
print(f'POST /sessions p50={sorted(times)[50]*1000:.0f}ms p95={sorted(times)[95]*1000:.0f}ms')
"
```

---

## 7. Pre-Deployment Gate

All of the following must be true before deploying:

- [ ] `python -m pytest tests/ -v` -- 0 failures
- [ ] Test coverage >= 80% on `dealsim_mvp/` (excluding `__pycache__`)
- [ ] All "Identified Gaps" (section 1.3) either tested or documented as accepted risk
- [ ] Manual frontend walkthrough (section 3) completed on Chrome, Firefox, Safari
- [ ] Mobile test on one real device (iOS or Android)
- [ ] Performance targets (section 4) met on staging
- [ ] XSS test suite (section 5.1) passed
- [ ] Rate limiting verified (section 5.2)
- [ ] Admin endpoints locked (section 5.4)
- [ ] `pip audit` shows 0 known vulnerabilities
- [ ] Health endpoint returns `{"status": "healthy"}` on staging
- [ ] Docker build completes without errors
- [ ] CORS origins configured for production domain
