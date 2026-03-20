# Logging & Monitoring Audit — DealSim MVP

**Date:** 2026-03-19
**Reviewer:** SRE Production Readiness Review
**Scope:** All Python source in `src/dealsim_mvp/`
**Deployment target:** UpCloud 2 CPU / 8 GB RAM, Docker, single uvicorn worker

---

## Executive Summary

DealSim has basic logging via Python's `logging` module but lacks the structured, observable, production-grade telemetry needed for reliable operation. The health check is minimal, there are no request-level metrics, no correlation IDs, no request timing middleware, and sensitive data leaks into analytics JSONL files. The application is functional for a beta launch but will be difficult to debug and impossible to monitor at scale without the changes below.

**Severity breakdown:** 4 critical, 4 high, 3 medium.

---

## 1. Logging Configuration

**Current state:** `app.py` lines 33-36 configure `logging.basicConfig` with a timestamp-level-name-message format to stderr. Log level is configurable via `LOG_LEVEL` env var.

**Findings:**

| # | Finding | Severity | Detail |
|---|---------|----------|--------|
| 1.1 | No structured (JSON) logging | CRITICAL | Plain-text logs cannot be parsed by Loki, CloudWatch, Datadog, or any log aggregator without fragile regex. Every field (timestamp, level, logger name, message, extras) should be a distinct JSON key. |
| 1.2 | `basicConfig` called at module level | MEDIUM | Works for a single-worker uvicorn but will double-configure loggers if `create_app()` is ever called in tests or multi-worker setups. Move config into `create_app()` with a guard or use `logging.config.dictConfig`. |
| 1.3 | No log format for uvicorn access logs | HIGH | Uvicorn emits its own access logs in a different format. These are not captured or unified with the application logger. In Docker, two interleaved formats make grep/parsing unreliable. |

**Recommendation:**
Replace `basicConfig` with `python-json-logger` or a manual `logging.Formatter` that outputs one JSON object per line. Configure uvicorn's access log format to match. Example:

```python
import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Merge any extra fields attached to the record
        for key in ("request_id", "session_id", "method", "path", "status", "duration_ms", "client_ip"):
            val = getattr(record, key, None)
            if val is not None:
                log_obj[key] = val
        return json.dumps(log_obj)
```

---

## 2. Log Levels

**Current state:** Modules use `logger.info`, `logger.warning`, `logger.debug`, and `logger.exception` appropriately in most places.

**Findings:**

| # | Finding | Severity | File(s) |
|---|---------|----------|---------|
| 2.1 | Silent exception swallowing in `_track()` and `_feature()` | HIGH | `routes.py:78-79, 85-86` — bare `except Exception: pass` means analytics failures produce zero log output. A broken analytics path could silently corrupt data for days. |
| 2.2 | `store.py` persistence failures logged at DEBUG | MEDIUM | `session.py:223`, `store.py:70` — `logger.debug("Failed to persist sessions")`. Persistence failure is at minimum WARNING. If the session file cannot be written, all in-flight sessions are at risk of loss on restart. |
| 2.3 | No ERROR-level logs on request handler exceptions | HIGH | `routes.py:367-368` is the only place that calls `logger.exception` (session creation failure). All other endpoints raise `HTTPException` without logging. A 500 from debrief generation, offer analysis, or challenge scoring produces no server-side log entry — only the client sees the error. |

**Recommendation:**
- Replace `pass` in `_track`/`_feature` with `logger.debug("Analytics tracking failed", exc_info=True)` at minimum.
- Elevate persistence failures to `WARNING`.
- Add a global exception handler middleware that logs unhandled exceptions at ERROR before returning 500:

```python
@app.middleware("http")
async def error_logging_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        raise
```

---

## 3. Request/Response Timing

**Current state:** No request timing exists anywhere. The rate limiter middleware (`app.py:101-113`) does not measure or log response times.

**Finding:**

| # | Finding | Severity |
|---|---------|----------|
| 3.1 | No request duration logging | CRITICAL | Without timing data, it is impossible to detect slow endpoints, measure p50/p95/p99 latencies, set SLOs, or alert on degradation. |

**Recommendation:**
Add timing middleware that logs method, path, status code, and duration for every request:

```python
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 1),
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return response
```

---

## 4. Error Context

**Current state:** `logger.exception("Failed to create session")` in `routes.py:367` is the only error log with a stack trace. All other error paths rely on HTTPException detail strings reaching the client.

**Findings:**

| # | Finding | Severity |
|---|---------|----------|
| 4.1 | No session_id in error context | HIGH | When a 404/409/500 occurs on `/sessions/{id}/message`, the session_id is not included in any log. Debugging requires correlating client-side error responses with server timestamps. |
| 4.2 | KeyError for missing sessions not logged | MEDIUM | `routes.py:398-401` catches KeyError and ValueError but does not log them. A burst of 404s from a broken client is invisible to the operator. |

