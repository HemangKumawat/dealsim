# DealSim — The Flight Simulator for Negotiations

Practice salary negotiations, freelance rate discussions, and business deals against calibrated AI opponents. Get scored across six dimensions with coaching tips you can actually use the next day.

![DealSim screenshot placeholder — add a screenshot here](docs/screenshot.png)

---

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/dealsim.git
cd dealsim
docker compose up --build
```

App is live at `http://localhost:8000`.

Without Docker:

```bash
pip install -e .
uvicorn dealsim_mvp.app:app --reload --port 8000
```

---

## What It Does

You pick a scenario — salary negotiation, freelance rate, rent, car buying, medical bill, or a raise conversation. DealSim assigns you an AI opponent with a hidden reservation price, a negotiating style, and pressure level you can't see. You negotiate in a chat interface. When you finish, you get a six-dimension scorecard showing exactly where you left money on the table and why.

The opponent's behavior is rule-based and swappable — the engine is built as an abstract interface, so plugging in a real LLM is a one-file change.

---

## Architecture Overview

```
Browser (single-page HTML + Tailwind CSS)
        │
        │  REST JSON
        ▼
FastAPI app (app.py)
  ├── api/routes.py          — all endpoints
  ├── core/session.py        — session lifecycle, JSON persistence
  ├── core/simulator.py      — rule-based negotiation engine (5 styles × 3 pressure levels)
  ├── core/scorer.py         — six-dimension scorecard generator
  ├── core/persona.py        — opponent personality profiles
  ├── api/offer_analyzer.py  — standalone offer analysis tool
  ├── api/debrief.py         — post-sim opponent reveal + playbook generator
  ├── api/analytics.py       — score history, challenge engine, pattern detection
  ├── analytics.py           — event tracking (JSONL)
  ├── feedback.py            — feedback collection
  └── monitoring.py          — request logging, error tracking
```

**Frontend** (`static/`) is a single `index.html` plus a set of independent JS modules loaded via `<script>` tags. No build step for the app itself — Tailwind CSS is compiled separately but the compiled file ships with the repo.

**Theme system** (`static/themes.css`, `static/theme-switcher.js`): three switchable themes — Arena (dark red), Coach (purple/gold), Lab (GitHub-dark blue) — controlled by a `data-theme` attribute on `<html>` and persisted in `localStorage`.

**Gamification** (`static/gamification.js`): XP, levels, streaks, and 12 achievements tracked in `localStorage`. Completely client-side — no server round-trips.

**Data persistence**: file-based JSON only. No database. Sessions, feedback, and analytics events write to JSONL files in `DEALSIM_DATA_DIR`. Suitable for a single-container deployment with one volume mount.

Full technical detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Deployment

The production stack is three Docker containers: nginx (SSL termination + rate limiting), the FastAPI app, and certbot (automatic certificate renewal).

```bash
cp .env.example .env
# edit .env — at minimum set DEALSIM_ADMIN_KEY, DEALSIM_CORS_ORIGINS, DEALSIM_DOMAIN
docker compose up -d --build
```

One-click cloud options (Render, Fly.io, Railway) and full VPS instructions: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DEALSIM_ENV` | `production` | `production` or `development` |
| `DEALSIM_HOST` | `0.0.0.0` | Uvicorn bind address |
| `DEALSIM_PORT` | `8000` | Internal server port |
| `DEALSIM_WORKERS` | `2` | Uvicorn worker count |
| `DEALSIM_CORS_ORIGINS` | *(required)* | Comma-separated allowed origins |
| `DEALSIM_ADMIN_KEY` | *(required)* | Key for `/admin/stats` — generate with `openssl rand -hex 32` |
| `DEALSIM_MAX_SESSIONS` | `1000` | Max concurrent in-memory sessions |
| `DEALSIM_SESSION_TTL_HOURS` | `1` | Idle session expiry |
| `DEALSIM_DATA_DIR` | `/app/data` | Where JSONL files are written |
| `DEALSIM_DOMAIN` | *(required for SSL)* | Public domain name, no scheme |
| `DEALSIM_EMAIL` | *(required for SSL)* | Let's Encrypt contact address |
| `BACKUP_DIR` | `/opt/backups/dealsim` | Local backup archive directory |
| `BACKUP_RETAIN_DAYS` | `7` | Days of backup archives to keep |
| `TELEGRAM_BOT_TOKEN` | *(optional)* | Backup alert notifications |
| `TELEGRAM_CHAT_ID` | *(optional)* | Backup alert notifications |

Full reference with explanations: `.env.example`

---

## API Overview

Interactive docs at `/docs` (Swagger) and `/redoc` when the server is running.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/sessions` | Start a negotiation |
| `POST` | `/api/sessions/{id}/message` | Send a message |
| `POST` | `/api/sessions/{id}/complete` | End and get scorecard |
| `GET` | `/api/sessions/{id}` | Get session state and transcript |
| `GET` | `/api/sessions/{id}/debrief` | Opponent hidden state reveal |
| `GET` | `/api/sessions/{id}/playbook` | Printable negotiation cheat sheet |
| `POST` | `/api/offers/analyze` | Analyze any offer against market data |
| `GET` | `/api/market-data/{role}/{location}` | Market benchmarks |
| `GET` | `/api/users/{id}/history` | Score history for a user |
| `GET` | `/api/users/{id}/patterns` | Cross-session behavioral patterns |
| `GET` | `/api/challenges/today` | Today's daily challenge |
| `POST` | `/api/challenges/today/submit` | Submit challenge result |
| `POST` | `/api/tools/earnings-calculator` | Lifetime earnings impact calculator |
| `POST` | `/api/tools/audit-email` | Audit a pasted negotiation email thread |
| `POST` | `/api/feedback` | Submit session feedback |
| `GET` | `/health` | Health check |
| `GET` | `/admin/stats` | Admin dashboard (Authorization header required) |

Full endpoint shapes with request/response schemas: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

---

## Scoring Dimensions

Each negotiation is scored 0–100 across six dimensions:

| Dimension | Weight | What it measures |
|---|---|---|
| Opening Strategy | 20% | Did you anchor first and ambitiously? |
| Information Gathering | 15% | Did you ask questions before conceding? |
| Concession Pattern | 25% | Were your concessions small and decelerating? |
| BATNA Usage | 15% | Did you reference alternatives for leverage? |
| Emotional Control | 10% | Did you stay composed under pressure? |
| Value Creation | 15% | Did you explore non-price terms? |

---

## Contributing

The codebase is intentionally small — about 3,000 lines of Python and a single-page frontend. The design principle: every module documents the rule or equation it implements, and nothing ships without a test.

**Adding a scenario** — extend `_ALLOWED_SCENARIO_TYPES` in `api/routes.py` and add a persona template in `core/persona.py`. That's it.

**Adding an opponent style** — subclass `SimulatorBase` in `core/simulator.py` and override `generate_response`. The base class is the only contract.

**Swapping in an LLM engine** — same as above. The `NegotiationPersona.to_mirofish_config()` method already generates the agent config format.

**Running tests:**

```bash
pip install -e ".[dev]"
pytest
```

**Building the CSS** (only needed if you change Tailwind classes in HTML):

```bash
npm install
npm run build:css
```

---

## License

Proprietary. All rights reserved.
