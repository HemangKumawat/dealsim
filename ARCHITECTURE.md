# DealSim — Full Product Architecture

> "DealSim = Offer Analysis (the product) + Simulation (the premium upsell) + Data Flywheel (the moat)"

---

## Current State (MVP)

**Total: 2,159 lines Python + 789 lines HTML = ~2,950 lines**

```
src/dealsim_mvp/
├── __init__.py                    # version string
├── app.py                         # 206 LOC — FastAPI factory, CORS, rate limiter, admin dashboard
├── api/
│   ├── __init__.py
│   ├── models.py                  # 119 LOC — Pydantic request/response models (partially unused)
│   └── routes.py                  # 224 LOC — 6 endpoints (sessions CRUD, feedback, events)
├── core/
│   ├── __init__.py
│   ├── analytics.py               #  80 LOC — JSONL append/read for events + feedback
│   ├── persona.py                 # 159 LOC — NegotiationPersona dataclass, 3 templates
│   ├── scorer.py                  # 454 LOC — 6-dimension scorer with coaching tips
│   ├── session.py                 # 248 LOC — session lifecycle, in-memory store + JSON persistence
│   └── simulator.py               # 669 LOC — rule-based engine (5 styles x 3 pressure levels)
static/
└── index.html                     # 789 LOC — single-file HTML/CSS/JS chat UI (Tailwind CDN)
tests/
├── conftest.py
├── test_api.py
├── test_integration.py
├── test_persona.py
└── test_scorer.py
```

### Existing API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/sessions` | Create new negotiation session |
| POST | `/api/sessions/{id}/message` | Send user message, get opponent response |
| POST | `/api/sessions/{id}/complete` | End session, generate scorecard |
| GET | `/api/sessions/{id}` | Get session state + transcript |
| POST | `/api/feedback` | Submit post-sim feedback |
| POST | `/api/events` | Track analytics event |
| GET | `/health` | Health check |
| GET | `/admin/stats` | Admin dashboard (key-protected) |

---

## Target File Structure

```
src/dealsim_mvp/
├── __init__.py
├── app.py                              # MODIFY — mount new routers, add middleware
│
├── api/
│   ├── __init__.py
│   ├── models.py                       # MODIFY — add models for all new endpoints
│   ├── routes.py                       # MODIFY — simulation endpoints only
│   ├── routes_analyzer.py              # NEW — offer analysis, counter-offer, playbook
│   ├── routes_debrief.py               # NEW — debrief, money-left, scorecard PNG
│   ├── routes_challenge.py             # NEW — daily challenge, score history
│   ├── routes_audit.py                 # NEW — email audit, lifetime calculator
│   └── middleware.py                   # NEW — security middleware (XSS, session eviction)
│
├── core/
│   ├── __init__.py
│   ├── analytics.py                    # MODIFY — add feature usage tracking
│   ├── persona.py                      # MODIFY — add 5 new scenario templates, expose tuning
│   ├── scorer.py                       # MODIFY — add money-left calculation, pattern detection
│   ├── session.py                      # MODIFY — persistence upgrade, history tracking
│   ├── simulator.py                    # MODIFY — difficulty progression, hidden state tracking
│   ├── analyzer.py                     # NEW — offer parsing, market position scoring
│   ├── counter_offer.py               # NEW — 3-strategy counter-offer generator
│   ├── playbook.py                     # NEW — printable cheat sheet generator
│   ├── debrief.py                      # NEW — opponent hidden state reveal engine
│   ├── scorecard_image.py             # NEW — PNG scorecard generation
│   ├── challenge.py                    # NEW — daily challenge engine
│   ├── patterns.py                     # NEW — cross-session pattern recognition
│   ├── audit.py                        # NEW — email negotiation auditor
│   └── scenarios.py                    # NEW — scenario registry (all 7 scenarios)
│
├── data/
│   ├── market_ranges.json              # NEW — salary/rate benchmarks by role/location
│   ├── scenarios.json                  # NEW — scenario definitions for all 7 types
│   └── challenge_bank.json             # NEW — daily challenge pool
│
static/
├── index.html                          # MODIFY — add tab navigation, new panels
├── analyzer.html                       # NEW — standalone offer analyzer page
├── scorecard.html                      # NEW — shareable scorecard view
└── js/
    ├── app.js                          # NEW — extracted from index.html, main app logic
    ├── analyzer.js                     # NEW — offer analyzer UI logic
    ├── charts.js                       # NEW — score history charts (Canvas API)
    └── share.js                        # NEW — scorecard sharing logic

tests/
├── conftest.py                         # MODIFY — add fixtures for new modules
├── test_api.py
├── test_integration.py
├── test_persona.py
├── test_scorer.py
├── test_analyzer.py                    # NEW
├── test_counter_offer.py              # NEW
├── test_playbook.py                    # NEW
├── test_debrief.py                     # NEW
├── test_scorecard_image.py            # NEW
├── test_challenge.py                   # NEW
├── test_patterns.py                    # NEW
├── test_audit.py                       # NEW
└── test_middleware.py                  # NEW
```