**Recommendation:**
Log at WARNING for 4xx client errors and ERROR for 5xx, always including the session_id and request path as structured fields.

---

## 5. Correlation / Request ID

**Current state:** No correlation ID exists. There is no way to trace a single user request through the rate limiter, route handler, session manager, simulator, scorer, and analytics tracker.

**Finding:**

| # | Finding | Severity |
|---|---------|----------|
| 5.1 | No request correlation ID | CRITICAL | In any multi-step debugging scenario (user reports "my session broke"), there is no single identifier to grep for across all log lines produced by that request. |

**Recommendation:**
Generate a UUID4 per request in middleware, attach it to the logging context (via `logging.LoggerAdapter` or `contextvars`), and return it in a `X-Request-ID` response header:

```python
import contextvars, uuid

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    _request_id.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response
```

Then use a filter or adapter so every `logger.*` call automatically includes the request_id.

---

## 6. Sensitive Data in Logs

**Current state:** The application stores analytics events to JSONL files (`data/events.jsonl`, `data/feedback.jsonl`, `data/user_history.jsonl`).

**Findings:**

| # | Finding | Severity |
|---|---------|----------|
| 6.1 | User emails stored in feedback JSONL | HIGH | `feedback.py:62` stores `email[:200]` in plaintext in the feedback file. If the data volume is compromised, all user emails are exposed. |
| 6.2 | Salary/offer numbers stored in analytics events | MEDIUM | `routes.py:809-811` tracks `current_offer` and `negotiated_offer` as event properties. While not PII, salary data combined with user_id could be sensitive. |
| 6.3 | Admin key transmitted as query parameter | HIGH | `app.py:164` accepts the admin key as `?key=...` in the URL. Query parameters appear in access logs, browser history, referrer headers, and any proxy logs. |
| 6.4 | No log scrubbing for request bodies | MEDIUM | If log level is set to DEBUG and request body logging is ever added, offer_text, email_text, and negotiation messages would appear in logs unredacted. |

**Recommendations:**
- Hash emails before storage or encrypt at rest. At minimum, do not log them.
- Move admin key from query parameter to `Authorization: Bearer <key>` header.
- Add a log filter that redacts fields matching patterns like `email`, `password`, `key`, `token`.
- Never log raw request bodies at INFO level or above.

---

## 7. Health Check Endpoint

**Current state:** `GET /health` returns `{"status": "healthy", "version": "0.1.0"}`. It is excluded from rate limiting. Docker HEALTHCHECK pings it every 30s.

**Findings:**

| # | Finding | Severity |
|---|---------|----------|
| 7.1 | Health check is shallow — no dependency verification | HIGH | The endpoint confirms the Python process is alive but does not verify that the data directory is writable, the session store is loadable, or the JSONL files are accessible. A corrupted session store or full disk would pass the health check. |
| 7.2 | No readiness vs. liveness distinction | MEDIUM | A single `/health` endpoint serves both purposes. During startup (session restore from disk), the app might serve 500s while appearing healthy. |

**Recommendation:**
Add a deep health check:

```python
@app.get("/health", tags=["system"])
def health_check():
    checks = {"api": "ok", "version": __version__}
    # Verify data directory is writable
    try:
        probe = Path(os.environ.get("DEALSIM_DATA_DIR", "data")) / ".health_probe"
        probe.write_text("ok")
        probe.unlink()
        checks["data_dir"] = "ok"
    except Exception as e:
        checks["data_dir"] = f"error: {e}"
    # Verify session store is loadable
    try:
        from dealsim_mvp.core.store import load_sessions
        load_sessions()
        checks["session_store"] = "ok"
    except Exception as e:
        checks["session_store"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values() if v != __version__)
    status_code = 200 if all_ok else 503
    return JSONResponse(
        content={"status": "healthy" if all_ok else "degraded", **checks},
        status_code=status_code,
    )
```

Add a separate `/ready` endpoint for load balancer readiness probes.

---

## 8. Metrics

**Current state:** The `AnalyticsTracker` in `analytics.py` tracks events to a JSONL file and computes aggregate stats on-demand via `get_stats()`. The admin dashboard (`/admin/stats`) displays session counts, completion rates, and feature usage. There are no Prometheus-style metrics, no counters, no histograms.

**Findings:**

