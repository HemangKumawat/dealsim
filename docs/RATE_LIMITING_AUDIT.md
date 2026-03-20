# Rate Limiting & DoS Protection Audit

**Date:** 2026-03-19
**Scope:** `app.py` rate limiter middleware, all API routes, nginx configuration, Docker/uvicorn setup
**Severity scale:** CRITICAL / HIGH / MEDIUM / LOW / INFO

---

## 1. Per-IP vs Per-Session: X-Forwarded-For Spoofing

**Finding: MEDIUM (mitigated in production, vulnerable in dev)**

The application-level rate limiter in `app.py` uses `request.client.host`:

```python
client_ip = request.client.host if request.client else "unknown"
```

**Behind nginx (production):** nginx sets `X-Real-IP` and `X-Forwarded-For` headers, but the FastAPI middleware does **not read them**. It reads the TCP-level `client.host`, which behind nginx will always be the Docker bridge IP (e.g., `172.17.0.1`). This means:

- All users share a single rate limit bucket in production when relying on the app-level limiter alone.
- nginx's own `limit_req` uses `$binary_remote_addr`, which is the true client IP, so nginx provides correct per-IP limiting at the edge.

**Without nginx (dev, direct exposure):** `client.host` is the real client IP. However, FastAPI/uvicorn does not parse `X-Forwarded-For` by default, so an attacker cannot spoof their IP via headers in this mode.

**Risk:** If the app is ever exposed directly (no nginx), the rate limiter works correctly per-IP. Behind nginx, the app-level limiter is effectively broken (single bucket for all traffic), but nginx's own rate limiting compensates.

**Recommendation:**
- Add `--proxy-headers` to uvicorn and use a trusted proxy configuration so `request.client.host` reflects the real client IP even behind nginx. This provides defense-in-depth.
- Alternatively, use `X-Real-IP` header when behind a trusted proxy:
  ```python
  client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
  ```
- If adding proxy-header trust, restrict it to the Docker network to prevent external spoofing.

---

## 2. Rate Limit Values and Endpoint Differentiation

**Finding: MEDIUM**

**Current state:**
- **App-level:** Flat 100 requests/minute for all endpoints (configurable via `RATE_LIMIT_PER_MINUTE` env var). Health check is exempted.
- **nginx-level:** Two zones defined:
  - `api_general`: 100 req/min with burst=20 (all routes under `/`)
  - `api_auth`: 10 req/min with burst=5 (auth endpoints matching `^/api/(auth|login|register|password|token)`)

**Problem:** All API endpoints get the same 100 req/min limit regardless of cost. These endpoints have very different resource profiles:

| Endpoint | Cost | Current Limit | Recommended |
|---|---|---|---|
| `GET /scenarios` | Trivial (returns static list) | 100/min | Fine |
| `POST /sessions` | High (creates persona, initializes simulator, writes to disk) | 100/min | 20/min |
| `POST /sessions/{id}/message` | High (runs simulation logic) | 100/min | 60/min |
| `POST /offers/analyze` | Medium (regex parsing, strategy generation) | 100/min | 30/min |
| `POST /tools/audit-email` | Medium (text analysis) | 100/min | 30/min |
| `POST /feedback` | Low (append to JSONL) | 100/min | 20/min |
| `POST /events` | Low (append to JSONL) | 100/min | 30/min |
| `GET /challenges/today` | Trivial (deterministic hash lookup) | 100/min | Fine |
| `POST /challenges/today/submit` | Medium (scoring + disk write) | 100/min | 20/min |
| Admin endpoints | High (reads entire JSONL, computes stats) | 100/min | 5/min |

**Recommendation:** Add per-endpoint nginx rate limit zones for expensive operations. At minimum, create a `api_heavy` zone at 20-30 req/min for session creation and offer analysis.

---

## 3. Memory Leak in Rate Limiter

**Finding: LOW (adequately mitigated)**

The rate limiter uses `defaultdict(list)` with two cleanup mechanisms:

1. **Per-request pruning (line 63):** On every request, the current IP's timestamps are filtered to the 60-second window. Empty lists are deleted (line 64-65).
2. **Periodic full sweep (line 55-59):** Every 60 seconds, all stale IPs (no timestamps in window) are evicted.

