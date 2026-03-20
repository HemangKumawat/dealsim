# DealSim Scaling Analysis

**Prepared:** 2026-03-19
**Scope:** `app.py`, `core/store.py`, `core/session.py`, `Dockerfile`, `docker-compose.yml`, `analytics.py`, `feedback.py`
**Goal:** Identify bottlenecks and a prioritized action plan for 100–500 concurrent users, keeping the MVP architecture (no Postgres).

---

## Executive Summary

The current architecture is a single-worker FastAPI process backed by a JSON file for session state, a JSONL file for analytics, and a JSONL file for feedback. It will handle light traffic (≤20 concurrent users) without issue. At 100 concurrent users it hits two hard walls simultaneously: the JSON session store becomes a serialization bottleneck and the in-memory rate limiter breaks under multi-worker deployment. At 500 concurrent users, both the session store and the analytics read path collapse.

The good news: the code is well-structured for incremental improvement. The session store interface already documents the swap path to Redis. The analytics writes are append-only. No architectural rewrite is needed — four targeted changes cover 100 concurrent users completely.

---

## Current Architecture Map

```
Request
  └── uvicorn (1 worker)
        └── FastAPI middleware stack
              ├── Rate limiter  ← in-process dict
              └── API routes
                    └── session.py
                          ├── _SESSIONS dict  ← in-process dict
                          └── store.py: .dealsim_sessions.json  ← full rewrite on every turn
                    └── analytics.py
                          └── events.jsonl  ← append per request, full read for /admin/stats
                    └── feedback.py
                          └── feedback.jsonl  ← append per request, full read for /admin/stats
```

---

## Bottleneck Inventory

### B1 — Full-file JSON rewrite on every session mutation (CRITICAL)

**File:** `core/store.py`, `save_sessions()` / `_persist_all()` in `session.py`

Every call to `negotiate()`, `create_session()`, or `complete_session()` calls `_store_session()`, which calls `_persist_all()`, which serializes **all** in-memory sessions to a single JSON file with `json.dump(..., indent=2)` followed by `fsync()`.

At 100 concurrent users with ~5 turns per session active simultaneously:
- Each `negotiate()` call triggers a full serialize-all-sessions write.
- With 100 active sessions, each write serializes ~100 session objects (each containing a full transcript).
- `_store_lock` is a single `threading.Lock()` — all writes queue behind it.
- An fsync on a Docker volume (which goes through the host filesystem) takes 5–50 ms.
- 100 concurrent writes × 50 ms = requests queuing 5 seconds deep.

**At 100 users:** Response latency spikes to 2–10 seconds on every turn. Users experience the app as hanging.
**At 500 users:** The write queue never drains. The app effectively deadlocks on the lock.

### B2 — In-memory rate limiter breaks under multiple workers (CRITICAL for scaling)

**File:** `app.py`, `_rate_store` dict, `_check_rate_limit()`

The rate limiter is a module-level dict (`_rate_store: dict[str, list[float]]`). It works correctly with `--workers 1`. The moment you increase workers (the first thing you do to handle more load), each worker has its own independent `_rate_store`. A user sending 1000 req/min would only see 100/min in each worker's view — rate limiting stops working entirely.

This is not just a scaling problem. It is a security regression that happens the instant you scale past 1 worker.

**At 100 users with 2+ workers:** Rate limits are unenforced — each worker only sees its slice of traffic.
**At 500 users:** Same issue, compounded. An abusive client can send unlimited requests.

### B3 — `_SESSIONS` in-memory dict is per-worker (BROKEN at 2+ workers)

**File:** `core/session.py`, `_SESSIONS` dict

Sessions are stored in a process-level dict. The JSON file is loaded once at import (`_restore_from_file()`). With 1 worker this works fine. With 2+ workers:

- Worker A creates session `abc-123`, stores it in Worker A's `_SESSIONS`.
- The next request for `abc-123` hits Worker B — `_SESSIONS` is empty on Worker B — `KeyError` → 404.

The file store exists precisely to solve this, but it does not solve it: `_restore_from_file()` runs once at startup, and writes go to disk from whichever worker handles the mutation. Worker B would only pick up Worker A's session if it re-reads the file — which it never does after startup.