| # | Finding | Severity |
|---|---------|----------|
| 8.1 | No standard metrics endpoint (`/metrics`) | CRITICAL | Without Prometheus-compatible metrics, you cannot graph request rate, error rate, or latency in Grafana or any monitoring stack. The JSONL-based analytics system is designed for product analytics, not operational metrics. |
| 8.2 | No error rate tracking | HIGH | There is no counter for 4xx or 5xx responses. A spike in errors is invisible unless someone checks the admin dashboard manually. |
| 8.3 | Analytics `get_stats()` reads entire JSONL file | MEDIUM | `analytics.py:244-259` parses the full events file on every `/admin/stats` call. At 100k+ events, this becomes a latency problem on a 2-CPU box. |

**Recommendation for UpCloud (lightweight, no Prometheus server needed):**

Use `prometheus-fastapi-instrumentator` for automatic request metrics:

```bash
pip install prometheus-fastapi-instrumentator
```

```python
from prometheus_fastapi_instrumentator import Instrumentator

def create_app() -> FastAPI:
    app = FastAPI(...)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    ...
```

This gives you request count, latency histograms, and in-flight requests for free. On UpCloud, pair with:
- **Option A (simplest):** Grafana Cloud free tier (50 GB logs, 10k metrics) — push metrics via Grafana Agent running as a sidecar container.
- **Option B (self-hosted):** Single Prometheus + Grafana container alongside the app. Fits easily in 8 GB RAM.

For the JSONL stats performance issue, add an in-memory counter cache that only flushes aggregates to disk periodically, or switch to SQLite for analytics storage.

---

## 9. Alerting

**Current state:** None. There is no webhook, email, PagerDuty, or any notification mechanism for errors or anomalies.

**Findings:**

| # | Finding | Severity |
|---|---------|----------|
| 9.1 | No alerting on 5xx spike | CRITICAL | If the session store corrupts or disk fills, users see errors but the operator has no notification. |
| 9.2 | No alerting on health check failure | HIGH | Docker HEALTHCHECK will restart the container after 3 failures, but nobody is notified. |

**Recommendation (pragmatic for a solo/small-team deploy):**

**Tier 1 — Immediate (zero-cost):**
- Use UptimeRobot or Betterstack (free tier) to ping `/health` every 60s and alert via email/Slack on failure.

**Tier 2 — Error alerting:**
- Add a simple webhook-on-error handler in the logging config. When an ERROR log is emitted, POST to a Slack/Discord webhook:

```python
import urllib.request, json

class WebhookHandler(logging.Handler):
    def __init__(self, webhook_url: str):
        super().__init__(level=logging.ERROR)
        self.url = webhook_url

    def emit(self, record):
        try:
            payload = json.dumps({
                "text": f"[DealSim ERROR] {record.getMessage()}"
            }).encode()
            req = urllib.request.Request(
                self.url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Don't crash the app over a failed alert
```

**Tier 3 — Full stack (when revenue justifies it):**
- Grafana Cloud alerting rules on the Prometheus metrics endpoint.

---

## 10. Log Rotation and Export

**Current state:** `AnalyticsTracker` and `FeedbackCollector` both implement file rotation at 10 MB with 3 rotated copies (`analytics.py:192-228`, `feedback.py:120-156`). The main Python logger (stderr) has no rotation — it relies on Docker's log driver.

**Findings:**

| # | Finding | Severity |
|---|---------|----------|
| 10.1 | Docker default log driver is `json-file` with no max-size | HIGH | Without configuring `max-size` and `max-file` on the Docker log driver, container logs will grow unbounded and fill the disk. On a 2-CPU UpCloud box with limited SSD, this is a ticking time bomb. |
| 10.2 | JSONL data files have rotation but no export/backup | MEDIUM | The rotated `.1`, `.2`, `.3` files are overwritten on the next rotation. There is no mechanism to export old data before it is lost. |
| 10.3 | Session store file (`.dealsim_sessions.json`) has no size limit | LOW | Sessions auto-clean after 1 hour (`store.py:31`), which is adequate. But a burst of thousands of concurrent sessions could bloat this file temporarily. |

**Recommendation:**

Add to `docker-compose.yml`:

```yaml
services:
  dealsim:
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
```

For data export, add a cron job or scheduled task that copies rotated JSONL files to object storage (UpCloud Object Storage or S3-compatible) before they are overwritten.

---

## 11. Real-Time Application State

**Current state:** The admin dashboard (`/admin/stats`) shows aggregate analytics. `session.py:380-394` has a `list_sessions()` function but it is not exposed via any API endpoint.

**Findings:**

| # | Finding | Severity |
|---|---------|----------|
| 11.1 | No real-time session count or active connection visibility | MEDIUM | The operator cannot see how many sessions are currently active, how many are in-flight, or what the current memory footprint of `_SESSIONS` dict is. |
| 11.2 | No `/debug/state` or equivalent introspection endpoint | LOW | Useful for debugging production issues without SSH. |