---

## Phase 1: Critical Path (Build First)

### Feature 1: "What They Were Thinking" Debrief

Post-simulation reveal of opponent's hidden state — their reservation price, hidden constraints, and internal reasoning at each turn.

**File:** `src/dealsim_mvp/core/debrief.py` (~120 LOC)

```
Dependencies: core/simulator.py (NegotiationState, Turn), core/persona.py (NegotiationPersona)
```

**What it does:**
- Takes a completed NegotiationState and generates a turn-by-turn "opponent inner monologue"
- Reveals: reservation_price, hidden_constraints, how close the user was to triggering acceptance at each turn
- Calculates "pressure felt" at each turn based on BATNA signals and concession patterns

**API Endpoint:**
- `GET /api/sessions/{id}/debrief` — returns debrief object with hidden state + per-turn analysis

**Response shape:**
```python
{
    "opponent_reservation_price": float,
    "opponent_hidden_constraints": list[str],
    "turns": [
        {
            "turn_number": int,
            "opponent_internal_state": str,   # "Was worried you'd walk away"
            "distance_to_deal": float,        # how far from acceptance threshold
            "pressure_felt": float,           # 0-1, based on user's moves
        }
    ],
    "key_moments": [str],                     # "Turn 3: your BATNA signal shifted power"
}
```

**Frontend:** New "Debrief" tab on the results screen. Expandable turn-by-turn view.

**Estimated LOC:** 120 (core) + 30 (route) + 20 (models) + 80 (frontend) + 60 (tests) = **310 total**

---

### Feature 2: "Money Left on Table" Calculation

Shows the gap between what the user achieved and what was theoretically achievable given the opponent's hidden reservation price.

**File:** `src/dealsim_mvp/core/scorer.py` (add function, ~60 LOC)

```
Dependencies: core/simulator.py (NegotiationState), core/persona.py (NegotiationPersona)
```

**What it does:**
- `calculate_money_left(state: NegotiationState) -> MoneyLeftResult`
- Compares agreed_value vs reservation_price
- Computes: absolute gap, percentage gap, qualitative rating ("You captured 87% of available value")

**API Endpoint:**
- Included in the debrief response (same `GET /api/sessions/{id}/debrief`)
- Also included in the `POST /api/sessions/{id}/complete` response (add field)

**Response fields added to debrief:**
```python
{
    "money_left_on_table": float,         # absolute gap
    "value_captured_pct": float,          # 0-100
    "rating": str,                        # "Excellent" / "Good" / "Room to improve"
    "best_possible_outcome": float,       # opponent's reservation price
}
```

**Frontend:** Prominent metric on results screen — large number with color coding.

**Estimated LOC:** 60 (core addition) + 15 (route) + 15 (models) + 40 (frontend) = **130 total**

---

### Feature 3: Shareable Score Card (PNG Generation)

Generate a branded PNG image of the scorecard that users can share on social media or save.

**File:** `src/dealsim_mvp/core/scorecard_image.py` (~180 LOC)

```
Dependencies: core/scorer.py (Scorecard), Pillow (new dependency)
New dependency: Pillow>=10.0
```

**What it does:**
- Takes a Scorecard and renders it as a 1200x630 PNG (OG image dimensions)
- Layout: DealSim branding, overall score (large), 6 dimension bars, scenario info, top tip
- Uses Pillow for image generation — no browser/headless Chrome required

**API Endpoint:**
- `GET /api/sessions/{id}/scorecard.png` — returns image/png response

**Frontend:**
- "Share" button on results screen
- Downloads PNG or copies share URL
- New page `static/scorecard.html` for link-shared scorecards (loads score data, shows card)

**Estimated LOC:** 180 (core) + 25 (route) + 50 (frontend) + 80 (tests) = **335 total**

---

