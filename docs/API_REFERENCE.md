# DealSim API Reference

Version `0.1.0` — FastAPI / Python 3.10+

---

## Overview

DealSim exposes a REST API under the `/api` prefix. All request and response bodies are JSON. The interactive OpenAPI UI is available at `/docs` and the machine-readable schema at `/openapi.json` (both served by FastAPI automatically when the server is running).

Base URL (local): `http://localhost:8000`

### Tags summary

| Tag | Purpose |
|---|---|
| `sessions` | Run a live negotiation simulation |
| `debrief` | Post-session analysis and coaching playbook |
| `offers` | Analyse a job offer and look up salary benchmarks |
| `users` | Per-user score history and behavioural patterns |
| `challenges` | Daily micro-challenge (one per day, date-seeded) |
| `feedback` | Submit a star rating + comment |
| `analytics` | Track custom usage events |
| `tools` | Standalone calculators (earnings, email audit) |
| `admin` | Protected aggregate stats dashboard |
| `system` | Health check |

---

## Authentication

Most endpoints require **no authentication**.

### Admin endpoints

`GET /api/admin/stats` and `GET /admin/stats` require the server-side `DEALSIM_ADMIN_KEY` environment variable to be set. Provide the key in the `Authorization` header:

```
Authorization: <key>
# or
Authorization: Bearer <key>
```

Both forms are accepted. If `DEALSIM_ADMIN_KEY` is not configured, the endpoints return `503`.

---

## Rate Limiting

Every request (except `GET /health`) is subject to an **in-memory per-IP rate limit**.

- Default: **100 requests per minute per IP**
- Configurable via the `RATE_LIMIT_PER_MINUTE` environment variable
- Supports `X-Forwarded-For` for deployments behind a reverse proxy

When the limit is exceeded the server responds:

```json
HTTP 429
{"detail": "Rate limit exceeded. Max 100 requests per minute."}
```

---

## Error Codes

| HTTP Status | Meaning |
|---|---|
| `400` | Bad request — validation error or invalid session ID format |
| `403` | Forbidden — wrong or missing admin key |
| `404` | Not found — session or market data entry does not exist |
| `409` | Conflict — session state mismatch (e.g. session still active, or already ended) |
| `422` | Unprocessable entity — Pydantic validation failure (wrong field types, out-of-range values) |
| `429` | Rate limit exceeded |
| `500` | Internal server error (internals never leaked to the client) |
| `503` | Service unavailable — feature disabled by missing env var |

All error bodies follow the FastAPI convention:

```json
{"detail": "<human-readable message>"}
```

---

## System

### `GET /health`

Health check. Exempt from rate limiting.

**Response `200`**

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

## Sessions

Sessions represent a single live negotiation. The flow is:

1. `POST /api/sessions` — create a session, get the opponent's opening message
2. `POST /api/sessions/{session_id}/message` — exchange messages in a loop
3. `POST /api/sessions/{session_id}/complete` — end the session and receive the scorecard
4. `GET /api/sessions/{session_id}/debrief` — reveal the opponent's hidden state and move analysis
5. `GET /api/sessions/{session_id}/playbook` — personalised coaching recommendations

Session IDs are UUID4 strings. Every endpoint that accepts a `session_id` validates that format and returns `400` if it does not match.

---

### `POST /api/sessions`

Start a new negotiation simulation.

**Request body**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `scenario_type` | string | no | `"salary"` | See `GET /api/scenarios` for available types |
| `target_value` | number (float, > 0) | **yes** | — | The user's goal value (e.g. `120000` for a salary) |
| `difficulty` | string | no | `"medium"` | `"easy"` \| `"medium"` \| `"hard"` |
| `context` | string | no | `""` | Free-text context (max 500 chars). E.g. `"Senior engineer at a Series B startup"` |
| `user_id` | string | no | `""` | Opaque user identifier for history tracking |
| `opponent_params` | object \| null | no | `null` | Slider overrides for opponent persona tuning |

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "salary",
    "target_value": 130000,
    "difficulty": "medium",
    "context": "Senior engineer role at a startup",
    "user_id": "user_abc123"
  }'
