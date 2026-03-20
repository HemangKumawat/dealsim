# DealSim — Architecture

## System Diagram

```
┌─────────────────────────────────────────────┐
│  Browser                                    │
│                                             │
│  index.html        static JS modules        │
│  (Tailwind CSS)    (IIFEs, no bundler)      │
└──────────────────────┬──────────────────────┘
                       │ REST JSON (HTTP/HTTPS)
                       │
┌──────────────────────▼──────────────────────┐
│  nginx (container)                          │
│  SSL termination, rate limiting,            │
│  security headers, static cache headers     │
└──────────────────────┬──────────────────────┘
                       │ proxy_pass :8000
                       │ (internal Docker network)
┌──────────────────────▼──────────────────────┐
│  FastAPI app (container)                    │
│                                             │
│  app.py ── CORS, rate limiter, error handler│
│    └── api/routes.py ── all endpoints       │
│          ├── core/session.py                │
│          ├── core/simulator.py              │
│          ├── core/scorer.py                 │
│          ├── core/persona.py                │
│          ├── api/offer_analyzer.py          │
│          ├── api/debrief.py                 │
│          ├── api/analytics.py               │
│          ├── analytics.py                   │
│          ├── feedback.py                    │
│          └── monitoring.py                  │
│                                             │
│  /app/data/ ── JSONL files (volume mount)   │
└─────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│  certbot (container)                        │
│  Let's Encrypt renewal every 12 hours       │
└─────────────────────────────────────────────┘
```

---

## Backend Module Map

All Python source is under `src/dealsim_mvp/`.

### Entry points

**`app.py`** (206 LOC) — FastAPI application factory. Registers CORS middleware, rate limiter (in-memory, per-IP sliding window, 100 req/min default), request logging, error tracking, the API router, static file serving, health check, and admin dashboard. Called once at import time to produce the `app` instance uvicorn runs.

**`__init__.py`** — version string only.

### `api/` — HTTP layer

**`routes.py`** — all API endpoints, all Pydantic request/response models. The router is mounted at `/api`. Endpoints delegate entirely to core modules — no business logic lives here. Also handles input validation (UUID4 session IDs, allowed scenario types, body size limits).

**`debrief.py`** — post-simulation reveal: generates the opponent's turn-by-turn inner monologue from the completed `NegotiationState`, calculates how close the user came to the reservation price at each turn, and produces a printable negotiation playbook.

**`offer_analyzer.py`** — standalone offer analysis. Compares a submitted offer against bundled market range data (P25/P50/P75/P90 benchmarks). Also handles the earnings impact calculator (compound salary negotiation effect over a career) and email audit (classify moves in a pasted negotiation thread).

**`analytics.py`** — user-facing history and pattern detection. Reads completed session records from JSONL, computes score trends and per-dimension patterns across sessions, and manages the daily challenge (deterministic scenario per date via date hash).

### `core/` — business logic

**`session.py`** (248 LOC) — session lifecycle. `create_session` assigns a persona and initializes state. `negotiate` runs one turn through the simulator. `complete_session` calls the scorer and writes the result. Sessions live in an in-memory dict (`_SESSIONS`) and are serialized to `{DATA_DIR}/sessions/{id}.json` for persistence across restarts. Idle sessions are evicted after `SESSION_TTL_HOURS`.

**`simulator.py`** (669 LOC) — the negotiation engine. Defines `NegotiationState` (full mutable turn state), `Turn` (single exchange with classified `MoveType`), and `SimulatorBase` (abstract base class). The concrete `RuleBasedSimulator` implements opponent behavior across five `NegotiationStyle` variants (competitive, collaborative, accommodating, avoiding, compromising) and three `PressureLevel` variants. Classifies the user's move via regex + heuristic signal detection. Swapping in an LLM requires only subclassing `SimulatorBase` and overriding `generate_response` — the state contract is unchanged.

**`scorer.py`** (454 LOC) — six-dimension scorecard generator. Each dimension is scored 0–100 from observable signals in the transcript (offer amounts, `MoveType` counts, timing). Weights sum to 1.0. Coaching tips are generated only for dimensions below 70, keeping output actionable. Output is a `Scorecard` dataclass.

**`persona.py`** (159 LOC) — opponent profile generator. `NegotiationPersona` is a dataclass with financial constraints (target price, reservation price, opening offer) and behavioral traits (patience, transparency, emotional reactivity, hidden constraints). Three scenario templates ship as defaults. `to_mirofish_config()` converts a persona to the MiroFish agent config format for future LLM integration. Accepts `opponent_params` overrides from the API for user-facing tuning sliders.