### Feature 4: Session Persistence (File-Based JSON Store)

Upgrade from the current in-memory store with lightweight index to full session persistence including transcript recovery.

**File:** `src/dealsim_mvp/core/session.py` (modify, ~80 LOC added)

```
Dependencies: none new — uses stdlib json, pathlib
```

**What it does:**
- Full session serialization to `{DATA_DIR}/sessions/{session_id}.json`
- Stores: persona config, full transcript, state snapshots, scorecard
- Session recovery on server restart: load from disk if not in memory
- Auto-cleanup: sessions older than 7 days are pruned on startup
- Session listing endpoint returns persisted sessions too

**API Endpoint changes:**
- `GET /api/sessions/{id}` now recovers from disk if not in memory
- `GET /api/sessions` (new) — list all sessions for score history

**Frontend:** Score history screen (Phase 2) depends on this.

**Estimated LOC:** 80 (core modifications) + 15 (route) + 50 (tests) = **145 total**

---

### Feature 5: Security Middleware

Rate limiting hardening, XSS sanitization, session eviction for abandoned sessions, input validation.

**File:** `src/dealsim_mvp/api/middleware.py` (~110 LOC)

```
Dependencies: app.py (mount middleware), stdlib (html, re)
```

**What it does:**
- XSS sanitization: strip HTML tags from all string inputs via middleware
- Enhanced rate limiting: per-endpoint limits (stricter on session creation)
- Session eviction: ACTIVE sessions with no activity for 30 minutes auto-complete
- Request size limiting: reject bodies > 10KB
- Security headers: X-Content-Type-Options, X-Frame-Options, CSP

**API Endpoint changes:**
- Middleware wraps all routes — no new endpoints
- Modify `app.py` to mount the middleware stack

**Frontend:** No changes.

**Estimated LOC:** 110 (middleware) + 30 (app.py mods) + 60 (tests) = **200 total**

---

### Feature 6: Offer Analyzer (New Module)

The core product differentiator. Paste any offer (salary, freelance rate, rent amount) and get instant market positioning.

**File:** `src/dealsim_mvp/core/analyzer.py` (~200 LOC)

```
Dependencies: data/market_ranges.json (new static data file)
```

**What it does:**
- `analyze_offer(offer_type, amount, role, location, experience) -> OfferAnalysis`
- Parses offer details from free text or structured input
- Compares against built-in market ranges (P25/P50/P75/P90 benchmarks)
- Returns: percentile position, strength rating, key factors, red flags
- Market data is bundled as JSON (no external API needed for MVP)

**Data file:** `src/dealsim_mvp/data/market_ranges.json` (~150 LOC)
- Covers: software engineer, PM, designer, data scientist, marketing (x 3 experience levels x 4 regions)
- Freelance: web dev, design, copywriting, consulting (x 3 tiers)

**API Endpoint:**
- `POST /api/analyze` — accepts offer details, returns analysis

**Request:**
```python
{
    "offer_type": "salary" | "freelance" | "rent",
    "amount": float,
    "role": str,                    # optional
    "location": str,                # optional
    "experience_years": int,        # optional
    "raw_text": str,                # optional — parse from pasted text
}
```

**Response:**
```python
{
    "percentile": int,              # 0-100, where this falls in market
    "rating": str,                  # "Below Market" / "Market Rate" / "Above Market" / "Strong"
    "market_range": {"p25": float, "p50": float, "p75": float, "p90": float},
    "factors": [str],               # "Location premium for SF: +15%"
    "red_flags": [str],             # "No equity mentioned — common in startups"
    "recommendation": str,          # "You have room to negotiate ~12% higher"
}
```

**Frontend:**
- New page `static/analyzer.html` — standalone tool (separate from simulation)
- Also accessible as a panel in the main app via tab navigation
- Input: paste offer text OR fill structured form
- Output: visual percentile gauge, color-coded rating, factor breakdown

**Estimated LOC:** 200 (core) + 150 (data) + 40 (route) + 25 (models) + 200 (frontend) + 80 (tests) = **695 total**

---

### Feature 7: Counter-Offer Generator

Given an offer analysis, generate 3 counter-offer strategies with specific language.

**File:** `src/dealsim_mvp/core/counter_offer.py` (~160 LOC)

```
Dependencies: core/analyzer.py (OfferAnalysis)
```