```

**Response `201`**

| Field | Type | Notes |
|---|---|---|
| `session_id` | string (UUID4) | Use in all subsequent calls |
| `opponent_name` | string | Generated persona name |
| `opponent_role` | string | E.g. `"HR Manager"` |
| `opening_message` | string | The opponent's first message |
| `opening_offer` | number \| null | Numeric offer if the opponent leads with one |

```json
{
  "session_id": "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
  "opponent_name": "Sarah Chen",
  "opponent_role": "HR Manager",
  "opening_message": "Thanks for coming in. We'd like to offer you $110,000.",
  "opening_offer": 110000.0
}
```

**Errors:** `422` (validation), `500` (session creation failure)

---

### `POST /api/sessions/{session_id}/message`

Send a negotiation message and receive the opponent's response.

**Path parameter:** `session_id` (UUID4)

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `message` | string (1–2000 chars) | **yes** | The user's negotiation message |

```bash
curl -X POST http://localhost:8000/api/sessions/a1b2c3d4-e5f6-4789-abcd-ef1234567890/message \
  -H "Content-Type: application/json" \
  -d '{"message": "I was thinking around $135,000 based on my research into market rates."}'
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `opponent_response` | string | The opponent's reply |
| `opponent_offer` | number \| null | Numeric counter-offer if present |
| `round_number` | integer | Current exchange count |
| `resolved` | boolean | `true` when agreement or walkaway is reached |
| `agreed_value` | number \| null | Final agreed value if `resolved` is `true` |
| `session_status` | string | `"active"` \| `"completed"` \| `"abandoned"` |

```json
{
  "opponent_response": "That's a bit high for us. We could go to $118,000.",
  "opponent_offer": 118000.0,
  "round_number": 2,
  "resolved": false,
  "agreed_value": null,
  "session_status": "active"
}
```

**Errors:** `400` (invalid session ID), `404` (session not found), `409` (session not active)

---

### `POST /api/sessions/{session_id}/complete`

End the negotiation and generate a scorecard. Can be called at any point in an active session.

**Path parameter:** `session_id` (UUID4)

**Query parameter**

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `user_id` | string | no | `""` | If provided, the result is saved to user history |

```bash
curl -X POST "http://localhost:8000/api/sessions/a1b2c3d4-e5f6-4789-abcd-ef1234567890/complete?user_id=user_abc123"
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `overall_score` | integer (0–100) | Composite negotiation score |
| `dimensions` | array of objects | Per-dimension breakdown (see below) |
| `top_tips` | array of strings | Top 3 actionable tips |
| `outcome` | string | E.g. `"deal_reached"` or `"walkaway"` |
| `agreed_value` | number \| null | Final agreed value if a deal was reached |
| `opponent_name` | string | Opponent persona name |

Each object in `dimensions`:

| Field | Type |
|---|---|
| `name` | string |
| `score` | integer |
| `weight` | number |
| `explanation` | string |
| `tips` | array of strings |

```json
{
  "overall_score": 74,
  "dimensions": [
    {
      "name": "anchoring",
      "score": 85,
      "weight": 0.25,
      "explanation": "Strong opening anchor 18% above opponent.",
      "tips": ["Next time, hold your anchor for at least one full round."]
    }
  ],
  "top_tips": ["Use decreasing concession steps next time."],
  "outcome": "deal_reached",
  "agreed_value": 126000.0,
  "opponent_name": "Sarah Chen"
}
```

**Errors:** `400` (invalid session ID), `404` (session not found)

---

### `GET /api/sessions/{session_id}`

Retrieve current session state and full transcript.

**Path parameter:** `session_id` (UUID4)

```bash
curl http://localhost:8000/api/sessions/a1b2c3d4-e5f6-4789-abcd-ef1234567890
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `session_id` | string | |
| `status` | string | `"active"` \| `"completed"` \| `"abandoned"` |
| `round_number` | integer | Total turns so far |
| `transcript` | array of objects | Ordered list of all turns |

Each transcript object:

| Field | Type | Notes |
|---|---|---|
| `speaker` | string | `"user"` or `"opponent"` |
| `text` | string | |
| `offer` | number \| null | Numeric offer contained in this turn, if any |

**Errors:** `400` (invalid session ID), `404` (session not found)

---

## Debrief

Debrief endpoints reveal hidden opponent state and provide coaching. Both require the session to have been completed first (status is not `"active"`).

---

### `GET /api/sessions/{session_id}/debrief`

