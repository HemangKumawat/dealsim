# DealSim MVP — Continuation Prompt

**Copy everything below the line into a new Claude Code chat to continue from where we left off.**

---

## Context

I've been building **DealSim** — a negotiation flight simulator MVP. The full deployment-ready codebase is at:

```
D:\Claude Base\easy_access\dealsim\
```

The original project source (with test_sim.py) is at:
```
D:\Claude Base\Mother Base\Simverse\dealsim-mvp\
```

This was built over a massive session using 130+ AI agents across 7 phases: strategic analysis → brainstorming → build → review → fix → deep audit → deployment prep.

---

## What DealSim Is

A negotiation practice tool where users chat with AI opponents, get scored, and learn to negotiate better. The strategic insight: **"The simulation is the delivery mechanism, the intelligence is the product."**

**Entry point:** Paste your offer → see what you're losing (Offer Analyzer)
**Core product:** Negotiation simulation with 10 scenario types, 6 scoring dimensions, hidden opponent state
**Upsell:** Full debrief ("What They Were Thinking"), playbook, pattern tracking
**Moat:** Data flywheel (outcome tracking, tactic effectiveness, opponent models, improvement trajectories)

---

## Tech Stack

- **Backend:** FastAPI (Python 3.12), single-process uvicorn
- **Frontend:** Single-file HTML SPA (`static/index.html`, ~2600 lines) with Tailwind CSS (CDN), system fonts
- **Persistence:** JSON file store with atomic writes (`os.replace` + `fsync`), JSONL analytics/feedback with 10MB rotation
- **Deployment:** Docker + docker-compose + nginx reverse proxy + Let's Encrypt SSL + backup scripts
- **Tests:** 310 tests across 12 files, all passing in ~0.5s

---

## Architecture

```
src/dealsim_mvp/
├── app.py              # FastAPI factory, CORS, rate limiting, admin dashboard
├── analytics.py        # JSONL analytics tracker with rotation
├── feedback.py         # JSONL feedback collector with rotation
├── api/
│   ├── routes.py       # 18 API endpoints (sessions, debrief, playbook, offers, tools, challenges, users, feedback, events, scenarios)
│   ├── models.py       # Pydantic request/response models
│   ├── analytics.py    # Analytics API routes
│   ├── debrief.py      # Debrief API routes
│   └── offer_analyzer.py  # Offer analysis API routes
├── core/
│   ├── simulator.py    # Rule-based negotiation engine (~670 lines), SimulatorBase ABC, 5 negotiation styles
│   ├── session.py      # Session lifecycle, threading locks, auto-complete at MAX_ROUNDS
│   ├── persona.py      # 22 persona templates across 10 scenarios, opponent tuner sliders
│   ├── scorer.py       # 6-dimension scoring (Opening, Info Gathering, Concession, BATNA, Emotional, Value Creation)
│   ├── debrief.py      # "What They Were Thinking" — reconstructs hidden opponent state per turn
│   ├── playbook.py     # Negotiation cheat sheet generator (pre-session and post-session modes)
│   ├── offer_analyzer.py  # 7 role categories × 5 levels, 20+ locations, 2026 benchmarks
│   ├── challenges.py   # 30 daily challenges across 6 tactical categories
│   ├── earnings.py     # Lifetime earnings calculator with compound interest
│   ├── email_audit.py  # Negotiation email auditor (8 checks, 0-100 scoring)
│   └── store.py        # JSON file persistence, atomic writes, threading locks, corrupt file recovery
static/
├── index.html          # Full SPA: landing, demo, chat, scorecard, debrief, playbook, analyzer, tuner, history, challenges, earnings, email audit
└── privacy.html        # GDPR-compliant privacy policy
tests/                  # 12 test files, 310 tests
docs/                   # 40+ audit reports, guides, deployment docs
deploy.sh               # 757-line all-in-one UpCloud deployment script (10 phases)
scripts/backup.sh       # Hourly encrypted S3 backups with Telegram alerts
scripts/restore.sh      # Point-in-time restore
```

---

## 10 Scenario Types

salary, freelance, rent, medical_bill, car_buying, scope_creep, raise, vendor, counter_offer, budget_request

Direction-aware: salary/freelance/raise/budget_request = user wants MORE; car_buying/rent/medical_bill/vendor = user wants LESS. This affects concession detection, scoring, persona difficulty, and debrief calculations.

---

## Key Bugs Already Fixed (don't re-introduce)

1. **Admin key moved from URL query param to Authorization header** — was in `?key=` exposing it in logs
2. **Direction awareness** — `_user_wants_more()` helper propagated to simulator, scorer, debrief, persona
3. **Opponent text mutation order** — `_render_opponent_response` now passes `prev_opponent_offer` as parameter
4. **User hardening ≠ concession** — moving AWAY from opponent no longer counts as concession
5. **Auto-complete at MAX_ROUNDS** — sets `agreed_value` to midpoint, not None
6. **Session status bug** — `api_get_session` returned persona name instead of lifecycle status
7. **f-string bug** — `corporate_manager` scope-creep template was missing `f` prefix
8. **Rate limiter `defaultdict` bug** — changed to plain `dict` with 10K IP cap
9. **CORS env var** — code reads `DEALSIM_CORS_ORIGINS` (matching configs)
10. **XSS in admin dashboard** — `html.escape()` on all dynamic values
11. **Offer parser** — handles "Base:", "Sign-on:", hourly rates, "150K" format, bi-weekly/monthly
12. **Playbook endpoint** — no longer calls `complete_session()` as side effect
13. **Debrief guard** — returns 409 if session still active
14. **Google Fonts removed** — system font stack (German GDPR compliance)
15. **Opponent tuner sliders** — `opponent_params` field wired through to persona generation
16. **All 10 scenarios** — dropdown expanded from 2 to 10