### Supporting modules

**`analytics.py`** (top-level) — `AnalyticsTracker` singleton. Appends events to `{DATA_DIR}/events.jsonl`. Tracks feature usage, scenario popularity, session counts, completion rate, daily active sessions. All tracking calls are fire-and-forget — exceptions are swallowed to never break the API.

**`feedback.py`** — `FeedbackCollector` singleton. Appends feedback submissions to `{DATA_DIR}/feedback.jsonl`. Computes running average rating and surfaces recent comments for the admin dashboard.

**`monitoring.py`** — two ASGI middlewares. `RequestLoggingMiddleware` logs method, path, status, and latency on every request. `ErrorTrackingMiddleware` catches unhandled exceptions, increments an error counter, and re-raises. `get_health_data()` returns the current error count and uptime for the health endpoint.

**`rate_limiter.py`** — extracted rate limiter utility (complements the in-app implementation in `app.py`).

---

## Frontend Module Map

All frontend files live in `static/`. The app shell is `index.html`. All JS modules are standalone IIFEs loaded via `<script src>` tags — no module bundler, no npm dependency at runtime.

| File | What it does |
|---|---|
| `index.html` | App shell: chat UI, session setup form, scorecard panel, history tab, all page sections |
| `themes.css` | Three theme palettes (Arena, Coach, Lab) as CSS custom properties on `[data-theme]` |
| `tailwind.out.css` | Compiled Tailwind output — do not edit directly |
| `theme-switcher.js` | Theme toggle in the nav bar. Reads/writes `localStorage`. Applies `data-theme` on `<html>` |
| `gamification.js` | XP, levels (1–∞), streaks, 12 achievements. Entire state in `localStorage` key `dealsim_profile`. Emits `levelUp` and `achievement` events |
| `achievements.js` | Achievement grid renderer and toast notifications. Reads from `DealSimGamification`, styles via CSS variables |
| `celebrations.js` | Subtle micro-celebrations (not confetti — restrained acknowledgments for key moments) |
| `toasts.js` | Toast notification system (`window.DealSimToasts`). Four typed methods: success, error, info, warning |
| `stats-bar.js` | Sticky bar showing streak, level/XP, win rate, session count. Updates on `session-complete` event |
| `radar-chart.js` | Pure SVG hexagonal radar chart for the six scoring dimensions |
| `score-trends.js` | Score history visualization: trend line chart, summary stats, per-dimension sparklines. Pure SVG |
| `scenario-cards.js` | Replaces the scenario `<select>` with a horizontally scrollable visual card row |
| `daily-challenge-card.js` | Landing page card for today's challenge. Fetches `/api/challenges/today`, awards +50 XP on completion |
| `onboarding.js` | 3-step tooltip tour for first-time visitors. Never shows again after skip or finish |
| `learning-path.js` | Visual skill-tree showing negotiation milestones as a horizontal progress path |
| `quick-match.js` | One-click random negotiation start. Injects a two-card hero above the setup form |
| `engine-peek.js` | Collapsible "Under The Hood" section — educational transparency about engine flow and scoring |
| `session-export.js` | Session export and sharing (`window.DealSimExport`) |
| `service-worker.js` | PWA service worker. Cache-first for app shell, network-first for `/api/` requests |

**Concept pages** (`concept-a-arena.html`, `concept-b-coach.html`, `concept-c-lab.html`) — standalone design explorations for the three visual themes. Not linked from the main app.

---

## Data Flow: A Negotiation Session

```
1. POST /api/sessions
   routes.py ──► persona.py   (assign opponent)
             ──► session.py   (create NegotiationState, store in memory)
             ──► disk         (write {session_id}.json)
             ◄── opening_message, opponent_name, opening_offer

2. POST /api/sessions/{id}/message  (repeated)
   routes.py ──► session.py   (load state)
             ──► simulator.py (classify user move, generate opponent response)
             ──► session.py   (append Turn to transcript, persist)
             ◄── opponent_response, opponent_offer, resolved

3. POST /api/sessions/{id}/complete
   routes.py ──► session.py   (mark completed)
             ──► scorer.py    (score all 6 dimensions, produce Scorecard)
             ──► analytics.py (record session event)
             ──► disk         (write final scorecard to {session_id}.json)
             ◄── overall_score, dimensions, top_tips, agreed_value

4. GET /api/sessions/{id}/debrief  (optional)
   routes.py ──► session.py   (load completed state)
             ──► debrief.py   (reveal opponent hidden state, turn analysis)
             ◄── opponent inner monologue, distance_to_deal per turn, key moments

5. GET /api/sessions/{id}/playbook  (optional)
   routes.py ──► debrief.py   (generate personalized cheat sheet)
             ◄── structured playbook sections + plain-text version
```