**Bug on line 64-67:** After pruning the list to only recent timestamps and deleting the key if empty, line 67 accesses `_rate_store[client_ip]` again. Because it's a `defaultdict(list)`, this **re-creates the empty list** for the IP that was just deleted. The flow is:

```python
_rate_store[client_ip] = [t for t in timestamps if t > window]  # prune
if not _rate_store[client_ip]:
    del _rate_store[client_ip]          # delete empty key

if len(_rate_store[client_ip]) >= RATE_LIMIT:  # re-creates empty list via defaultdict!
    return False
_rate_store[client_ip].append(now)      # writes to re-created key
```

This means the `del` on line 65 is immediately undone. The key always gets recreated with `[now]`. This is not a memory leak per se (the entry is small), but it means the "delete empty keys" logic is dead code.

**Under sustained attack:** If 100,000 unique IPs each send one request, the store holds 100,000 entries. The periodic sweep cleans them after 60 seconds of inactivity, so the worst-case memory is proportional to unique IPs within a 60-second window. At ~100 bytes per entry (IP string + list with one float), 100K IPs would use ~10MB. Not catastrophic but worth noting.

**Recommendation:**
- Fix the dead-code bug: check `len(...)` before the `del`, or use a regular `dict` with `.get()`.
- Consider a max-size cap on `_rate_store` (e.g., 50,000 keys) as a safety valve. If exceeded, reject new IPs with 429.

---

## 4. Session Exhaustion Attack

**Finding: HIGH**

**Current state:** There is no limit on the number of sessions a single IP or user can create. The `POST /sessions` endpoint creates a new `NegotiationSession` object in the `_SESSIONS` dict every time it's called.

Each session contains:
- `NegotiationPersona` with generated system prompt (~1-2KB)
- `NegotiationState` with transcript (grows per message)
- `RuleBasedSimulator` instance
- `Scorecard` (after completion)

**Attack scenario:** An attacker at 100 req/min (the rate limit) can create 100 sessions/minute. Each session is ~5KB minimum, growing with messages. In one hour: 6,000 sessions = ~30MB. In 24 hours: 144,000 sessions = ~720MB.

**Mitigation already present:**
- `store.py` auto-cleans sessions older than 1 hour on file load (`_MAX_AGE_SECONDS = 3600`).
- BUT: the in-memory `_SESSIONS` dict in `session.py` is only cleaned when `load_sessions()` is called (module import time). There is no periodic in-memory cleanup.

**The in-memory dict grows without bound** during runtime. Stale sessions are only cleaned from the JSON file, not from the `_SESSIONS` dict. The `_persist_all()` function serializes ALL in-memory sessions, including stale ones.

**Recommendation:**
- Add a max-sessions-per-IP limit (e.g., 10 active sessions per IP).
- Add periodic in-memory session cleanup (e.g., every 5 minutes, evict sessions older than 1 hour from `_SESSIONS`).
- Add a global session cap (e.g., 10,000) and reject new sessions when exceeded.
- Consider adding session creation to a stricter rate limit zone in nginx (10-20 req/min).

---

## 5. Request Body Size Limits

**Finding: LOW (partially addressed)**

**nginx level:** `client_max_body_size 10m` is set globally. This prevents uploads larger than 10MB from reaching the app.

**Application level:** Pydantic models enforce field-level limits:
- `SendMessageRequest.message`: max_length=2000
- `FeedbackRequest.comment`: max_length=1000
- `FeedbackRequest.email`: max_length=200
- `EventRequest.event_type`: max_length=50
- `AuditEmailRequest.email_text`: min_length=10 (no max_length)
- `CreateSessionRequest.context`: no max_length in routes.py (500 in models.py, but routes.py defines its own model without this limit)
- `OfferAnalyzeRequest.offer_text`: min_length=5 (no max_length)
- `ChallengeSubmitRequest.response`: min_length=5 (no max_length)
- `EventRequest.properties`: arbitrary dict (no size limit)

**Gaps:**
- `offer_text`, `email_text`, `challenge response`, and `context` fields have no upper bound at the application level. A 10MB JSON body would pass nginx but could cause expensive regex parsing in `analyze_offer()` and `audit_email()`.
- `EventRequest.properties` accepts an arbitrary dict with no depth or size limit.

