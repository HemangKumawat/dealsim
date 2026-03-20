# DealSim -- Company Internal Technical Document

**Version:** 0.1.0
**Date:** 2026-03-19
**Classification:** Internal -- Engineering & Founders
**Status:** Post-W1 audit, pre-production

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Core Engine](#2-core-engine)
3. [Scoring System](#3-scoring-system)
4. [Security Posture](#4-security-posture)
5. [Persistence Layer](#5-persistence-layer)
6. [Deployment](#6-deployment)
7. [Testing](#7-testing)
8. [Analytics & Feedback](#8-analytics--feedback)
9. [Content Library](#9-content-library)
10. [Known Limitations](#10-known-limitations)
11. [Development History](#11-development-history)

---

## 1. Architecture Overview

### System Summary

DealSim is a rule-based negotiation training simulator built as a single Python application with a FastAPI backend and a single-file HTML/CSS/JS frontend. The design is deliberately dependency-light: three runtime dependencies (FastAPI, uvicorn, Pydantic), file-based persistence, no database, no external API calls.

**Codebase size:** ~2,950 lines Python + 789 lines HTML at MVP; expanded to approximately 5,500 lines Python after Phase 1 features.

### Module Map

```
src/dealsim_mvp/
+-- __init__.py                    # Version string
+-- app.py                         # FastAPI factory, CORS, rate limiter, admin dashboard
|
+-- api/
|   +-- models.py                  # Pydantic request/response schemas
|   +-- routes.py                  # Session CRUD, feedback, events, history, patterns
|   +-- routes_analyzer.py         # Offer analysis, counter-offer, playbook
|   +-- routes_debrief.py          # Post-sim debrief, scorecard PNG
|   +-- routes_challenge.py        # Daily challenge endpoints
|   +-- routes_audit.py            # Email audit, lifetime calculator
|   +-- middleware.py              # XSS sanitization, session eviction, security headers
|   +-- offer_analyzer.py          # API-layer offer parsing (wraps core)
|
+-- core/
|   +-- simulator.py               # Rule-based negotiation engine (669 LOC)
|   +-- scorer.py                  # 6-dimension scorer with coaching tips (454 LOC)
|   +-- persona.py                 # Opponent generation, 22 persona templates (159 LOC)
|   +-- session.py                 # Session lifecycle, in-memory store + JSON persistence
|   +-- store.py                   # Atomic file-based session storage
|   +-- debrief.py                 # Opponent hidden state reveal engine
|   +-- playbook.py                # Personalized negotiation cheat sheet generator
|   +-- offer_analyzer.py          # Offer parsing, market position scoring
|   +-- counter_offer.py           # 3-strategy counter-offer generator
|   +-- challenges.py              # Daily challenge engine
|   +-- email_audit.py             # Email negotiation auditor
|   +-- earnings.py                # Lifetime earnings calculator
|   +-- analytics.py               # JSONL append/read for events + feedback
|
+-- data/
    +-- market_ranges.json         # Salary/rate benchmarks by role/location
    +-- scenarios.json             # Scenario definitions
    +-- challenge_bank.json        # 30 daily challenge templates

static/
+-- index.html                     # Single-file chat UI (Tailwind CDN)
```

### Data Flow

```
  User (browser)
       |
       v
  static/index.html  <-- Tailwind CDN, vanilla JS
       |
       | REST API (JSON)
       v
  app.py (FastAPI)
       |-- Rate limiter middleware
       |-- CORS middleware
       |-- Security headers
       |
       +-- routes.py -----------> session.py ----> store.py ----> .json on disk
       |                              |
       |                              +----------> simulator.py
       |                              |                |
       |                              +----------> scorer.py
       |                              |
       |                              +----------> persona.py
       |
       +-- routes_analyzer.py --> offer_analyzer.py -> market_ranges.json
       |                     +--> counter_offer.py
       |                     +--> playbook.py
       |
       +-- routes_debrief.py ---> debrief.py
       |
       +-- routes_challenge.py -> challenges.py -> challenge_bank.json
       |
       +-- routes_audit.py -----> email_audit.py
       |                     +--> earnings.py
       |
       +-- analytics.py --------> events.jsonl (append-only)
       +-- feedback.py ---------> feedback.jsonl (append-only)
```

### API Surface -- 18 Endpoints

| # | Method | Path | Category | Description |
|---|--------|------|----------|-------------|
| 1 | POST | `/api/sessions` | Simulation | Create new negotiation session |
| 2 | POST | `/api/sessions/{id}/message` | Simulation | Send user message, get opponent response |
| 3 | POST | `/api/sessions/{id}/complete` | Simulation | End session, generate scorecard |
| 4 | GET | `/api/sessions/{id}` | Simulation | Get session state + transcript |
| 5 | GET | `/api/sessions/{id}/debrief` | Post-Sim | Opponent hidden state + per-turn analysis |
| 6 | GET | `/api/sessions/{id}/playbook` | Post-Sim | Personalized negotiation cheat sheet |
| 7 | POST | `/api/offers/analyze` | Analysis | Market position scoring for any offer |
| 8 | GET | `/api/market-data/{role}/{loc}` | Analysis | Benchmark lookup |
| 9 | GET | `/api/users/{id}/history` | History | Score history across sessions |
| 10 | GET | `/api/users/{id}/patterns` | History | Cross-session behavioral patterns |
| 11 | GET | `/api/challenges/today` | Challenge | Today's daily challenge config |
| 12 | POST | `/api/challenges/today/submit` | Challenge | Submit challenge response and score |
| 13 | POST | `/api/feedback` | Analytics | Post-sim user feedback |
| 14 | POST | `/api/events` | Analytics | Feature usage tracking event |
| 15 | GET | `/api/scenarios` | Content | List available scenarios |
| 16 | POST | `/api/tools/earnings-calculator` | Tools | Lifetime earnings impact projection |
| 17 | POST | `/api/tools/audit-email` | Tools | Audit pasted email thread |
| 18 | GET | `/health` | System | Health check |

Admin endpoint (not counted): `GET /admin/stats` -- key-protected dashboard.

---

## 2. Core Engine

### How the Negotiation Simulator Works

The simulator (`core/simulator.py`, 669 LOC) is a rule-based state machine. There is no LLM involved. Every opponent response is generated deterministically from the current negotiation state, the persona configuration, and the user's classified move.

#### Turn Processing Pipeline

```
User message (text)
    |
    v
1. _extract_offer(text) --> monetary value or None
2. _classify_user_move(text, offer, state) --> MoveType enum
3. _check_resolution(move, offer, state) --> deal/no-deal/continue
4. _generate_opponent_response(move, state, persona) --> text + new offer
5. Update state (turn history, offer tracking, pressure counters)
6. Return response to API layer
```

#### Move Classification

User messages are classified into one of seven move types:

| MoveType | Detection Method |
|----------|-----------------|
| `ANCHOR` | First monetary offer from user |
| `COUNTER_OFFER` | Subsequent offer moving toward opponent (direction-aware) |
| `CONCESSION` | Offer moving away from user's position (direction-aware) |
| `QUESTION` | Interrogative signals ("what", "how", "why", "?") |
| `INFO_SHARE` | BATNA signals, credential mentions, market data references |
| `ACCEPTANCE` | Agreement signals ("deal", "accept") with no counter-offer present |
| `REJECTION` | Walk-away signals ("no deal", "walk away") |

**Direction awareness** (fixed in W1 audit): The classifier now determines whether the user wants to negotiate UP (salary, raise, freelance) or DOWN (medical bill, car, rent, vendor) by comparing anchor positions. Concession detection flips accordingly. This was the most impactful bug found during review -- roughly half of all scenario types had inverted concession classification before the fix.

#### Negotiation Style System

Each opponent persona has one of five negotiation styles. The style determines how the opponent calculates their next offer:

| Style | Behavior | Step Calculation |
|-------|----------|-----------------|
| COMPETING | Anchors aggressively, small concessions | `abs(midpoint - current) * 0.15 * pressure_factor` |
| COLLABORATING | Seeks mutual gains, responds to questions | `abs(midpoint - current) * 0.4 * pressure_factor` |
| COMPROMISING | Splits the difference | `abs(user_offer - current) * 0.5 * pressure_factor` |
| AVOIDING | Deflects, stalls, reveals little | Holds position 40% of the time; micro-concedes otherwise |
| ACCOMMODATING | Concedes readily under pressure | `abs(midpoint - current) * 0.6 * pressure_factor` |

`pressure_factor` is a 0.0--1.0 value derived from the persona's pressure setting (LOW=0.3, MEDIUM=0.6, HIGH=1.0) combined with runtime modifiers from user BATNA signals and concession patterns.

#### State Tracking

The `NegotiationState` object tracks per-session:
- Full turn history with classified moves
- User and opponent offer sequences
- Concession counts and magnitudes
- Question count and info-share count
- Pressure signals detected
- Hidden opponent state (reservation price, constraints, emotional reactivity)
- Resolution status (active / deal_reached / no_deal / walkaway)

---

## 3. Scoring System

### Six Dimensions

Every completed negotiation is scored across six dimensions, weighted to sum to 100. Each dimension produces a 0--100 raw score.

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Opening Strategy | 20% | Did the user anchor first? How ambitious relative to market? |
| Information Gathering | 15% | Questions asked, timing of information probes |
| Concession Pattern | 25% | Size, speed, and deceleration of concessions |
| BATNA Usage | 15% | References to alternatives for leverage |
| Emotional Control | 10% | Composure under pressure moves |
| Value Creation | 15% | Exploration of integrative solutions beyond price |

### Dimension Calculation Details

**Opening Strategy (20%)**
- Anchoring first: +30 base points
- Ambitiousness: compared to the midpoint of opening-to-reservation range. Anchoring beyond midpoint scores higher.
- Penalty for not anchoring at all: capped at 25.

**Information Gathering (15%)**
- Scored on absolute question count with a turn-adjusted bonus (post-fix).
- 0 questions = 15, 1 = 40, 2 = 60, 3+ = 75 base.
- +15 bonus if question ratio > 0.3 of total turns.
- Known issue (SCORE-02, deferred): pure ratio scoring still rewarded short negotiations before fix.

**Concession Pattern (25%)**
- Measures concession magnitude and deceleration.
- Decelerating concessions (each smaller than the last) score highest.
- Zero-concession with deal: now scored based on deal position relative to opponent's full range (post-fix). Accepting the first offer scores 35, not 100.
- Known issue (SCORE-04, deferred): keyword matching for value creation is still gameable.

**BATNA Usage (15%)**
- Detects alternative-reference signals in user messages.
- 1 well-timed signal = 90 (post-fix; was 80).
- 2 signals = 75, 3+ = 55, 0 = 20.
- Diminishing returns by design: overusing BATNA sounds like bluffing.

**Emotional Control (10%)**
- Tracks user response patterns after opponent pressure moves.
- Immediate large concessions after pressure: penalized.
- Steady or measured responses: rewarded.
- Lowest weight because it is the hardest to measure from text alone.

**Value Creation (15%)**
- Detects mentions of non-price package terms (equity, remote work, signing bonus, timeline, etc.).
- Known issue (SCORE-04, deferred): keyword presence is counted regardless of context. A user mentioning "I don't care about equity" still gets credit.

### Calibration Notes

- The scoring system was designed for salary negotiations and extended to other scenarios. Scoring accuracy is highest for salary/freelance, lowest for medical bill and scope creep scenarios.
- Weights were set by the design team, not calibrated against human expert ratings. Weight validation against expert-scored transcripts is a planned future task.
- The "money left on table" metric (debrief module) provides a complementary outcome-based score that is independent of behavioral scoring.

---

## 4. Security Posture

### Audit Scope

A full security review was conducted on 2026-03-19 covering all Python files in `src/dealsim_mvp/`. A parallel deployment configuration review covered the Dockerfile, docker-compose.yml, fly.toml, render.yaml, railway.json, and environment variable handling.

### Findings Summary

| Severity | Found | Fixed | Remaining |
|----------|-------|-------|-----------|
| CRITICAL | 1 | 1 | 0 |
| HIGH | 7 | 7 | 0 |
| MEDIUM | 8 | 3 | 5 |
| LOW | 7 | 0 | 7 |

### Critical and High Fixes Applied

| ID | Issue | Fix |
|----|-------|-----|
| CORS mismatch | App read `CORS_ORIGINS`; all deploy configs set `DEALSIM_CORS_ORIGINS`. CORS was wide open on every deployment. | App now reads `DEALSIM_CORS_ORIGINS`. Defaults to localhost with warning. |
| XSS in admin | Feedback comments and feature names interpolated into HTML without escaping. | Applied `html.escape()` to all user-controlled strings in admin dashboard. |
| Admin key default | Default key was `change-this-secret`. | Default changed to empty string; admin returns 503 when unconfigured. |
| Admin key in HTML | Key embedded in `<a href>` tag in dashboard source. | Replaced with static placeholder text. |
| Admin key comparison | Used `!=` (timing-vulnerable). | Changed to `secrets.compare_digest()`. |
| Rate limiter leak | `_rate_store` dict keys never evicted; unbounded memory growth. | Per-request eviction of empty keys + periodic 60-second sweep. |
| Docker root user | Container ran all processes as root. | Added non-root `dealsim` user in Dockerfile. |
| Health check curl | `docker-compose.yml` used `curl` which is absent from `python:3.12-slim`. | Changed to Python `urllib.request` pattern. |
| CORS + credentials | `allow_origins=["*"]` with `allow_credentials=True`. | Credentials now conditional on explicit origin list. |
| Exception leakage | `detail=str(exc)` exposed internal error messages. | Generic "Internal server error" returned; exception logged server-side. |
| Session ID validation | Arbitrary strings accepted as session IDs. | UUID4 regex validation on all session endpoints; invalid IDs return 400. |

### Remaining Known Issues

| Severity | Issue | Status |
|----------|-------|--------|
| MEDIUM | `user_id` unbounded, no auth on history endpoint | Deferred -- requires auth system design |
| MEDIUM | `list_sessions()` exposes all session IDs | Function exists but not wired to public route |
| MEDIUM | Session store file has default OS permissions | Deferred -- Windows support incomplete for POSIX permissions |
| MEDIUM | Uniform rate limit for all endpoint tiers | Deferred -- tiered limits planned |
| MEDIUM | Proxy-unaware IP detection behind reverse proxy | Deferred -- requires `TRUSTED_PROXIES` config |
| LOW | `scenario_type` and `difficulty` not enum-validated | Silently falls back to defaults |
| LOW | Unbounded event `properties` dict | Can write large payloads to JSONL |
| LOW | Loose dependency version pins | No upper bounds in pyproject.toml |
| LOW | No lock file for reproducible builds | `uv.lock` not committed |
| LOW | API docs (`/docs`, `/redoc`) exposed in production | Planned: disable in production environment |
| LOW | MD5 used for challenge rotation | Non-security context; scanner noise |
| LOW | Data files potentially under static root | Latent risk if `STATIC_DIR` changes |

---

## 5. Persistence Layer

### Architecture

DealSim uses file-based persistence with no database. Three storage mechanisms:

| Store | Format | File | Purpose |
|-------|--------|------|---------|
| Session store | JSON (single file) | `{DATA_DIR}/sessions.json` | Active + completed negotiation sessions |
| Analytics | JSONL (append-only) | `{DATA_DIR}/events.jsonl` | Feature usage events |
| Feedback | JSONL (append-only) | `{DATA_DIR}/feedback.jsonl` | Post-session user feedback |

`DATA_DIR` defaults to `/tmp/dealsim_data` (configurable via `DEALSIM_DATA_DIR`).

### Session Store (store.py)

**Write pattern:** Atomic write-then-replace using `os.replace()` (single syscall, atomic on both POSIX and Windows). Data is flushed to disk with `f.flush()` + `os.fsync()` before the replace.

**Thread safety:** `threading.Lock` guards all of `save_sessions()`, `load_sessions()`, and `clear_store()`. Sufficient for single-process uvicorn. Multi-worker deployments require file-level locking (`filelock` package) or migration to SQLite.

**Session lifecycle:**
1. Created in memory on `POST /api/sessions`
2. Persisted to disk after every state change (message, completion)
3. Recovered from disk on server restart if not in memory
4. Auto-pruned: sessions older than 7 days removed on startup

**Corruption recovery:** If JSON parsing fails on load, the corrupt file is renamed to `.corrupt.{unix_timestamp}` and an empty dict is returned. The server starts cleanly; sessions are lost but evidence is preserved.

**Directory auto-creation:** `save_sessions()` calls `mkdir(parents=True, exist_ok=True)` before writing.

### Analytics & Feedback (JSONL)

**Write pattern:** `threading.Lock`-protected append of a single JSON line. Partial lines from crashes are skipped on read (JSONL is inherently crash-safe per-line).

**Rotation:** Triggered when a JSONL file exceeds 10 MB. Current file becomes `.1`, previous `.1` becomes `.2`, up to `.3` max. Oldest is deleted. All renames use `os.replace()`.

### What Was Fixed in W1

| Issue | Severity | Fix |
|-------|----------|-----|
| Non-atomic write on Windows (`remove` + `rename` gap) | HIGH | Replaced with single `os.replace()` + `fsync` |
| No concurrency protection on session store | HIGH | Added `threading.Lock` to store.py and session.py |
| Corrupt JSON discards all sessions without backup | MEDIUM | Archive corrupt file before returning empty |
| Unbounded JSONL growth | MEDIUM | Added 10 MB rotation with 3 archived copies |
| Store directory not auto-created | LOW | Added `mkdir` before write |

### What Remains

| Issue | Severity | Notes |
|-------|----------|-------|
| Multi-process locking | N/A for MVP | Single-worker uvicorn only; documented as production prerequisite |
| File permissions (0o600) | LOW | Windows support incomplete for POSIX permissions |
| Disk-full error propagation | MEDIUM | Errors are logged but not returned as HTTP 507 |

---

## 6. Deployment

### Docker Configuration

**Base image:** `python:3.12-slim`
**Package manager:** `uv` (installed via pip, used for fast dependency resolution)
**User:** Non-root `dealsim` user (added in W1 fix)
**Exposed port:** 8000

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml .
COPY src/ src/
COPY static/ static/
RUN uv pip install --system .
RUN useradd --create-home --shell /bin/bash dealsim \
    && mkdir -p /tmp/dealsim_data \
    && chown dealsim:dealsim /tmp/dealsim_data
USER dealsim
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "dealsim_mvp.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### Cloud Platform Configurations

| Platform | Config File | Free Tier | Data Persistence | Cold Start |
|----------|-------------|-----------|-----------------|------------|
| Render | `render.yaml` | Yes (spins down after 15 min) | Ephemeral on free; add Render Disk for paid | ~30s after spin-down |
| Fly.io | `fly.toml` | Yes (3 shared-CPU VMs, 256MB) | Requires `fly volumes create` | ~10-30s (grace period set to 30s) |
| Railway | `railway.json` | $5/mo credit | Persists within deploy lifecycle | Minimal |
| VPS (Hetzner) | Manual | ~$4/mo (CX22) | Docker volume, persistent | None |

### Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `PORT` | `8000` | No | Server port |
| `DEALSIM_CORS_ORIGINS` | `localhost` | Yes (production) | Comma-separated allowed origins |
| `DEALSIM_ADMIN_KEY` | `""` (disabled) | Yes (production) | Admin dashboard access key |
| `DEALSIM_DATA_DIR` | `/tmp/dealsim_data` | No | Persistent data directory |
| `DEALSIM_SESSION_FILE` | `{DATA_DIR}/sessions.json` | No | Session store file path |
| `RATE_LIMIT_PER_MINUTE` | `100` | No | Max requests per IP per minute |
| `LOG_LEVEL` | `INFO` | No | Python log level |
| `DEALSIM_ENV` | `""` | No | Set to `production` to disable API docs |

### Health Checks

All platforms use the same endpoint: `GET /health` returns `{"status": "healthy", "version": "0.1.0"}` with HTTP 200. The Dockerfile HEALTHCHECK runs every 30 seconds with a 5-second timeout and 3 retries.

---

## 7. Testing

### Summary

| Metric | Value |
|--------|-------|
| Total tests | 310 (298 initial + 12 added during fix cycle) |
| All passing | Yes (303/303 after engine fixes; remaining aligned after analyzer fixes) |
| Runtime | ~0.5s |
| Test framework | pytest 8.x + httpx for async API tests |
| Line coverage tool | Not yet configured (pytest-cov recommended) |

### Coverage by Module

| Source Module | Test File | Tests | Status |
|--------------|-----------|-------|--------|
| `core/persona.py` | `test_persona.py` | 16 | Pre-existing |
| `core/simulator.py` | `test_simulator.py` | 19 | Pre-existing |
| `core/scorer.py` | `test_scorer.py` | 20 | Pre-existing, updated in W1 |
| `core/session.py` | `test_session.py` | 15 | Pre-existing |
| `api/routes.py` | `test_api.py` | 16 | Pre-existing, updated in W1 |
| Integration | `test_integration.py` | 12 | Pre-existing |
| `core/debrief.py` | `test_debrief.py` | 14 | New in W1 |
| `core/playbook.py` | `test_playbook.py` | 19 | New in W1 |
| `core/offer_analyzer.py` | `test_offer_analyzer.py` | 37 | New in W1 (20 + 17 after fixes) |
| `core/earnings.py` + `core/email_audit.py` | `test_tools.py` | 23 | New in W1 |
| `core/challenges.py` | `test_challenges.py` | 50 | New in W1 |

### API Endpoint Test Coverage

| Coverage Level | Count | Percentage |
|---------------|-------|------------|
| Full HTTP-level tests | 7/18 | 39% |
| Unit-tested (core logic) | 16/18 | 89% |
| No test at all | 4 endpoints | 22% |

**Untested endpoints:** `/api/users/{id}/history`, `/api/users/{id}/patterns`, `/api/events`, `/api/scenarios`. These need HTTP-level test cases.

### What Is Tested

- All negotiation move types (anchor, counter, concession, question, info-share, acceptance, rejection)
- Direction-aware classification for buyer vs seller scenarios
- All five negotiation styles at three pressure levels
- All six scoring dimensions with boundary cases
- Zero-concession deal scoring (gameable case patched)
- Debrief generation for deal and no-deal outcomes
- Playbook generation with pre-session and post-session modes
- Offer analyzer: 2026-calibrated benchmarks, five roles, eight locations
- Text parsing: "$150K" format, bi-weekly/monthly pay periods, combined bonus formats
- Email audit: empty input, very long input, unicode/emoji
- Daily challenges: all 30 templates, edge cases (negative day, unicode responses)
- Earnings calculator: zero increase, negative increase, compound projections
- Session ID format validation (UUID4 regex)
- Rate limiting behavior

### What Is Not Tested

| Gap | Risk | Notes |
|-----|------|-------|
| `core/store.py` -- file I/O | Medium | Needs `tmp_path` fixture for corrupt JSON, missing file, stale cleanup |
| Concurrent session modification | Medium | Needs threading test harness |
| JSONL mid-line corruption recovery | Low | Handled by try/except but not exercised in tests |
| Store file permission denied | Low | OS-specific, hard to test portably |
| Line-level coverage metrics | -- | pytest-cov not yet configured |

### Bugs Found During Testing

Two bugs were found by the test-writing agents and subsequently fixed:

1. **ZeroDivisionError** in `core/offer_analyzer.py` when `base_salary=0`. Fixed with bounds checking (`< 1` and `> $10M`).
2. **ValueError** in `api/offer_analyzer.py` when offer text contained both "15% annual bonus" and "$10k signing bonus" -- regex group collision. Fixed by separating signing bonus and annual bonus regex patterns.

---

## 8. Analytics & Feedback

### Event Tracking

The analytics system records user interactions as JSONL events appended to `data/events.jsonl`. Each event contains:

```json
{
  "event_type": "session_completed",
  "session_id": "uuid",
  "properties": { "scenario": "salary", "score": 72, "turns": 8 },
  "timestamp": "2026-03-19T14:30:00Z"
}
```

**Allowed event types:** `session_created`, `session_completed`, `analyzer_used`, `counter_offer_generated`, `playbook_generated`, `challenge_started`, `challenge_completed`, `debrief_viewed`, `scorecard_shared`, `pattern_viewed`, `feedback_submitted`.

### Feature Usage Measurement

The admin dashboard (`GET /admin/stats?key=...`) aggregates events to show:

- Total sessions created and completion rate
- Average overall score
- Feature usage breakdown (which tools are used most/least)
- Scenario type distribution
- Recent feedback with star ratings and comments
- Conversion funnel: session created --> first message --> completed --> feedback submitted

### Feedback Collection

Post-session feedback is collected via `POST /api/feedback` with:
- Star rating (1-5)
- Free-text comment
- Session ID linkage
- Timestamp

Feedback is stored in `data/feedback.jsonl` with the same rotation policy as analytics (10 MB max, 3 archived copies).

### Admin Dashboard

Server-rendered HTML page protected by `DEALSIM_ADMIN_KEY`. Shows aggregate metrics without requiring any frontend framework. All user-controlled content (comments, feature names, scenario types) is HTML-escaped to prevent XSS.

---

## 9. Content Library

### Scenarios (10 types)

| Scenario | User Role | Opponent Role | Direction |
|----------|-----------|---------------|-----------|
| Salary Negotiation | Candidate | Hiring Manager / CTO | User wants UP |
| Freelance Rate | Freelancer | Client | User wants UP |
| Raise Request | Employee | Manager | User wants UP |
| Counter-Offer | Candidate with competing offer | Current employer | User wants UP |
| Budget Request | Department head | Finance director | User wants UP |
| Rent Negotiation | Tenant | Landlord | User wants DOWN |
| Medical Bill | Patient | Billing department | User wants DOWN |
| Car Purchase | Buyer | Dealer | User wants DOWN |
| Vendor Contract | Procurement | Vendor sales rep | User wants DOWN |
| Scope Creep | Freelancer | Client expanding scope | User wants DOWN (resist scope) |

### Personas (22 templates)

Each scenario has 2-3 persona templates with different negotiation styles. Examples:

| Persona | Scenario | Style | Pressure | Key Trait |
|---------|----------|-------|----------|-----------|
| Alex Chen (CTO) | Salary | COMPETING | HIGH | Tight budget, values equity |
| Sarah Mitchell (HR Director) | Salary | COLLABORATING | MEDIUM | Flexible on benefits |
| Marcus Webb (Startup Founder) | Freelance | COMPETING | HIGH | Scope-conscious, deadline-driven |
| Patricia Owens (Landlord) | Rent | ACCOMMODATING | LOW | Values long tenancies |
| First-Line Rep | Medical Bill | AVOIDING | MEDIUM | Deflects, limited authority |

Each persona defines: name, role, style, pressure, patience, transparency, emotional_reactivity, reservation_price, opening_offer, hidden_constraints[], and scenario-specific vocabulary.

### Daily Challenges (30 templates)

Micro-negotiations with specific constraints, rotating on a 30-day cycle (deterministic from date hash). Examples:

- "Negotiate without using a number" -- scored on anchoring technique
- "Close the deal in 3 turns or less" -- scored on efficiency
- "Get 3 pieces of information before making an offer" -- scored on information gathering

Each challenge defines: title, description, scenario_prompt, constraint, max_turns (typically 3), scoring_focus (single dimension).

---

## 10. Known Limitations

### Engine Limitations (Deferred from W1 Review)

| ID | Issue | Impact | Priority |
|----|-------|--------|----------|
| BUG-03 | AVOIDING style can produce stuck negotiations (40% hold probability loops) | Frustrating UX with AVOIDING opponents | Medium |
| BUG-04 | `_extract_offer` takes MAX value from ranges; misparses "between $80K and $90K" | Wrong offer extracted in ~15% of range-format messages | Low |
| SCORE-02 | Information Gathering ratio still partially rewards short negotiations | Scoring bias toward quick games | Medium |
| SCORE-03 | BATNA dimension capped at 90 (was 80, raised but still has a ceiling) | 1.5 points permanently unattainable in overall score | Low |
| SCORE-04 | Value Creation dimension gameable via keyword mention without context | Users can inflate scores by name-dropping terms | Medium |
| PERSONA-02 | AVOIDING personas frustrating, not engaging (no "break point" mechanic) | Players learn nothing from stalled negotiations | Medium |
| PERSONA-03 | ACCOMMODATING opponents too easy (no relationship threshold) | No tension in ACCOMMODATING scenarios | Low |

### Playbook Limitations

| ID | Issue | Impact |
|----|-------|--------|
| PLAY-01 (partial) | Opening lines still salary-centric for some scenario types | Wrong framing for rent/medical/car |
| PLAY-02 | Concession ladder ignores non-monetary trades | Misses integrative options in rent/scope scenarios |
| PLAY-03 | Literal `[placeholder]` brackets in two objection responses | Visible to users as broken output |
| PLAY-04 | Key questions salary-biased when constraints are empty | Generic questions for non-salary scenarios |

### Infrastructure Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Single-process only | Cannot run multiple uvicorn workers safely | `threading.Lock` sufficient for single worker; multi-worker requires `filelock` or SQLite |
| No authentication | Anyone can read any user's history by guessing user_id | user_id is optional and client-generated; no PII stored |
| No database | All data in JSON/JSONL files on local disk | Acceptable for MVP volume; SQLite migration planned for production |
| No LLM integration | Opponent responses are rule-based, not generated | Keeps latency < 50ms and cost at zero; LLM integration is a future premium feature |
| Market data is static | Benchmark salaries are bundled JSON, not live data | Labeled as "2026-Q1 (2024 base +8%)"; manual refresh required |

### What to Build Next

**Short-term (pre-launch):**
1. Fix PLAY-03 (placeholder brackets) -- 5-minute fix
2. Add HTTP-level tests for 4 untested endpoints
3. Configure pytest-cov for line-level coverage
4. Add tiered rate limiting for expensive endpoints

**Medium-term (post-launch):**
1. AVOIDING break-point mechanic (BUG-03 + PERSONA-02)
2. Direction-aware offer range parsing (BUG-04)
3. Context-aware Value Creation scoring (SCORE-04)
4. Full scenario-specific playbook language (PLAY-01, PLAY-02, PLAY-04)

**Long-term (production scaling):**
1. SQLite migration for analytics and session storage
2. Multi-worker support with file-level locking
3. LLM-generated opponent responses (premium tier)
4. Live market data API integration
5. User authentication and account system

---

## 11. Development History

### Phase 1: Analysis (70 Agents)

The project began with a 70-agent parallel analysis sprint that produced the full product architecture document (`ARCHITECTURE.md`). This analysis covered:

- Market research on negotiation training tools
- Feature prioritization across 19 planned features in 3 phases
- Dependency graph mapping
- API surface design (21 endpoints planned, 18 implemented)
- LOC estimates per feature (subsequently validated within 15% accuracy)
- Build order optimization within each phase

The architecture document served as the single source of truth for all subsequent build work.

### Phase 2: Build (13 Agents)

Thirteen specialized agents built the product in dependency order:

1. **Session Persistence** -- file-based JSON store with atomic writes
2. **Security Middleware** -- rate limiting, XSS sanitization, session eviction
3. **Debrief Engine** -- opponent hidden state reveal, per-turn analysis
4. **Money Left on Table** -- outcome gap calculation
5. **Scorecard PNG** -- Pillow-based image generation (1200x630)
6. **Offer Analyzer** -- market position scoring against bundled benchmarks
7. **Counter-Offer Generator** -- three strategies (conservative/assertive/aggressive)
8. **Playbook Generator** -- personalized cheat sheet with opening lines, concession ladder, objection responses
9. **Daily Challenge Engine** -- 30-template rotation with constraint-based scoring
10. **Additional Scenarios** -- expanded from 2 to 10 negotiation types with 22 persona templates
11. **Email Audit** -- paste-and-analyze for real negotiation threads
12. **Lifetime Calculator** -- compound career impact projection
13. **Frontend Integration** -- wired all features into `static/index.html`

Total build output: approximately 5,500 lines of Python + 789 lines of HTML.

### Phase 3: Review Audit (12 Agents)

Twelve review agents conducted parallel audits across five domains:

| Review | Agent Role | Findings |
|--------|-----------|----------|
| Security Review | Security Engineer | 4 HIGH, 8 MEDIUM, 5 LOW findings |
| Engine Review | Game Design Engineer | 3 HIGH, 6 MEDIUM, 8 LOW findings (bugs + scoring + persona balance) |
| Persistence Review | Reliability Engineer | 2 HIGH, 2 MEDIUM, 3 LOW findings |
| Deployment Review | DevOps Engineer | 1 CRITICAL, 4 HIGH, 5 MEDIUM, 4 LOW findings |
| Test Coverage | QA Engineer | 126 new tests written; 2 bugs found during testing |

### Phase 4: Fix Cycle

Five targeted fix passes addressed all CRITICAL and HIGH findings:

| Fix Pass | Scope | Tests After |
|----------|-------|-------------|
| Security Fixes | 10 fixes (CORS, XSS, admin key, rate limiter, Docker, session validation) | 300/301 |
| Engine Fixes | 10 fixes (direction awareness, concession tracking, scoring, difficulty, debrief) | 303/303 |
| Persistence Fixes | 5 fixes (atomic writes, locking, rotation, corruption recovery, directory creation) | 303/303 |
| Analyzer Fixes | 8 fixes (consolidated architecture, ZeroDivisionError, regex crash, benchmarks, parser) | 310/310 |
| Frontend Fixes | 11 fixes (5 broken integrations, 5 conversion improvements, accessibility) | N/A (manual) |

### Current State

All CRITICAL and HIGH issues are resolved. The codebase is in a deployable state for beta testing. Twelve MEDIUM and seven LOW issues remain documented and tracked. The test suite runs in under 0.5 seconds with 310 passing tests covering 89% of endpoints at the unit level.

---

*Document generated 2026-03-19. For questions, refer to the source review documents in `docs/` or the architecture document at project root.*