---

## Data Flow: Offer Analysis

```
POST /api/offers/analyze
routes.py ──► offer_analyzer.py ──► market_ranges (bundled JSON)
          ◄── percentile, rating, market_range (P25/P50/P75/P90), factors, red_flags, recommendation

POST /api/tools/earnings-calculator
routes.py ──► offer_analyzer.py   (compound salary impact calculation)
          ◄── 5-year, 10-year, career projections

POST /api/tools/audit-email
routes.py ──► offer_analyzer.py   (parse + classify moves in pasted text)
          ◄── per-turn feedback, 6-dimension scores, recommendations
```

---

## Theme System

Three themes are defined in `themes.css` as CSS custom property blocks on attribute selectors:

```
:root, [data-theme="arena"]   — dark navy, coral red accent
[data-theme="coach"]          — deep purple, amber accent
[data-theme="lab"]            — GitHub-dark, blue accent
```

Every color in the UI reads from a variable (`--accent`, `--bg`, `--card-bg`, etc.) rather than a hardcoded value. Adding a fourth theme requires one new `[data-theme="name"]` block in `themes.css` and one entry in the `PALETTES` object in `theme-switcher.js`. No other files need to change.

The active theme is stored in `localStorage` key `dealsim_theme` and applied on page load by `theme-switcher.js` before the first paint.

---

## Gamification System

All gamification state is client-side, stored in `localStorage` under `dealsim_profile`. The server never sees XP or achievement data.

**XP formula:** base XP per session = `10 + (overall_score / 10)`. Level thresholds follow a linear progression (100 XP per level, uncapped).

**Achievements** (12 total): trigger on session completion. The gamification engine checks all achievement conditions after every `recordSession` call and emits `achievement` events for any newly unlocked ones. The achievements module picks up these events and fires toast notifications.

**Streak tracking:** a session counts toward the streak only if it occurs on a calendar day with no prior session. The streak resets if a day is skipped.

**Daily challenge bonus:** completing today's challenge awards a flat +50 XP on top of the normal session XP, handled in `daily-challenge-card.js`.

---

## Dependency Graph (Backend)

```
app.py
  └── api/routes.py
        ├── core/session.py
        │     └── core/simulator.py
        │           └── core/persona.py
        ├── core/scorer.py
        │     └── core/simulator.py  (NegotiationState, Turn, MoveType)
        ├── api/debrief.py
        │     └── core/session.py
        │     └── core/simulator.py
        ├── api/offer_analyzer.py    (standalone — no simulator dependency)
        ├── api/analytics.py         (reads JSONL files directly)
        ├── analytics.py             (AnalyticsTracker singleton)
        ├── feedback.py              (FeedbackCollector singleton)
        └── monitoring.py
```

`api/offer_analyzer.py` is deliberately isolated from `core/simulator.py` and `core/session.py`. The offer analysis tool is the primary product; the simulation is the training add-on. Keeping them separate means the analyzer can run as a lightweight standalone tool without pulling in the full simulation stack.

---

## Design Principles

1. **No database.** File-based persistence only (JSONL + JSON). A single container with one volume mount is the entire deployment.

2. **No build step for the app.** The frontend is a static HTML file with script tags. The Tailwind CSS compilation (`npm run build:css`) is developer tooling — the compiled output ships with the repo and does not need to run in production or CI.

3. **No external APIs.** Market range data is bundled as JSON. The simulation engine is rule-based. An internet outage does not affect functionality.

4. **Swappable engine.** `SimulatorBase` is the contract. Replacing the rule-based engine with an LLM requires subclassing that one class and overriding `generate_response`. The session, scorer, persona, and API layers are untouched.

5. **Analytics never break the API.** All tracking calls are wrapped in try/except and silently swallowed. A buggy analytics write never returns a 500 to the user.

6. **Document the rule.** Every module that implements a formula or decision rule states it in the docstring. This is a simulation engine — the governing logic should be readable without running the code.
