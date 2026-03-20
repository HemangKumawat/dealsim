# DealSim — The Flight Simulator for Negotiations

Practice salary negotiations, freelance rate discussions, and business deals against calibrated AI opponents. Get scored across six dimensions with coaching tips you can actually use the next day.

**Live at [dealsim.org](https://dealsim.org)**

---

## Negotiation Engines

DealSim ships with three interchangeable negotiation engines. The system auto-selects the best available engine at session start, with graceful fallback:

| Engine | How it works | What you need |
|---|---|---|
| **Rule-Based** | Deterministic opponent logic — 5 negotiation styles × 3 pressure levels. Fast, predictable, always available. | Nothing — works out of the box |
| **LLM** | Any OpenAI-compatible API (DeepSeek, GPT-4, etc.) generates natural-language responses with offer extraction. | `LLM_API_KEY` in `.env` |
| **[MiroFish](https://github.com/mirofish-io/mirofish)** | Multi-agent AI simulation engine. Each opponent is a persistent AI agent with memory, personality, and strategic reasoning across turns. The most realistic negotiation experience. | MiroFish Docker container |

### How MiroFish Powers DealSim

[MiroFish](https://github.com/mirofish-io/mirofish) is an open-source multi-agent simulation engine (AGPL-3.0). DealSim uses it to create opponents that *think* rather than follow scripts:

1. **Session starts** → DealSim creates a MiroFish project with the opponent's personality, constraints, and negotiation style baked into a system prompt
2. **Each turn** → Your message is sent to MiroFish's `/api/simulation/interview` endpoint. The AI agent processes it with full conversation memory and responds in character
3. **Offer extraction** → DealSim parses dollar amounts from the natural language response and tracks the concession pattern
4. **Move classification** → Word-boundary regex classifies each response as a counter-offer, acceptance, rejection, or question — with negative-pattern guards to prevent false positives (e.g., "not done" won't trigger acceptance)
5. **Graceful fallback** → If MiroFish is unreachable mid-conversation, DealSim falls back to the rule-based engine seamlessly. The user never sees an error.

The opponent's personality parameters (aggressiveness, patience, flexibility) map directly to MiroFish agent configuration, so the same persona definitions work across all three engines.

```
Fallback chain:  MiroFish → LLM → Rule-Based
```

---

## Quick Start

```bash
git clone https://github.com/HemangKumawat/dealsim.git
cd dealsim
docker compose up --build
```

App is live at `http://localhost:8000`.

Without Docker:

```bash
pip install -e .
uvicorn dealsim_mvp.app:app --reload --port 8000
```

### Enable MiroFish (optional)

```bash
# Start the MiroFish container
docker run -d -p 5001:5001 mirofish/mirofish:latest

# Tell DealSim where to find it
echo "MIROFISH_BASE_URL=http://localhost:5001" >> .env
```

DealSim auto-detects the running MiroFish instance and promotes it to the primary engine.

---

## What It Does

You pick a scenario — salary negotiation, freelance rate, rent, car buying, medical bill, or a raise conversation. DealSim assigns you an AI opponent with a hidden reservation price, a negotiating style, and pressure level you can't see. You negotiate in a chat interface. When you finish, you get a six-dimension scorecard showing exactly where you left money on the table and why.

**Engine selection**: Choose your opponent engine per session — rule-based for practice, LLM for natural conversation, or MiroFish for the full multi-agent experience. The frontend shows which engine is active with a live badge.

**Opponent tuning**: Adjust aggressiveness, patience, flexibility, and market pressure via sliders before starting. These parameters shape the opponent's behavior regardless of which engine runs underneath.

---

## Architecture Overview

```
Browser (single-page HTML + Tailwind CSS)
        │
        │  REST JSON
        ▼
FastAPI app (app.py)
  ├── api/routes.py            — endpoints, request validation, engine selection
  ├── core/engine_factory.py   — engine auto-detection and fallback chain
  ├── core/simulator.py        — SimulatorBase ABC + RuleBasedSimulator
  ├── core/llm_simulator.py    — LLM engine (OpenAI-compatible APIs)
  ├── core/mirofish.py         — MiroFish multi-agent engine
  ├── core/mirofish_client.py  — async HTTP client with retry/backoff
  ├── core/mirofish_config.py  — MiroFish connection config (env-validated)
  ├── core/session.py          — session lifecycle, TTL cleanup, persistence
  ├── core/scorer.py           — six-dimension scorecard generator
  ├── core/persona.py          — opponent personality profiles
  ├── api/offer_analyzer.py    — standalone offer analysis tool
  ├── api/debrief.py           — post-sim opponent reveal + playbook
  ├── api/analytics.py         — score history, challenges, pattern detection
  ├── analytics.py             — event tracking (JSONL)
  ├── feedback.py              — feedback collection
  └── monitoring.py            — request logging, error tracking
```

**Engine factory** (`core/engine_factory.py`): Auto-detects available engines at startup via health probes. Builds per-session simulator instances for stateful engines (MiroFish) while sharing stateless ones (rule-based, LLM).

**MiroFish client** (`core/mirofish_client.py`): Async HTTP client with configurable retry attempts, exponential backoff, and timeout handling. Communicates with MiroFish's REST API — no SDK dependency.

**Session lifecycle** (`core/session.py`): Background cleanup task expires idle sessions every 5 minutes (configurable TTL). MiroFish sessions get proper cleanup — stopping the simulation and releasing server-side resources.

**Frontend** (`static/`): Single `index.html` with independent JS modules. Engine selector, opponent parameter sliders, live engine badge, and a "How it works" section explaining the three engines.

**Theme system**: Three switchable themes — Arena (dark), Coach (purple/gold), Lab (blue). Persisted in `localStorage`.

**Gamification**: XP, levels, streaks, and 12 achievements. Completely client-side.

**Data persistence**: File-based JSONL only. No database required.

---

## Deployment

Production stack: nginx (SSL + rate limiting) → FastAPI app → certbot (auto-renewal).

```bash
cp .env.example .env
# edit .env — set DEALSIM_ADMIN_KEY, DEALSIM_DOMAIN, DEALSIM_EMAIL
docker compose -f docker-compose.production.yml up -d --build
```

Rolling updates with zero downtime:

```bash
cd /opt/dealsim && bash scripts/deploy.sh
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DEALSIM_ENV` | `production` | `production` or `development` |
| `DEALSIM_WORKERS` | `2` | Uvicorn worker count |
| `DEALSIM_CORS_ORIGINS` | *(required)* | Comma-separated allowed origins |
| `DEALSIM_ADMIN_KEY` | *(required)* | Admin endpoint key — `openssl rand -hex 32` |
| `DEALSIM_MAX_SESSIONS` | `1000` | Max concurrent in-memory sessions |
| `DEALSIM_SESSION_TTL_HOURS` | `1` | Idle session expiry |
| `DEALSIM_DOMAIN` | *(required for SSL)* | Public domain name |
| `DEALSIM_EMAIL` | *(required for SSL)* | Let's Encrypt contact |
| **LLM Engine** | | |
| `DEALSIM_USE_LLM` | `false` | Enable LLM negotiation engine |
| `LLM_API_KEY` | — | DeepSeek / OpenAI API key |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | API endpoint |
| `LLM_MODEL` | `deepseek-chat` | Model identifier |
| **MiroFish Engine** | | |
| `MIROFISH_BASE_URL` | — | MiroFish container URL (e.g., `http://localhost:5001`) |
| `MIROFISH_TIMEOUT` | `30.0` | HTTP request timeout (seconds) |
| `MIROFISH_RETRY_ATTEMPTS` | `3` | Retry count on failure |
| `MIROFISH_RETRY_BACKOFF` | `1.5` | Exponential backoff base |

Full reference: `.env.example`

---

## API Overview

Interactive docs at `/docs` (Swagger) and `/redoc` when the server is running.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/sessions` | Start a negotiation (accepts `engine`, `user_params`, `opponent_params`) |
| `POST` | `/api/sessions/{id}/message` | Send a message |
| `POST` | `/api/sessions/{id}/complete` | End and get scorecard |
| `GET` | `/api/sessions/{id}` | Session state and transcript |
| `GET` | `/api/sessions/{id}/debrief` | Opponent hidden state reveal |
| `GET` | `/api/sessions/{id}/playbook` | Printable negotiation cheat sheet |
| `POST` | `/api/offers/analyze` | Analyze any offer against market data |
| `GET` | `/api/market-data/{role}/{location}` | Market benchmarks |
| `GET` | `/api/users/{id}/history` | Score history |
| `GET` | `/api/users/{id}/patterns` | Cross-session behavioral patterns |
| `GET` | `/api/challenges/today` | Daily challenge |
| `POST` | `/api/challenges/today/submit` | Submit challenge result |
| `POST` | `/api/tools/earnings-calculator` | Lifetime earnings impact |
| `POST` | `/api/tools/audit-email` | Audit a negotiation email thread |
| `POST` | `/api/feedback` | Submit session feedback |
| `GET` | `/health` | Health check (includes `available_engines`, `simulator_engine`) |
| `GET` | `/admin/stats` | Admin dashboard (auth required) |

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

## Tests

```bash
pip install -e ".[dev]"
pytest
```

472 tests covering all three engines, session lifecycle, scoring, API validation, and MiroFish fallback behavior.

---

## Contributing

**Adding a scenario** — extend `_ALLOWED_SCENARIO_TYPES` in `api/routes.py` and add a persona template in `core/persona.py`.

**Adding a negotiation engine** — subclass `SimulatorBase` in `core/simulator.py`, implement `opening_statement()` and `generate_response()`, register it in `engine_factory.py`.

**Adjusting opponent behavior** — persona parameters (`aggressiveness`, `patience`, `flexibility`, `knowledge`, `emotion`, `budget`) are validated 0–100 and flow through to all engines via `opponent_params`.

---

## Built With

- [FastAPI](https://fastapi.tiangolo.com/) — async Python web framework
- [MiroFish](https://github.com/mirofish-io/mirofish) — multi-agent AI simulation engine
- [Tailwind CSS](https://tailwindcss.com/) — utility-first CSS
- [httpx](https://www.python-httpx.org/) — async HTTP client

## License

Proprietary. All rights reserved.