**What it does:**
- `generate_counters(analysis: OfferAnalysis, user_preferences: dict) -> list[CounterStrategy]`
- Three strategies:
  1. **Conservative** — aim for P50-P60, low risk, collaborative tone
  2. **Assertive** — aim for P70-P80, moderate risk, data-backed justification
  3. **Aggressive** — aim for P85+, higher risk, BATNA-leveraged
- Each strategy includes: target number, opening number, script (2-3 sentences to say), rationale

**API Endpoint:**
- `POST /api/counter-offer` — accepts analysis ID or raw offer, returns 3 strategies

**Response:**
```python
{
    "strategies": [
        {
            "name": "Conservative",
            "target": float,
            "opening_ask": float,
            "risk_level": "low" | "medium" | "high",
            "script": str,          # exact words to say/write
            "rationale": str,       # why this works
        }
    ]
}
```

**Frontend:** Displayed below offer analysis. Each strategy is a card with copy-to-clipboard script.

**Estimated LOC:** 160 (core) + 30 (route) + 20 (models) + 80 (frontend) + 60 (tests) = **350 total**

---

### Feature 8: Playbook Generator

Generate a printable negotiation cheat sheet customized to the user's specific situation.

**File:** `src/dealsim_mvp/core/playbook.py` (~180 LOC)

```
Dependencies: core/analyzer.py (OfferAnalysis), core/counter_offer.py (CounterStrategy)
```

**What it does:**
- `generate_playbook(analysis, counters, user_context) -> Playbook`
- Sections: Your Position, Market Data Summary, 3 Counter Strategies, Key Phrases to Use, Phrases to Avoid, BATNA Preparation Checklist, Red Flags to Watch For
- Output as structured data (frontend renders it) and as plain text (for printing/copy)

**API Endpoint:**
- `POST /api/playbook` — accepts analysis + preferences, returns structured playbook

**Response:**
```python
{
    "title": str,
    "sections": [
        {
            "heading": str,
            "content": str | list[str],
            "type": "text" | "checklist" | "table" | "script",
        }
    ],
    "print_text": str,              # plain text version for copy/print
}
```

**Frontend:** Styled printable view with "Print" and "Copy to Clipboard" buttons.

**Estimated LOC:** 180 (core) + 30 (route) + 20 (models) + 120 (frontend) + 60 (tests) = **410 total**

---

### Phase 1 Summary

| # | Feature | New Files | Modified Files | LOC |
|---|---------|-----------|---------------|-----|
| 1 | Debrief | core/debrief.py, routes_debrief.py | — | 310 |
| 2 | Money Left | — | core/scorer.py, routes_debrief.py | 130 |
| 3 | Scorecard PNG | core/scorecard_image.py | pyproject.toml (Pillow) | 335 |
| 4 | Session Persist | — | core/session.py, routes.py | 145 |
| 5 | Security Middleware | api/middleware.py | app.py | 200 |
| 6 | Offer Analyzer | core/analyzer.py, routes_analyzer.py, data/market_ranges.json | — | 695 |
| 7 | Counter-Offer | core/counter_offer.py | routes_analyzer.py | 350 |
| 8 | Playbook | core/playbook.py | routes_analyzer.py | 410 |

**Phase 1 total: ~2,575 LOC across 8 new files + 6 modified files**

---

## Phase 2: Retention Features (Build Second)

### Feature 9: Opponent Tuning Sliders

Expose persona parameters to the UI so users can customize their training opponent.

**File:** `src/dealsim_mvp/core/persona.py` (modify, ~40 LOC added)

```
Dependencies: core/persona.py (NegotiationPersona)
```

**What it does:**
- New function: `create_custom_persona(base_template, overrides) -> NegotiationPersona`
- Overridable params: style (dropdown), pressure (dropdown), patience (0-1 slider), transparency (0-1 slider), budget_tightness (0-1 slider maps to reservation_price adjustment)

**API Endpoint changes:**
- Modify `POST /api/sessions` to accept optional `persona_overrides` dict

**Frontend:** Collapsible "Customize Opponent" panel in session setup. 5 sliders/dropdowns.

**Estimated LOC:** 40 (core) + 15 (route mod) + 10 (models) + 100 (frontend) = **165 total**

---

### Feature 10: Difficulty Progression

Structured difficulty levels with clear behavioral differences.

**File:** `src/dealsim_mvp/core/simulator.py` (modify, ~50 LOC added) + `core/persona.py` (modify, ~30 LOC)

```
Dependencies: core/persona.py, core/simulator.py
```