---

## Deployment Target

**UpCloud VPS:**
- IP: `94.237.87.238`
- OS: Ubuntu 24.04 LTS
- Specs: 2 CPU / 8GB RAM (Frankfurt, de-fra1)
- Estimated usage: ~830MB RAM, handles ~200 concurrent users
- Claude Code cannot SSH — user must `scp` and run manually

**Deployment steps:**
```bash
# From local machine — upload the entire dealsim folder
scp -r "D:\Claude Base\easy_access\dealsim" root@94.237.87.238:/opt/

# Or just the deploy script
scp deploy.sh root@94.237.87.238:~

# On the server
ssh root@94.237.87.238
export DEALSIM_DOMAIN="your-domain.com"
export DEALSIM_EMAIL="your@email.com"
bash deploy.sh
```

The deploy.sh script handles: Docker install, firewall (ufw), SSL (certbot), nginx config, Docker build, backup cron, monitoring (Dozzle), and prints the admin key at the end.

---

## Launch Readiness: B+ Grade

### Must-Fix Before Launch (from 32-agent audit)

| ID | Issue | Status |
|----|-------|--------|
| MF-1 | Admin key in URL query param | ✅ FIXED — moved to Authorization header |
| MF-2 | Single-worker constraint | ⚠️ DOCUMENTED — `--workers 1` is set, don't increase without Redis |
| MF-3 | No Content-Security-Policy header | ❌ TODO — add CSP to nginx config |
| MF-4 | Rate limiter unbounded memory | ✅ FIXED — 10K IP hard cap added |
| MF-5 | `YOUR_DOMAIN` placeholder in nginx | ⚠️ BY DESIGN — deploy.sh replaces at deploy time |

### Known Technical Debt (Post-Launch)

1. **`_persist_all()` O(n) bottleneck** — serializes ALL sessions on every write. Fine for <100 concurrent, needs per-session files or Redis beyond that.
2. **Scoring has salary-biased keywords** — some scoring heuristics don't apply well to 5/10 scenario types.
3. **7 dead API endpoints** — never called from frontend (analytics, some tool endpoints).
4. **No structured JSON logging** — plaintext logs, harder to search in production.
5. **No metrics endpoint** — no Prometheus/StatsD integration.
6. **Tailwind CDN dependency** — should bundle locally for reliability.
7. **Mobile responsiveness** — slider thumbs too small on mobile, iOS keyboard issues.
8. **Test coverage 29% at endpoint level** — core logic well-tested, API routes less so.
9. **No session expiry background task** — sessions only cleaned on file load.
10. **`user_id` field no character validation** — could inject newlines into JSONL files.

---

## Business Strategy

- **B2C:** $29/report one-time
- **B2B2C:** Career coaches $99/mo
- **B2B Enterprise:** $199/seat
- **Data marketplace:** Recruiter intelligence feed $299/mo
- **Distribution:** Reddit r/cscareerquestions first → Product Hunt → LinkedIn content → career coach partnerships
- **Chrome extension** as distribution layer (future)
- **The 10x Feature (not yet built):** Negotiation Strategy Engine with Behavioral Memory — remembers patterns across sessions, detects weaknesses, computes Pareto-optimal trade-offs

---

## AGPL-3.0 / MiroFish Note

MiroFish (the parent framework) is AGPL-3.0 licensed. DealSim communicates with it via REST API from separate Docker containers = NOT a derivative work. Safe for commercial use. Do not merge codebases into a single binary.

---

## What To Do Next

Pick up from here. The deployment package is ready at `D:\Claude Base\easy_access\dealsim\`. The most impactful next steps are:

1. **Deploy to UpCloud** — scp files, run deploy.sh, verify health endpoint
2. **Add CSP header** — the one remaining must-fix (MF-3)
3. **Bundle Tailwind CSS locally** — remove CDN dependency
4. **Set up UptimeRobot** — free ping on /health every 5 minutes
5. **Get first users** — share link on Reddit r/cscareerquestions with a "practice your salary negotiation" post
6. **Build the 10x feature** — Negotiation Strategy Engine with Behavioral Memory (the real moat)

Read the full audit reports in `docs/` for detailed findings. Key reports:
- `docs/LAUNCH_READINESS_REPORT.md` — overall assessment
- `docs/UPCLOUD_DEPLOY.md` — step-by-step deployment guide
- `docs/DISASTER_RECOVERY.md` — DR plan with 6 failure scenario runbooks
- `docs/COMPANY_INTERNAL.md` — 17-page technical architecture document
- `docs/INVESTOR_OVERVIEW.md` — investor-facing overview
- `docs/USER_GUIDE.md` — 11-chapter user guide