**Recommendation:**
- Add `max_length` to all free-text fields: `offer_text` (5000), `email_text` (5000), `response` (2000), `context` (500).
- Add size validation to `EventRequest.properties` (e.g., max 10 keys, max 200 chars per value).
- Reduce `client_max_body_size` to `1m` in nginx -- no endpoint needs more than that.

---

## 6. Analytics/Feedback Endpoint Spam

**Finding: MEDIUM**

**`POST /events`:** Accepts any of 13 predefined event types. Validates `event_type` against an allowlist, which is good. However:
- No authentication required.
- No deduplication (same event can be submitted thousands of times).
- Each event is appended to `events.jsonl`, growing the file.
- The `get_stats()` method reads and parses the entire JSONL file on every call, so a bloated file degrades admin dashboard performance.

**`POST /feedback`:** Similarly unauthenticated:
- The `session_id` field is required but not validated against actual sessions (no existence check).
- An attacker can spam fake feedback with non-existent session IDs.
- Each submission appends to `feedback.jsonl`.

**Mitigations already present:**
- File rotation at 10MB with 3 rotated copies (so max ~40MB total).
- Rate limit of 100/min applies.

**Remaining risk:** At 100 events/min, the JSONL file reaches 10MB in roughly 1-2 days of sustained spam, triggering rotation. The admin dashboard `get_stats()` reads the entire file each time, which at 10MB of JSON is slow but not catastrophic.

**Recommendation:**
- Validate `session_id` exists before accepting feedback.
- Add a stricter rate limit for `POST /feedback` (10-20 per minute).
- Consider rate-limiting `POST /events` to 30/min.
- Add a unique constraint or deduplication window for feedback (one per session_id).

---

## 7. Slowloris / Slow-Read Protection

**Finding: LOW (mitigated by nginx)**

**uvicorn (direct):** The Dockerfile runs uvicorn with defaults. uvicorn has no built-in slowloris protection. Default timeout is unlimited for connection keep-alive. A slowloris attacker could hold connections open indefinitely.

**nginx (production):** Provides adequate protection:
- `keepalive_timeout 65` -- closes idle connections after 65 seconds.
- `proxy_connect_timeout 10s` -- backend connection timeout.
- `proxy_send_timeout 60s` / `proxy_read_timeout 60s` -- limits slow backend responses.
- `client_body_buffer_size 128k` -- limits buffered request body size.
- No explicit `client_header_timeout` or `client_body_timeout` (nginx defaults: 60s each, which is acceptable).

**uvicorn --workers 1:** Only one worker process. A small number of slow connections could exhaust the single worker's capacity. The worker uses asyncio, so slow I/O connections don't fully block, but CPU-bound attacks (large request bodies hitting regex parsing) would block the event loop.

**Recommendation:**
- Add `--timeout-keep-alive 5` to the uvicorn command in Dockerfile to limit idle connections.
- Consider increasing `--workers` to 2-4 for the production Dockerfile (the server has 2 CPUs).
- Add explicit `client_header_timeout 10s` and `client_body_timeout 10s` in nginx config.

---

## 8. 1000 Concurrent Requests Behavior

**Finding: MEDIUM**

**With nginx:** nginx's `limit_req zone=api_general burst=20 nodelay` means:
- Requests within 100/min rate pass immediately.
- Burst allows 20 extra requests without delay.
- Request 121+ in a minute gets 429.
- nginx's `worker_connections 1024` per worker (2 workers = 2048 total) handles the TCP connections.

So 1000 concurrent requests from a single IP: ~120 succeed, ~880 get 429. From 1000 different IPs: all succeed (under 100/min each).

**Without nginx (dev):**
- The app-level rate limiter is synchronous Python running in an async middleware. The `_rate_store` dict is not thread-safe (no lock). With `--workers 1` this is fine (single process, GIL + asyncio). With multiple workers, the dict is per-process and not shared.
- uvicorn with 1 worker and asyncio can handle many concurrent connections, but CPU-bound endpoints (offer analysis, scoring) will serialize on the event loop.
- 1000 concurrent session-creation requests would create 1000 sessions in memory rapidly. The `_persist_all()` call serializes ALL sessions to JSON on every creation, so the 1000th request would write a file containing all 1000 sessions. This is O(n^2) total write cost.