**What it does:**
- 4 levels: Easy (transparent, patient), Medium (current default), Hard (competitive, impatient, hides info), Expert (adversarial, uses pressure tactics, tight reservation)
- Each level adjusts: style distribution, pressure, patience, transparency, reservation_price tightness, max_turns before walkaway
- Expert adds new opponent behaviors: deadline pressure, take-it-or-leave-it ultimatums

**API Endpoint changes:**
- Modify `POST /api/sessions` — difficulty now accepts "easy" | "medium" | "hard" | "expert"

**Frontend:** 4-button difficulty selector with descriptions. Current difficulty shown during sim.

**Estimated LOC:** 80 (core) + 10 (route) + 80 (frontend) = **170 total**

---

### Feature 11: Score History + Improvement Tracker

Track scores across sessions and show improvement trends.

**File:** `src/dealsim_mvp/core/session.py` (modify, ~40 LOC) + `src/dealsim_mvp/api/routes.py` (modify, ~30 LOC)

```
Dependencies: core/session.py (persistence), core/scorer.py (Scorecard)
```

**What it does:**
- `get_score_history() -> list[ScoreHistoryEntry]` — reads all completed sessions from disk
- Returns: date, scenario, difficulty, overall score, 6 dimension scores, outcome
- Computes: running average, best score, streak info, dimension-level trends

**API Endpoint:**
- `GET /api/score-history` — returns ordered list of past scores with trend data

**Frontend:** New "History" tab. Line chart (Canvas API) showing score over time. Dimension breakdown table. Personal bests highlighted.

**Estimated LOC:** 40 (core) + 30 (route) + 20 (models) + 150 (frontend js/charts) + 40 (tests) = **280 total**

---

### Feature 12: Pattern Recognition

Cross-session behavioral analysis — "you always cave on equity," "you never anchor first."

**File:** `src/dealsim_mvp/core/patterns.py` (~200 LOC)

```
Dependencies: core/session.py (score history), core/simulator.py (MoveType, Turn)
```

**What it does:**
- `detect_patterns(sessions: list[NegotiationState]) -> list[Pattern]`
- Patterns detected:
  - Anchoring: "You anchor first in only 30% of sessions"
  - Concession speed: "Your average first concession is 8% — too large"
  - BATNA usage: "You never mention alternatives"
  - Topic avoidance: "You never bring up equity or benefits"
  - Emotional triggers: "You concede more after pressure moves"
- Each pattern has: description, frequency, severity (info/warning/critical), specific tip

**API Endpoint:**
- `GET /api/patterns` — returns detected patterns across all completed sessions

**Frontend:** "Insights" section on the History tab. Each pattern is a card with severity color.

**Estimated LOC:** 200 (core) + 25 (route) + 15 (models) + 80 (frontend) + 80 (tests) = **400 total**

---

### Feature 13: Daily Challenge

3-minute micro-negotiation with a daily rotating scenario. One attempt per day, leaderboard potential.

**File:** `src/dealsim_mvp/core/challenge.py` (~150 LOC)

```
Dependencies: core/simulator.py, core/persona.py, core/scorer.py, data/challenge_bank.json
```

**What it does:**
- `get_daily_challenge() -> ChallengeConfig` — deterministic daily scenario (hash of date)
- Challenge = compressed scenario: 3-turn max, specific constraint (e.g., "negotiate without using a number"), scored on a single dimension
- `score_challenge(state) -> ChallengeResult` — special scoring for the constraint

**Data file:** `src/dealsim_mvp/data/challenge_bank.json` (~100 LOC)
- 30 challenge templates rotating monthly

**API Endpoints:**
- `GET /api/challenge/today` — get today's challenge config
- `POST /api/challenge/start` — start challenge session (special 3-turn session)
- `POST /api/challenge/{id}/complete` — score and return result

**Frontend:** "Daily Challenge" card on home screen. Timer, constraint display, compressed chat UI.

**Estimated LOC:** 150 (core) + 100 (data) + 40 (routes) + 20 (models) + 120 (frontend) + 60 (tests) = **490 total**

---

### Feature 14: Additional Scenarios

5 new negotiation types beyond salary and freelance.

**File:** `src/dealsim_mvp/core/scenarios.py` (~180 LOC) + `src/dealsim_mvp/core/persona.py` (modify, ~100 LOC)

```
Dependencies: core/persona.py (NegotiationPersona, templates)
```

**New scenarios with persona templates:**