Post-negotiation analysis: opponent's hidden targets, move-by-move commentary, and money left on the table.

**Path parameter:** `session_id` (UUID4)

```bash
curl http://localhost:8000/api/sessions/a1b2c3d4-e5f6-4789-abcd-ef1234567890/debrief
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `session_id` | string | |
| `opponent_target` | number | Opponent's ideal outcome |
| `opponent_reservation` | number | The maximum/minimum the opponent would accept |
| `opponent_pressure` | string | Opponent's urgency level: `"low"` \| `"medium"` \| `"high"` |
| `hidden_constraints` | array of strings | Constraints the opponent never revealed |
| `agreed_value` | number \| null | |
| `money_left_on_table` | number \| null | How much more was achievable |
| `optimal_outcome` | number | Best theoretically achievable value |
| `outcome_grade` | string | `"excellent"` \| `"good"` \| `"fair"` \| `"poor"` \| `"incomplete"` |
| `move_analysis` | array of `MoveAnalysisItem` | Per-turn commentary |
| `key_moments` | array of strings | Narrative highlights |
| `biggest_mistake` | string \| null | |
| `best_move` | string \| null | |

Each `MoveAnalysisItem`:

| Field | Type | Notes |
|---|---|---|
| `turn_number` | integer | |
| `speaker` | string | `"user"` or `"opponent"` |
| `move_type` | string | E.g. `"anchor"`, `"concession"`, `"question"`, `"batna_signal"`, `"acceptance"`, `"pressure"`, `"information_share"` |
| `offer` | number \| null | |
| `analysis` | string | |
| `strength` | string | `"strong"` \| `"neutral"` \| `"weak"` |
| `missed_opportunity` | string \| null | |

**Errors:** `400` (invalid ID), `404` (not found), `409` (session still active)

---

### `GET /api/sessions/{session_id}/playbook`

Personalised coaching playbook based on session performance. Can be called on active or completed sessions.

**Path parameter:** `session_id` (UUID4)

```bash
curl http://localhost:8000/api/sessions/a1b2c3d4-e5f6-4789-abcd-ef1234567890/playbook
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `session_id` | string | |
| `overall_score` | integer | |
| `style_profile` | string | E.g. `"Skilled negotiator with strong fundamentals"` |
| `strengths` | array of strings | Observed strong behaviours |
| `weaknesses` | array of strings | Observed weak behaviours |
| `recommendations` | array of `PlaybookEntryItem` | Ranked recommendations |
| `practice_scenarios` | array of strings | Suggested next practice sessions |

Each `PlaybookEntryItem`:

| Field | Type | Notes |
|---|---|---|
| `category` | string | E.g. `"anchoring"`, `"leverage"`, `"concessions"`, `"information"` |
| `title` | string | |
| `description` | string | |
| `priority` | string | `"high"` \| `"medium"` \| `"low"` |

**Errors:** `400` (invalid ID), `404` (not found)

---

## Offers

### `POST /api/offers/analyze`

Parse a free-text job offer and return market positioning, negotiability scores, counter strategies, and key insights. If `role` and `location` are both provided, the base salary component is enriched with a market position signal.

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `offer_text` | string (min 5 chars) | **yes** | Free text describing the offer |
| `role` | string | no | Role slug (see role aliases below) |
| `location` | string | no | Location slug (see location aliases below) |