**At 2 workers:** ~50% of session requests return 404 (whichever worker didn't create the session).
**At 4 workers:** ~75% failure rate.

This bottleneck is dormant at `--workers 1` (the current Dockerfile) but becomes catastrophic the moment you increase workers, which is the natural first response to load.

### B4 — Analytics `get_stats()` reads the entire JSONL file on every admin dashboard hit

**File:** `analytics.py`, `_read_all()` called by `get_stats()`

`_read_all()` opens and parses the entire `events.jsonl` on every `/admin/stats` request. At 100 users doing 10 turns each, the file grows at roughly 1000 events/session × 100 users = 100,000 lines. Parsing 100k lines of JSON on every dashboard hit:
- Takes 200–500 ms per request
- Holds `self._lock` during the entire read (blocking all concurrent analytics writes)

**At 100 users:** Admin dashboard is slow but functional. Analytics writes can queue.
**At 500 users:** File reaches hundreds of thousands of lines. Dashboard takes seconds. Write lock contention begins to affect request latency.

### B5 — Static file serving through Python (minor)

**File:** `app.py`, `serve_root()` reads `index.html` with `Path.read_text()` on every request.

Serving `index.html` via `(static_dir / "index.html").read_text()` bypasses FastAPI's `StaticFiles` caching. Every `GET /` hits Python. At 100 users this is minor overhead; at 500 it wastes worker time on a zero-logic operation.

---

## Failure Modes by Scale

### At 100 concurrent users

| Symptom | Root Cause |
|---|---|
| Turn responses take 2–10 seconds | B1: JSON rewrite on every negotiate() with lock contention |
| Multi-worker deploy breaks sessions | B3: per-worker _SESSIONS dict |
| Rate limiting stops working at 2+ workers | B2: per-worker rate store |
| Admin dashboard slow | B4: full JSONL scan |

The app does not crash at 100 users with 1 worker — it degrades to unusable latency. With 2+ workers it breaks functionally (sessions not found, rate limits bypass).

### At 500 concurrent users

| Symptom | Root Cause |
|---|---|
| App appears hung, timeouts everywhere | B1: write queue never drains under load |
| Sessions failing at 75%+ rate | B3: session state siloed per worker |
| Rate limiter completely ineffective | B2: 8-worker deploy = 8× the allowed rate per IP |
| Analytics file becomes a bottleneck | B4: JSONL read/write lock contention |
| High memory per worker | B3: each worker holds full session dict in RAM |

At 500 users with 1 worker, the single-threaded fsync bottleneck causes timeouts that trigger client retries, which compound the queue. At 500 users with multiple workers, the session-not-found errors make the product non-functional.

---

## Prioritized Action Plan

Changes are ordered by impact-to-effort ratio. Changes 1–3 are the minimum viable set for 100 users. Changes 4–5 extend to 500 users without a database.

---

### Change 1 — Stop rewriting all sessions on every write (Effort: 2 hours)

**What to change:** `core/store.py` and `core/session.py`

The current write path serializes and fsync-writes every session on every mutation. Replace this with write-through to individual session files. Each session gets its own file: `.dealsim_sessions/{session_id}.json`.

Key changes:
- `save_sessions()` becomes `save_session(session_id, data)` — writes one file at a time.
- `load_sessions()` becomes `load_session(session_id)` — reads one file.
- `_persist_all()` in `session.py` becomes `_persist_one(session)` — called only for the mutated session.
- The lock in `store.py` becomes a per-session lock (a `dict[str, Lock]`) or can be dropped entirely since `os.replace()` is already atomic.

**Expected win:** Write time drops from O(N sessions) to O(1 session). At 100 concurrent users, each negotiate() call writes ~2–5 KB instead of 100+ KB. Lock contention drops to near zero.

**Trade-off:** The startup `_restore_from_file()` now needs to glob all session files. This is fine — it runs once.

---

### Change 2 — Move rate limiting to nginx or a shared counter (Effort: 1–3 hours)

**What to change:** `app.py` rate limiter, `docker-compose.yml` / nginx config

Option A (least code change, immediately correct): Move rate limiting to nginx using `limit_req_zone`. The `nginx/` directory already exists in the repo, so nginx is already part of the deployment plan. Add a `limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m` directive. Remove the in-process rate limiter from `app.py` or keep it as a last-resort fallback.

Option B (pure Python, works without nginx): Replace `_rate_store` dict with a `multiprocessing.Manager().dict()` and replace the module-level lock with `multiprocessing.Lock()`. This shares state across workers within the same host.

Option A is better. The nginx config is already present — this is likely a 30-minute addition to the existing nginx config file.

**Expected win:** Rate limiting works correctly under any number of workers. Security regression at 2+ workers is eliminated.

---

### Change 3 — Pin sessions to a worker using sticky routing, or use the file store correctly (Effort: 1–4 hours)

**What to change:** `docker-compose.yml` (nginx upstream) or `core/session.py`

This addresses B3 — the per-worker `_SESSIONS` dict breaking multi-worker deploys.

Option A (no code change — sticky sessions via nginx): Configure nginx upstream with `ip_hash` or use the session ID as a routing key (`hash $arg_session_id consistent`). Every request for session `abc-123` always hits the same worker. Zero code change required to session.py.

Option B (fix the file-store round-trip): After Change 1, each session is its own file. Modify `_load_session()` to fall back to disk if the session is not in the in-memory dict. This is already the documented intent (`_restore_from_file()`) but it only runs once at startup. Making it per-lookup (with a simple `not in _SESSIONS` check before raising `KeyError`) makes multi-worker deploys correct without sticky routing.

Option B is two lines of code and makes the architecture genuinely stateless. Recommended.

The `_load_session()` change:
```python
# current (broken for multi-worker):
session = _SESSIONS.get(session_id)
if session is None:
    raise KeyError(...)

# fixed:
session = _SESSIONS.get(session_id)
if session is None:
    # try disk (handles multi-worker case)
    try:
        data = load_session(session_id)   # after Change 1
        session = _deserialize_session(data)
        _SESSIONS[session_id] = session
    except FileNotFoundError:
        raise KeyError(f"Session not found: {session_id}")
```

**Expected win:** Multi-worker deploys become safe. You can now run `--workers 4` and sessions are found correctly regardless of which worker handles the request.

---

### Change 4 — Add in-memory analytics cache with TTL (Effort: 2–3 hours)

**What to change:** `analytics.py`, `get_stats()`

`get_stats()` currently calls `_read_all()` on every hit. The admin dashboard does not need real-time accuracy — a 60-second cache is sufficient for any operational purpose.

Add a simple module-level cache:

```python
_stats_cache: dict | None = None
_stats_cache_ts: float = 0.0
_STATS_CACHE_TTL: float = 60.0

def get_stats(self) -> dict:
    now = time.time()
    if _stats_cache is not None and (now - _stats_cache_ts) < _STATS_CACHE_TTL:
        return _stats_cache
    result = self._compute_stats()   # current get_stats() logic
    # update cache
    ...
    return result
```

This eliminates 99% of JSONL reads under normal usage. The same pattern applies to `feedback.py` `get_summary()`.

**Expected win:** Admin stats endpoint goes from 200–500 ms to <1 ms on cached hits. JSONL write lock contention drops to near zero. Works at 500+ users.

---

### Change 5 — Increase workers and add resource limits to docker-compose (Effort: 30 minutes)

**What to change:** `Dockerfile` CMD, `docker-compose.yml`

After Changes 1–3, the architecture is safe for multiple workers. Update the Dockerfile:

```dockerfile
# Replace:
CMD ["uvicorn", "dealsim_mvp.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# With:
CMD ["uvicorn", "dealsim_mvp.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

The standard formula is `workers = 2 * CPU_cores + 1`. For a 2-vCPU container (typical for Fly.io/Railway small tier), that is 5 workers. Start with 4 to leave headroom.

Also add memory limits to `docker-compose.yml` to prevent a memory leak in one session from killing the container:

```yaml
deploy:
  resources:
    limits:
      memory: 512M
```

**Expected win:** Request throughput increases 4×. Combined with Changes 1–3, this is sufficient for 500 concurrent users on a single host.

---

## What This Does NOT Solve (Future Work)

- **Horizontal scaling (multiple hosts):** Changes 1–3 make a single host with multiple workers correct. Running two separate hosts (load balancer in front) still requires a shared session store (Redis or similar) because the session files are on local disk. This is the only architectural change that requires Redis.
- **Analytics at very high volume (>1M events):** The JSONL approach with a TTL cache works up to ~1M events. Above that, the file scan in `_read_all()` (even cached) becomes slow on cold start. SQLite is the right next step — it requires changing only `_append()` and `_read_all()` in `analytics.py`.
- **Session cleanup:** `_MAX_AGE_SECONDS = 3600` with 500 users means up to 500 session files accumulating per hour. A background cleanup task (e.g., `asyncio` periodic coroutine) should prune old session files. Currently cleanup only runs on `load_sessions()`.

---

## Implementation Order

| Priority | Change | Effort | Unlocks |
|---|---|---|---|
| 1 | Per-session file writes (B1) | 2 hours | Eliminates the primary latency spike |
| 2 | Fix multi-worker session lookup (B3) | 1 hour | Makes 2+ workers safe |
| 3 | Move rate limiting to nginx (B2) | 1 hour | Fixes security regression at 2+ workers |
| 4 | Analytics stats cache (B4) | 2 hours | Eliminates read bottleneck at 500 users |
| 5 | Increase workers + resource limits | 30 min | Multiplies throughput immediately |

Total estimated effort: **6–8 hours of focused work.**

Changes 1–3 alone bring the system from "breaks at 100 concurrent users" to "handles 100 concurrent users cleanly on 1 worker." Adding Change 5 after Changes 1–3 brings it to 500 concurrent users without any infrastructure change.