1. **Rent Negotiation** — tenant vs landlord, involves lease terms, maintenance, move-in date
2. **Medical Bill** — patient vs billing department, involves payment plans, itemization, financial hardship
3. **Car Purchase** — buyer vs dealer, involves trade-in, financing, add-ons
4. **Freelance Scope** — freelancer vs client on scope creep, involves timeline, deliverables, revision limits
5. **Raise Request** — employee vs manager (not hiring — retention), involves performance data, market comps, timeline

Each scenario defines: 2 persona templates, scenario-specific vocabulary, relevant package terms, appropriate market ranges.

**Data file:** `src/dealsim_mvp/data/scenarios.json` (~200 LOC)

**API Endpoint changes:**
- Modify `POST /api/sessions` — scenario_type now accepts: "salary", "freelance", "rent", "medical", "car", "freelance_scope", "raise"

**Frontend:** Scenario picker with icons and descriptions on session setup screen.

**Estimated LOC:** 180 (scenarios.py) + 100 (persona.py additions) + 200 (data) + 15 (route mod) + 80 (frontend) + 60 (tests) = **635 total**

---

### Phase 2 Summary

| # | Feature | New Files | Modified Files | LOC |
|---|---------|-----------|---------------|-----|
| 9 | Opponent Tuning | — | persona.py, routes.py, models.py | 165 |
| 10 | Difficulty | — | simulator.py, persona.py | 170 |
| 11 | Score History | — | session.py, routes.py | 280 |
| 12 | Pattern Recognition | core/patterns.py | — | 400 |
| 13 | Daily Challenge | core/challenge.py, data/challenge_bank.json, routes_challenge.py | — | 490 |
| 14 | New Scenarios | core/scenarios.py, data/scenarios.json | persona.py | 635 |

**Phase 2 total: ~2,140 LOC across 5 new files + 7 modified files**

---

## Phase 3: Growth Features (Build Third)

### Feature 15: Feedback System Enhancement

The basic feedback endpoint exists. Enhance with structured follow-up questions and NPS scoring.

**File:** `src/dealsim_mvp/core/analytics.py` (modify, ~40 LOC)

```
Dependencies: core/analytics.py (existing)
```

**What it does:**
- Add structured fields: usefulness_rating (1-5), realism_rating (1-5), would_recommend (0-10 NPS), improvement_suggestion (text)
- Post-sim feedback prompt with contextual questions based on scenario type
- Aggregate NPS calculation for admin dashboard

**API Endpoint changes:**
- Modify `POST /api/feedback` — accept additional fields

**Frontend:** Enhanced feedback modal with 3 rating sliders + text box. Appears after every completed session.

**Estimated LOC:** 40 (core) + 15 (route mod) + 10 (models) + 60 (frontend) = **125 total**

---

### Feature 16: Usage Analytics

Track which features get used, where users drop off, and session flow patterns.

**File:** `src/dealsim_mvp/core/analytics.py` (modify, ~60 LOC)

```
Dependencies: core/analytics.py (existing)
```

**What it does:**
- Expand allowed event types: "analyzer_used", "counter_offer_generated", "playbook_generated", "challenge_started", "challenge_completed", "debrief_viewed", "scorecard_shared", "pattern_viewed"
- Add session flow tracking: events within a session are linked by session_id
- Time-on-page estimates from event timestamps

**API Endpoint changes:**
- Modify `POST /api/events` — expand allowed event types
- Modify `GET /admin/stats` — add feature usage breakdown

**Frontend:** Emit events from every new feature interaction. No visible UI change.

**Estimated LOC:** 60 (core) + 10 (route mod) + 80 (frontend event calls) = **150 total**

---

### Feature 17: Admin Dashboard Enhancement

Upgrade the inline HTML admin page to show feature usage, funnel analysis, and challenge stats.

**File:** `src/dealsim_mvp/app.py` (modify, ~100 LOC)

```
Dependencies: core/analytics.py (read_events, read_feedback)
```

**What it does:**
- Feature usage table: which features are used most/least
- Conversion funnel: session_created → first_message → completed → feedback_submitted
- Daily active usage chart (simple ASCII or inline SVG)
- Challenge participation stats
- Analyzer usage stats

**API Endpoint changes:**
- Modify `GET /admin/stats` — richer dashboard HTML

**Frontend:** Server-rendered HTML (no JS framework needed). Same pattern as current admin page.

**Estimated LOC:** 100 (app.py expansion) + 20 (analytics additions) = **120 total**