```bash
curl -X POST http://localhost:8000/api/offers/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "offer_text": "Base salary $130k, 15% annual bonus, 10k signing bonus, 4 weeks PTO",
    "role": "software_engineer",
    "location": "san_francisco"
  }'
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `components` | array of `OfferComponentItem` | Parsed offer components |
| `overall_market_position` | string | `"below_market"` \| `"at_market"` \| `"above_market"` \| `"unknown"` |
| `overall_score` | integer (0–100) | Higher is better |
| `counter_strategies` | array of `CounterStrategyItem` | Ranked strategies at different risk levels |
| `key_insights` | array of strings | Actionable observations |

Each `OfferComponentItem`:

| Field | Type | Notes |
|---|---|---|
| `name` | string | E.g. `"base_salary"`, `"signing_bonus"`, `"equity"`, `"annual_bonus"`, `"pto"`, `"remote"` |
| `value` | string | Human-readable value |
| `numeric_value` | number \| null | Parsed dollar value where applicable |
| `negotiability` | string | `"high"` \| `"medium"` \| `"low"` \| `"fixed"` |
| `market_position` | string \| null | `"below"` \| `"at"` \| `"above"` — only populated when market data is available |
| `notes` | string | Additional notes |

Each `CounterStrategyItem`:

| Field | Type | Notes |
|---|---|---|
| `name` | string | Strategy name |
| `description` | string | |
| `suggested_counter` | string | Concrete counter-offer suggestion |
| `risk_level` | string | `"low"` \| `"medium"` \| `"high"` |
| `rationale` | string | Why this strategy works |

---

### `GET /api/market-data/{role}/{location}`

Return salary percentile benchmarks for a role and location. Data is bundled (no external API calls); vintage is 2026-Q1.

**Path parameters**

| Parameter | Notes |
|---|---|
| `role` | Role slug or alias (see table below) |
| `location` | Location slug or alias (see table below) |

```bash
curl http://localhost:8000/api/market-data/software_engineer/san_francisco
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `role` | string | Normalised role key |
| `location` | string | Normalised location key |
| `p25` | number | 25th percentile annual salary (USD) |
| `p50` | number | Median |
| `p75` | number | 75th percentile |
| `p90` | number | 90th percentile |
| `source` | string | Data provenance note |

```json
{
  "role": "software_engineer",
  "location": "san_francisco",
  "p25": 182520.0,
  "p50": 217620.0,
  "p75": 259740.0,
  "p90": 294840.0,
  "source": "DealSim bundled BLS/H1B approximations (2026-Q1)"
}
```

**Errors:** `404` — no data for that role/location combination. The error body includes a list of available roles.

#### Available roles

| API slug | Aliases accepted |
|---|---|
| `software_engineer` | `swe`, `sde`, `developer`, `engineer`, `senior_engineer`, `senior_swe`, `staff_engineer` |
| `product_manager` | `pm`, `product` |
| `data_scientist` | `ds`, `ml_engineer` |
| `data_engineer` | `data_eng` |
| `devops_sre` | `devops`, `sre` |
| `engineering_manager` | `eng_manager` |
| `designer` | `ux_designer`, `ui_designer` |
| `marketing_manager` | `marketing` |
| `sales_representative` | — |
| `general` | — |

#### Available locations (with multiplier vs national baseline)

| Slug | Aliases | Multiplier |
|---|---|---|
| `san_francisco` | `sf`, `bay_area`, `silicon_valley` | 1.30× |
| `new_york` | `nyc`, `manhattan` | 1.25× |
| `seattle` | `sea` | 1.15× |
| `boston` | — | 1.15× |
| `los_angeles` | — | 1.12× |
| `washington_dc` | — | 1.10× |
| `san_diego` | — | 1.08× |
| `miami` | — | 1.08× |
| `portland` | — | 1.05× |
| `raleigh` | — | 0.98× |
| `philadelphia` | — | 1.02× |
| `austin` | `atx` | 1.00× |
| `denver` | — | 1.00× |
| `chicago` | `chi` | 0.95× |
| `atlanta` | — | 0.95× |
| `dallas` | — | 0.92× |
| `houston` | — | 0.92× |
| `pittsburgh` | — | 0.94× |
| `remote` | — | 1.00× |
| `national` | `us`, `usa`, `united_states` | 1.00× |

---

## Users

User data is stored locally in JSONL files. There is no account system — the `user_id` is an opaque string you provide.

### `GET /api/users/{user_id}/history`

Score history across all completed sessions for a user.

```bash
curl http://localhost:8000/api/users/user_abc123/history
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `user_id` | string | |
| `total_sessions` | integer | |
| `sessions` | array of objects | Raw session summaries |
| `average_score` | number | |
| `best_score` | integer | |
| `worst_score` | integer | |
| `score_trend` | string | `"improving"` \| `"stable"` \| `"declining"` \| `"insufficient_data"` |
| `favorite_scenario` | string \| null | Most-played scenario type |

Returns an empty history (not `404`) when the user has no sessions.

---

### `GET /api/users/{user_id}/patterns`

Detect recurring negotiation strengths and weaknesses from session history. Requires at least 2 completed sessions.

```bash
curl http://localhost:8000/api/users/user_abc123/patterns
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `user_id` | string | |
| `sessions_analyzed` | integer | |
| `patterns` | array of `PatternItem` | |
| `style_profile` | string | Plain-English summary |
| `top_strength` | string \| null | Best-scoring dimension name |
| `top_weakness` | string \| null | Worst-scoring dimension name |