**Recommendation:**
Add an admin-protected endpoint:

```python
@app.get("/api/admin/state", tags=["admin"])
def admin_state(key: str = FastQuery(...)):
    _verify_admin(key)
    import sys
    sessions = list_sessions()
    return {
        "active_sessions": len([s for s in sessions if s["status"] == "active"]),
        "total_sessions_in_memory": len(sessions),
        "rate_limiter_tracked_ips": len(_rate_store),
        "python_version": sys.version,
        "process_uptime_seconds": time.time() - _app_start_time,
    }
```

---

## Production Logging Setup for UpCloud (2 CPU, 8 GB RAM, Docker)

### Recommended Architecture

```
                    UpCloud VM (2 CPU / 8 GB)
    ┌──────────────────────────────────────────────┐
    │  Docker Compose                               │
    │  ┌─────────────────┐  ┌────────────────────┐ │
    │  │  dealsim:8000   │  │  grafana-agent     │ │
    │  │  (app + metrics)│  │  (scrapes /metrics │ │
    │  │                 │  │   ships to cloud)  │ │
    │  └────────┬────────┘  └────────────────────┘ │
    │           │ JSON logs to Docker log driver    │
    │  ┌────────┴────────┐                         │
    │  │  Docker json-file│ (max 50MB x 5 files)  │
    │  └─────────────────┘                         │
    └──────────────────────────────────────────────┘
              │                    │
              ▼                    ▼
    UptimeRobot/Betterstack   Grafana Cloud (free)
    (uptime ping /health)     (metrics + dashboards)
```

### Implementation Priority

**Week 1 — Critical path (deploy-blocking):**
1. Add JSON log formatter (Finding 1.1)
2. Add request timing middleware (Finding 3.1)
3. Add request correlation ID middleware (Finding 5.1)
4. Configure Docker log rotation (Finding 10.1)
5. Set up external uptime monitor on `/health` (Finding 9.1)
6. Move admin key from query param to Authorization header (Finding 6.3)

**Week 2 — High priority:**
7. Add `prometheus-fastapi-instrumentator` for `/metrics` (Finding 8.1)
8. Deepen health check to verify data dir + session store (Finding 7.1)
9. Add global exception logging middleware (Finding 2.3)
10. Fix silent exception swallowing in `_track()`/`_feature()` (Finding 2.1)
11. Add Slack/Discord webhook error alerting (Finding 9.2)
12. Add `/api/admin/state` endpoint (Finding 11.1)

**Week 3 — Hardening:**
13. Hash or encrypt emails in feedback store (Finding 6.1)
14. Elevate persistence failure log level to WARNING (Finding 2.2)
15. Log 4xx errors at WARNING with session context (Finding 4.1, 4.2)
16. Add JSONL data export/backup cron (Finding 10.2)
17. Add Grafana Agent sidecar for metrics shipping (Finding 8.1)

### Minimal `docker-compose.production.yml` Addition

```yaml
services:
  dealsim:
    environment:
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
      - DEALSIM_ALERT_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # Optional: Grafana Agent for metrics shipping
  grafana-agent:
    image: grafana/agent:latest
    volumes:
      - ./grafana-agent.yaml:/etc/agent/agent.yaml
    depends_on:
      - dealsim
    restart: unless-stopped
```

### Resource Budget on UpCloud 2 CPU / 8 GB

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| DealSim (uvicorn, 1 worker) | 0.5 core avg | ~200 MB | 250 MB logs (rotated) |
| Prometheus metrics (in-process) | negligible | ~20 MB | — |
| Grafana Agent (optional sidecar) | 0.05 core | ~50 MB | — |
| **Headroom** | **~1.4 cores** | **~7.7 GB** | plenty |

The monitoring stack fits comfortably. No need for a separate monitoring VM at this scale.

---

## Summary Table

| Check | Current State | Verdict | Priority |
|-------|--------------|---------|----------|
| Structured logging | Plain text to stderr | FAIL | Week 1 |
| Log levels appropriate | Mostly OK, 3 issues | PARTIAL | Week 2 |
| Request/response timing | None | FAIL | Week 1 |
| Error context for debugging | Minimal | FAIL | Week 2 |
| Correlation ID per request | None | FAIL | Week 1 |
| Sensitive data exclusion | Email in plaintext, admin key in URL | FAIL | Week 1-2 |
| Health check depth | Shallow (process alive only) | PARTIAL | Week 2 |
| Metrics endpoint | None | FAIL | Week 2 |
| Alerting capability | None | FAIL | Week 1-2 |
| Log rotation/export | JSONL rotated; Docker logs unbounded | PARTIAL | Week 1 |
| Real-time app state | Admin dashboard only, no live state | PARTIAL | Week 2 |