---

### Feature 18: Negotiation Audit

Paste an email thread or chat log and get feedback on negotiation technique.

**File:** `src/dealsim_mvp/core/audit.py` (~220 LOC)

```
Dependencies: core/simulator.py (MoveType, _classify_user_move patterns), core/scorer.py (scoring logic)
```

**What it does:**
- `audit_negotiation(text: str, role: str) -> AuditResult`
- Parses multi-turn conversation from pasted text (detects "me:"/"them:" or email headers)
- Classifies each turn's move type using existing signal detection from simulator.py
- Scores the conversation on the same 6 dimensions as the simulator
- Generates per-turn feedback: "Here you conceded without getting anything in return"

**API Endpoint:**
- `POST /api/audit` — accepts raw text + role indicator, returns audit result

**Response:**
```python
{
    "turns_detected": int,
    "your_moves": [{"text": str, "move_type": str, "feedback": str}],
    "scores": {...},                # same 6-dimension structure
    "overall_score": int,
    "top_recommendations": [str],
}
```

**Frontend:** New page or tab. Large text area for pasting. Results displayed same as sim scorecard.

**Estimated LOC:** 220 (core) + 35 (route) + 25 (models) + 120 (frontend) + 80 (tests) = **480 total**

---

### Feature 19: Lifetime Earnings Calculator

Show cumulative impact of better negotiation across a career.

**File:** `src/dealsim_mvp/core/analyzer.py` (add function, ~60 LOC)

```
Dependencies: core/analyzer.py (existing)
```

**What it does:**
- `calculate_lifetime_impact(current_salary, negotiated_salary, years_remaining, raise_pct) -> LifetimeResult`
- Compound calculation: the $5K you negotiate now compounds through future raises
- Shows: 5-year impact, 10-year impact, career total, with and without raises
- Viral hook: "Negotiating $8K more today = $147K over 10 years"

**API Endpoint:**
- `POST /api/lifetime-calc` — accepts salary pair + career params, returns projections

**Frontend:** Interactive calculator with sliders. Big number display. "Share this" integration.

**Estimated LOC:** 60 (core) + 20 (route) + 15 (models) + 100 (frontend) + 30 (tests) = **225 total**

---

### Phase 3 Summary

| # | Feature | New Files | Modified Files | LOC |
|---|---------|-----------|---------------|-----|
| 15 | Feedback | — | analytics.py, routes.py, models.py | 125 |
| 16 | Usage Analytics | — | analytics.py, routes.py | 150 |
| 17 | Admin Dashboard | — | app.py, analytics.py | 120 |
| 18 | Negotiation Audit | core/audit.py, routes_audit.py | — | 480 |
| 19 | Lifetime Calculator | — | analyzer.py, routes_analyzer.py | 225 |

**Phase 3 total: ~1,100 LOC across 2 new files + 6 modified files**

---

## Dependency Graph

```
                    ┌─────────────┐
                    │   app.py    │
                    │  (factory)  │
                    └──────┬──────┘
                           │ mounts
            ┌──────────────┼──────────────┬────────────────┐
            │              │              │                │
     routes.py     routes_analyzer.py  routes_debrief.py  routes_challenge.py
     (simulation)   (analysis tools)   (post-sim)         (daily)
            │              │              │                │
            │         ┌────┴────┐    ┌────┴────┐          │
            │     analyzer.py  counter_offer.py  debrief.py  challenge.py
            │         │         playbook.py       │          │
            │         │              │            │          │
            └────┬────┴──────────────┴────────────┴──────────┘
                 │
          ┌──────┴──────┐
          │   core/     │
          ├─ session.py │──── persistence layer
          ├─ simulator.py │── negotiation engine
          ├─ scorer.py  │── scoring + money-left
          ├─ persona.py │── opponent generation
          ├─ patterns.py│── cross-session analysis
          ├─ analytics.py│── event tracking
          └─ scenarios.py│── scenario registry
                 │
          ┌──────┴──────┐
          │   data/     │
          ├─ market_ranges.json
          ├─ scenarios.json
          └─ challenge_bank.json
```

---