Each `PatternItem`:

| Field | Type | Notes |
|---|---|---|
| `name` | string | Pattern label |
| `description` | string | |
| `frequency` | string | `"always"` \| `"often"` |
| `impact` | string | `"positive"` \| `"negative"` |
| `recommendation` | string | |

---

## Challenges

One challenge is active per calendar day. The challenge is determined deterministically from the date (MD5 hash of `YYYY-MM-DD`), so every user sees the same challenge on any given day.

### `GET /api/challenges/today`

Retrieve today's micro-challenge.

```bash
curl http://localhost:8000/api/challenges/today
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `id` | string | Challenge identifier |
| `title` | string | |
| `description` | string | |
| `scenario_prompt` | string | The situation the user must respond to |
| `scoring_criteria` | array of strings | Criteria checked during scoring |
| `max_score` | integer | Always `100` |
| `category` | string | E.g. `"anchoring"`, `"leverage"`, `"information"`, `"concessions"`, `"value_creation"`, `"emotional_control"`, `"communication"` |
| `date` | string | ISO date string (`YYYY-MM-DD`) |

---

### `POST /api/challenges/today/submit`

Submit a text response to today's challenge and receive an automated score.

**Request body**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `user_id` | string | no | `"anonymous"` | Stored with the submission |
| `response` | string (min 5 chars) | **yes** | — | The user's written response |

```bash
curl -X POST http://localhost:8000/api/challenges/today/submit \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_abc123",
    "response": "Based on my research, I believe $135,000 reflects the current market rate for this role in San Francisco. I have a competing offer at a similar level."
  }'
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `total` | integer | Total score out of `max_score` |
| `breakdown` | array of `CriterionBreakdown` | Per-criterion result |
| `challenge` | object | Full challenge object (same shape as `GET /api/challenges/today`) |

Each `CriterionBreakdown`:

| Field | Type |
|---|---|
| `criterion` | string |
| `met` | boolean |
| `score` | integer |
| `max` | integer |

---

## Feedback

### `POST /api/feedback`

Submit a star rating and optional comment for a completed session. Stored locally; no third-party service.

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string | **yes** | Session that generated the feedback |
| `rating` | integer (1–5) | **yes** | Star rating |
| `comment` | string | no | Max 1000 chars |
| `email` | string | no | Max 200 chars; only stored if provided |
| `final_score` | integer \| null | no | Negotiation score for context |
| `scenario_type` | string \| null | no | E.g. `"salary"` |

```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
    "rating": 5,
    "comment": "Loved the debrief feature.",
    "final_score": 74,
    "scenario_type": "salary"
  }'
```

**Response `200`**

```json
{"status": "ok", "message": "Thank you for your feedback!"}
```

---

## Analytics

### `POST /api/events`

Track a custom usage event. All events are stored locally (JSONL); no PII is expected.

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_type` | string | **yes** | Must be one of the allowed values (see below) |
| `properties` | object | no | Arbitrary key-value pairs |

**Allowed `event_type` values:**

`session_created`, `simulation_completed`, `score_viewed`, `feedback_submitted`, `page_view`, `debrief_viewed`, `playbook_generated`, `offer_analyzed`, `challenge_completed`, `feature_used`, `message_sent`, `email_audited`, `earnings_calculated`

```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{"event_type": "page_view", "properties": {"page": "landing"}}'
```

**Response `200`**

```json
{"status": "ok"}
```

**Errors:** `400` — unknown event type

---

## Tools

### `POST /api/tools/earnings-calculator`

Calculate the lifetime earnings impact of negotiating a higher salary. Uses 3% compounding annual raises over a 30-year career.

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `current_offer` | number (> 0) | **yes** | The offer on the table |
| `negotiated_offer` | number (> 0) | **yes** | The outcome after negotiation |

```bash
curl -X POST http://localhost:8000/api/tools/earnings-calculator \
  -H "Content-Type: application/json" \
  -d '{"current_offer": 110000, "negotiated_offer": 125000}'
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `current_offer` | number | |
| `negotiated_offer` | number | |
| `difference_annual` | number | Year-one difference |
| `difference_5yr` | number | 5-year compounded total |
| `difference_10yr` | number | 10-year compounded total |
| `difference_career` | number | 30-year compounded total |
| `compounding_note` | string | Human-readable summary |