**Recommendation:**
- The `_persist_all()` serializing all sessions on every write is a performance bottleneck. Consider debounced/batched persistence or per-session file writes.
- Add connection limits in nginx: `limit_conn_zone $binary_remote_addr zone=conn_per_ip:10m; limit_conn conn_per_ip 50;` to cap concurrent connections per IP.

---

## 9. IP Blocking Capability

**Finding: MEDIUM (no dynamic blocking)**

**Current state:**
- **nginx:** Static IP allowlist for admin endpoints only (`allow`/`deny` directives). No dynamic IP blocking.
- **App-level:** No IP blocking mechanism. The rate limiter returns 429 but never blocks an IP.

**What exists:**
- Rate limiting (100/min) slows attackers but doesn't block them.
- No fail2ban or similar integration.
- No API endpoint to add/remove blocked IPs.
- No automatic escalation from rate-limit violations to IP blocks.

**Recommendation:**
- Install fail2ban on the host watching nginx 429 responses. Config: ban IP for 1 hour after 50 rate-limit violations in 5 minutes.
- Add an in-app IP blocklist (loaded from env var or file) checked in the middleware before the rate limiter. This allows emergency manual blocks without nginx reload.
- Consider a simple escalation: if an IP hits the rate limit 10 times in 5 minutes, add to a temporary blocklist (15-minute ban). Store in memory with TTL.

---

## 10. Rate Limiter Behind Reverse Proxy

**Finding: HIGH (requires action)**

**Current behavior:** As detailed in section 1, the app-level rate limiter sees the nginx container's IP for all requests. This means:

1. The app-level 100/min limit applies to ALL traffic combined, not per-user.
2. Once total traffic exceeds 100 req/min (easily possible with normal usage), legitimate users get 429 from the app even though nginx let them through.
3. nginx's rate limiting is the actual protection layer, and it works correctly using `$binary_remote_addr`.

**Double rate limiting conflict:** A request might pass nginx's 100/min per-IP limit but hit the app's 100/min global limit. This creates unpredictable 429 responses for legitimate users under normal load.

**Recommendation (pick one):**
1. **Fix the app to read real IP:** Add `--proxy-headers` to uvicorn and set `FORWARDED_ALLOW_IPS` to the Docker network. The app then reads `X-Forwarded-For` correctly.
2. **Disable app-level rate limiting in production:** Since nginx handles it correctly, set `RATE_LIMIT_PER_MINUTE=999999` in the Docker env to effectively disable the app-level limiter. Simpler but removes defense-in-depth.
3. **Replace with middleware that respects proxies:** Use a library like `slowapi` that handles `X-Real-IP` / `X-Forwarded-For` properly.

---

## Summary of Findings

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | App rate limiter ignores proxy headers | HIGH | nginx compensates, but app limiter is broken behind proxy |
| 2 | Flat rate limit for all endpoints | MEDIUM | Expensive endpoints need stricter limits |
| 3 | Minor dead code in rate limiter cleanup | LOW | Periodic sweep handles it |
| 4 | Unlimited session creation | HIGH | No per-IP session cap, no in-memory cleanup |
| 5 | Missing max_length on several text fields | LOW | nginx caps at 10MB, but regex parsing is expensive |
| 6 | Analytics/feedback spam | MEDIUM | No auth, no dedup, file grows until rotation |
| 7 | No slowloris protection without nginx | LOW | nginx mitigates in production |
| 8 | O(n^2) persistence on concurrent session creation | MEDIUM | 1000 sessions = 1000 full-file rewrites |
| 9 | No dynamic IP blocking | MEDIUM | Only static nginx rules |
| 10 | App + nginx double rate limiting conflict | HIGH | Can cause false 429s for legitimate users |

## Priority Actions

1. **Fix app-level rate limiter to read real client IP** behind nginx (sections 1, 10). This is the most impactful single fix.
2. **Add session creation limits:** max 10 active sessions per IP, periodic in-memory cleanup (section 4).
3. **Add max_length to unbounded text fields** (`offer_text`, `email_text`, `response`) (section 5).
4. **Add per-endpoint rate limits in nginx** for `POST /sessions` and `POST /offers/analyze` (section 2).
5. **Install fail2ban** for automatic IP blocking on repeated 429s (section 9).