## New Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "pydantic>=2.0",
    "Pillow>=10.0",          # Phase 1: scorecard PNG generation
]
```

No other external dependencies required. The design is deliberately dependency-light.

---

## API Endpoint Map (Full Product)

### Simulation (routes.py — existing, modified)
| Method | Path | Phase |
|--------|------|-------|
| POST | `/api/sessions` | MVP (modify P2) |
| POST | `/api/sessions/{id}/message` | MVP |
| POST | `/api/sessions/{id}/complete` | MVP (modify P1) |
| GET | `/api/sessions/{id}` | MVP (modify P1) |
| GET | `/api/sessions` | P1 (new — list all) |

### Analysis Tools (routes_analyzer.py — new)
| Method | Path | Phase |
|--------|------|-------|
| POST | `/api/analyze` | P1 |
| POST | `/api/counter-offer` | P1 |
| POST | `/api/playbook` | P1 |
| POST | `/api/lifetime-calc` | P3 |

### Post-Sim (routes_debrief.py — new)
| Method | Path | Phase |
|--------|------|-------|
| GET | `/api/sessions/{id}/debrief` | P1 |
| GET | `/api/sessions/{id}/scorecard.png` | P1 |

### Daily Challenge (routes_challenge.py — new)
| Method | Path | Phase |
|--------|------|-------|
| GET | `/api/challenge/today` | P2 |
| POST | `/api/challenge/start` | P2 |
| POST | `/api/challenge/{id}/complete` | P2 |

### History & Patterns (routes.py — additions)
| Method | Path | Phase |
|--------|------|-------|
| GET | `/api/score-history` | P2 |
| GET | `/api/patterns` | P2 |

### Audit (routes_audit.py — new)
| Method | Path | Phase |
|--------|------|-------|
| POST | `/api/audit` | P3 |

### Feedback & Analytics (routes.py — existing, modified)
| Method | Path | Phase |
|--------|------|-------|
| POST | `/api/feedback` | MVP (modify P3) |
| POST | `/api/events` | MVP (modify P3) |

### System (app.py — existing)
| Method | Path | Phase |
|--------|------|-------|
| GET | `/health` | MVP |
| GET | `/admin/stats` | MVP (modify P3) |

**Total endpoints: 21 (8 existing + 13 new)**

---

## LOC Summary

| Phase | New Code | Cumulative |
|-------|----------|------------|
| MVP (current) | 2,950 | 2,950 |
| Phase 1 | 2,575 | 5,525 |
| Phase 2 | 2,140 | 7,665 |
| Phase 3 | 1,100 | 8,765 |

**Full product: ~8,800 lines** — still a single-developer-manageable codebase.

---

## Build Order Within Each Phase

### Phase 1 (strict order — each step depends on the previous)
1. **Session Persistence** (#4) — everything else needs reliable storage
2. **Security Middleware** (#5) — must be in place before any public traffic
3. **Debrief + Money Left** (#1, #2) — extends existing simulation, no new modules
4. **Scorecard PNG** (#3) — depends on scorer, adds Pillow dependency
5. **Offer Analyzer** (#6) — new independent module, no sim dependency
6. **Counter-Offer Generator** (#7) — depends on analyzer
7. **Playbook Generator** (#8) — depends on analyzer + counter-offer

### Phase 2 (mostly parallel)
- **Scenarios** (#14) first — other features benefit from more scenario variety
- **Difficulty** (#10) + **Opponent Tuning** (#9) — can be built in parallel
- **Score History** (#11) then **Pattern Recognition** (#12) — patterns needs history
- **Daily Challenge** (#13) — independent, can be built anytime

### Phase 3 (all independent)
- Build in any order. **Audit** (#18) is highest value. **Lifetime Calculator** (#19) is lowest effort.

---

## Design Principles for All Development Agents

1. **No new dependencies without justification.** Pillow is the only addition. Everything else uses stdlib + FastAPI + Pydantic.

2. **Every new module must have a docstring stating its governing equation or decision logic.** This is a physics simulation engine repo — document the rules.

3. **Every new endpoint must have a test.** Use the existing `conftest.py` pattern with `httpx.AsyncClient`.

4. **The analyzer module is the product.** Simulation is the upsell. Build analyzer to work standalone — it must not import from simulator.py or session.py.

5. **All monetary values stay in the same unit.** No currency conversion. State the convention in every module that handles money.

6. **Frontend stays as single-file HTML pages with Tailwind CDN.** No build step. No npm. JS files are extracted only for code organization — they are loaded via `<script src>` tags.

7. **File-based persistence only.** No database. JSON files in `DATA_DIR`. This keeps deployment to a single container with a volume mount.

8. **Market data is bundled, not fetched.** `market_ranges.json` ships with the app. External API integration is a future concern, not an architecture concern.