```json
{
  "current_offer": 110000.0,
  "negotiated_offer": 125000.0,
  "difference_annual": 15000.0,
  "difference_5yr": 79546.27,
  "difference_10yr": 172935.52,
  "difference_career": 714905.85,
  "compounding_note": "A $15,000/yr increase compounds to $714,905 over a 30-year career (assuming 3% annual raises)."
}
```

---

### `POST /api/tools/audit-email`

Score a negotiation email draft for tone, language discipline, and structural effectiveness.

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `email_text` | string (min 10 chars) | **yes** | Full draft email text |

```bash
curl -X POST http://localhost:8000/api/tools/audit-email \
  -H "Content-Type: application/json" \
  -d '{"email_text": "Thank you for the offer of $105,000. Based on market data for this role in SF, I was hoping we could discuss $125,000."}'
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `overall_score` | integer (0–100) | |
| `tone` | string | Plain-English tone assessment |
| `strengths` | array of strings | |
| `issues` | array of strings | |
| `suggestions` | array of strings | |
| `rewrite_hints` | array of strings | Specific phrase replacements |

---

## Utility

### `GET /api/scenarios`

List all available negotiation scenario types.

```bash
curl http://localhost:8000/api/scenarios
```

**Response `200`** — array of scenario objects

| Field | Type | Notes |
|---|---|---|
| `type` | string | Pass this as `scenario_type` in `POST /api/sessions` |
| `name` | string | Display name |
| `description` | string | |
| `default_target` | number | Suggested starting `target_value` |
| `difficulties` | array of strings | Always `["easy", "medium", "hard"]` |

Current scenario types: `salary`, `freelance`, `rent`, `medical_bill`, `car_buying`, `scope_creep`, `raise`, `vendor`, `counter_offer`, `budget_request`.

---

## Admin

Both admin endpoints require the `Authorization` header (see Authentication section).

### `GET /api/admin/stats`

JSON aggregate statistics. Returns analytics and feedback summary combined.

```bash
curl http://localhost:8000/api/admin/stats \
  -H "Authorization: Bearer <your-admin-key>"
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `total_sessions` | integer | |
| `total_completed` | integer | |
| `total_messages` | integer | |
| `completion_rate` | number | Percentage |
| `average_score` | number | |
| `feature_usage` | object | Feature name → count |
| `feature_usage_order` | array of strings | Features sorted most → least used |
| `scenario_popularity` | object | Scenario type → count |
| `score_distribution` | object | Score bucket → count |
| `daily_active_sessions` | array of objects | Last 30 days: `{"date": "YYYY-MM-DD", "sessions": N}` |
| `feedback.total_feedback` | integer | |
| `feedback.average_rating` | number | |
| `feedback.rating_distribution` | object | Star level → count |
| `feedback.recent_comments` | array of objects | Last 20 comments with rating and timestamp |
| `feedback.feedback_with_email_count` | integer | |
| `feedback.feedback_with_comment_count` | integer | |

**Errors:** `403` (wrong key), `503` (admin key not configured)

### `GET /admin/stats`

HTML version of the same data, rendered as a browser dashboard. Same authentication. Not included in the OpenAPI schema.

---

## Static and Utility Pages

These are served from the `static/` directory when it is present and are not part of the API schema.

| Path | Notes |
|---|---|
| `GET /` | Frontend SPA (`index.html`) |
| `GET /privacy` | Privacy policy page (`static/privacy.html`) |

---

## WebSocket Protocol

There is no WebSocket interface. All real-time negotiation state is managed through the synchronous REST session endpoints.

---

## OpenAPI / Interactive Docs

FastAPI generates and serves these automatically:

| URL | Description |
|---|---|
| `/docs` | Swagger UI — interactive browser-based API explorer |
| `/redoc` | ReDoc — alternative API reference renderer |
| `/openapi.json` | Raw OpenAPI 3.x schema (JSON) |

These are the authoritative machine-readable source of truth. The endpoints, models, and validation rules shown here are derived directly from the same Pydantic models that power those schemas.
