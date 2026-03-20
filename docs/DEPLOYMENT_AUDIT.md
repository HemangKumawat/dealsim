# DealSim Deployment Audit

**Date:** 2026-03-19
**Scope:** Dockerfile, docker-compose.yml, render.yaml, fly.toml, railway.json, .env.example, .dockerignore, DEPLOY.md
**Target platform:** UpCloud Ubuntu 24.04, 2 CPU / 8 GB RAM (also evaluates Render, Fly.io, Railway)

---

## Overall Assessment

The deployment configuration is solid for an early-stage MVP. The Dockerfile follows most best practices, cloud configs are consistent, and the security posture is reasonable. The main gaps are: no multi-stage build, no lockfile pinning in the image, missing resource limits in docker-compose, no TLS termination in the default VPS setup, and no backup strategy for persistent data.

**Severity scale:** CRITICAL (deploy blocker) / HIGH (fix before production traffic) / MEDIUM (fix soon) / LOW (improvement) / INFO (observation)

---

## 1. Dockerfile Review

**File:** `Dockerfile`

### What is done well
- Uses `python:3.12-slim` (not full Debian -- good)
- Non-root user `dealsim` created and used via `USER dealsim`
- Data directory ownership set correctly
- HEALTHCHECK present with sensible intervals
- `--no-cache-dir` on pip install
- Single `EXPOSE 8000`

### Issues

#### 1.1 No lockfile copied -- builds are not reproducible (HIGH)

`uv.lock` exists in the repo but is excluded by `.dockerignore` (the `*.md` and general pattern do not exclude it, but `uv.lock` is simply never copied). The Dockerfile copies `pyproject.toml` and runs `uv pip install --system .`, which resolves dependencies at build time. Two builds on different days can produce different dependency versions.

**Fix:** Copy and use the lockfile:
```dockerfile
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY static/ static/
RUN uv pip install --system --locked .
```

#### 1.2 No multi-stage build -- image contains build tools (MEDIUM)

The final image includes `uv`, pip, setuptools, and compilation artifacts. A multi-stage build would drop the image size by 30-50 MB and reduce attack surface.

**Fix:**
```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY static/ static/
RUN uv pip install --system --target=/install .

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local/lib/python3.12/site-packages/
COPY src/ src/
COPY static/ static/
RUN useradd --create-home --shell /bin/bash dealsim \
    && mkdir -p /tmp/dealsim_data \
    && chown dealsim:dealsim /tmp/dealsim_data
USER dealsim
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "dealsim_mvp.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

#### 1.3 Layer caching suboptimal (LOW)

`COPY src/ src/` is done before `RUN uv pip install`, so any source code change invalidates the dependency install cache. Dependencies should be installed before source code is copied.

**Fix:** Split the install into two steps:
```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --locked .   # cached unless pyproject.toml changes
COPY src/ src/
COPY static/ static/
```
Note: this requires that `pyproject.toml` does not use dynamic version from source. Currently the version is hardcoded (`version = "0.1.0"`), so this works.

#### 1.4 HEALTHCHECK uses Python import -- slightly slow (INFO)

The healthcheck spawns a full Python interpreter on every check. For a slim container this is fine, but `curl` or `wget` would be faster. Since `python:3.12-slim` lacks curl, the current approach is the correct tradeoff. No action needed.

#### 1.5 Single worker in CMD (INFO)

`--workers 1` is appropriate for the Fly.io 256 MB VM but underutilizes the UpCloud 8 GB target. Consider making this configurable:
```dockerfile
CMD ["sh", "-c", "uvicorn dealsim_mvp.app:app --host 0.0.0.0 --port ${DEALSIM_PORT:-8000} --workers ${DEALSIM_WORKERS:-1}"]
```

---

## 2. docker-compose.yml Review

### What is done well
- `env_file` used (secrets not hardcoded)
- Named volumes for data persistence
- `restart: unless-stopped` appropriate for VPS
- Healthcheck matches Dockerfile healthcheck

### Issues

#### 2.1 No resource limits (HIGH for VPS deployment)

No `mem_limit`, `cpus`, or `deploy.resources` defined. On the UpCloud 2 CPU / 8 GB box, a runaway process could consume all memory and crash the host.

**Fix:**
```yaml
services:
  dealsim:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 4G
        reservations:
          cpus: "0.5"
          memory: 512M
```

#### 2.2 Port bound to all interfaces (MEDIUM)

`ports: "8000:8000"` binds to `0.0.0.0`, exposing the app directly without TLS. On a VPS with a reverse proxy (Caddy), bind to localhost only:
```yaml
ports:
  - "127.0.0.1:8000:8000"
```

#### 2.3 No logging configuration (MEDIUM)

No log driver or rotation configured. On a long-running VPS, container logs will grow unbounded.

**Fix:**
```yaml
services:
  dealsim:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

#### 2.4 Two volumes but unclear purpose of second (LOW)

`dealsim-analytics:/app/data` mounts a volume at `/app/data`, but the app writes to `DEALSIM_DATA_DIR=/tmp/dealsim_data` (the first volume). Verify whether `/app/data` is actually used. If not, remove it to avoid confusion.

---

## 3. Security Review

#### 3.1 No secrets leaked in image (PASS)

`.env` is in `.dockerignore`. No hardcoded keys in Dockerfile. `render.yaml` uses `generateValue: true` for the admin key. Good.

#### 3.2 Non-root execution (PASS)

Dockerfile creates and switches to `dealsim` user. Verified.

#### 3.3 Admin key passed via query parameter (MEDIUM -- pre-existing)

`/admin/stats?key=YOUR_KEY` passes the secret in the URL, which appears in access logs, browser history, and referrer headers. This was noted in the existing security review. Consider switching to an `Authorization` header.

#### 3.4 .dockerignore excludes tests and docs but not `data/` (LOW)

The `data/` directory in the repo root is not excluded. If it contains sample data or local state, it will be copied into the image via `COPY src/ src/` (it is outside `src/`, so actually safe). However, explicitly adding `data/` to `.dockerignore` is good hygiene.

#### 3.5 `uv.lock` not in image (see 1.1) -- supply chain risk (HIGH)

Without the lockfile, a compromised or yanked PyPI package could be pulled at build time. Pinning via the lockfile is the primary defense.

---

## 4. Cloud Platform Config Consistency

| Setting | Dockerfile | docker-compose | render.yaml | fly.toml | railway.json |
|---|---|---|---|---|---|
| Port | 8000 | 8000 | (auto) | 8000 | $PORT |
| Health path | /health | /health | /health | /health | /health |
| Workers | 1 | (from image) | (from image) | (from image) | 1 (override) |
| Env: DEALSIM_ENV | -- | development | production | production | -- |
| Restart policy | -- | unless-stopped | (platform) | (platform) | ON_FAILURE (3) |
| Non-root user | yes | yes (from image) | yes (from image) | yes (from image) | yes (from image) |

### Issues

#### 4.1 Railway overrides CMD (LOW)

`railway.json` sets `startCommand` which overrides the Dockerfile CMD. This is fine but creates a maintenance burden -- if the app entrypoint changes, two places need updating. Consider removing the startCommand and relying on the Dockerfile CMD.

#### 4.2 Render uses free plan (INFO)

Free plan spins down after 15 minutes of inactivity. First request after cold start takes ~30 seconds. Acceptable for MVP/demo, not for production.

#### 4.3 Fly.io VM is 256 MB shared CPU (INFO)

Adequate for the current app (FastAPI + in-memory sessions, no database). Will need scaling if concurrent users exceed ~50.

#### 4.4 No DEALSIM_ADMIN_KEY in fly.toml env block (CORRECT)

Secrets are set via `fly secrets set`, not in the config file. This is the right approach.

---

## 5. Production Readiness

| Concern | Status | Notes |
|---|---|---|
| HTTPS | PARTIAL | Fly.io: forced. Render/Railway: platform-handled. VPS: manual Caddy setup documented but not default. |
| Logging | MISSING | No structured logging config. No log rotation in compose. |
| Monitoring | MISSING | No Prometheus metrics, no error tracking (Sentry), no uptime monitoring. |
| Backups | MISSING | Feedback data in `/tmp/dealsim_data/feedback.json` has no backup strategy. Volume loss = data loss. |
| Rate limiting | PRESENT | In-memory rate limiter exists in the app. |
| Graceful shutdown | PARTIAL | Uvicorn handles SIGTERM, but no explicit shutdown hook for flushing data. |
| Session persistence | NONE | Sessions are in-memory. Server restart = all active sessions lost. Acceptable for MVP. |

### Recommended additions for production

1. **Backup cron** (VPS): `0 */6 * * * docker cp dealsim:/tmp/dealsim_data/feedback.json /backups/feedback-$(date +\%F-\%H).json`
2. **Uptime check**: Free tier at UptimeRobot or similar, hitting `/health` every 5 minutes.
3. **Structured logging**: Add `--log-config` to uvicorn or use Python's `logging.config` with JSON formatter.

---

## 6. UpCloud Compatibility (Ubuntu 24.04, 2 CPU / 8 GB RAM)

**Verdict: Fully compatible. Significantly over-provisioned for current app.**

| Resource | App requirement | UpCloud allocation | Headroom |
|---|---|---|---|
| CPU | ~0.1 cores idle, ~0.5 under load | 2 cores | 75-95% free |
| RAM | ~80-150 MB (Python + FastAPI + sessions) | 8 GB | 98% free |
| Disk | ~200 MB (image) + data | Depends on plan | Ample |
| Network | Low (JSON API, static HTML) | 1 Gbps | Ample |

### Deployment steps for UpCloud

The VPS instructions in DEPLOY.md (Option D) apply directly. Ubuntu 24.04 ships with systemd and supports Docker CE from the official repo. The `curl -fsSL https://get.docker.com | sh` one-liner works on Ubuntu 24.04.

### Optimization for the UpCloud box

With 8 GB RAM, increase workers to utilize both CPUs:
```
DEALSIM_WORKERS=3
```
Three workers on 2 CPUs is a reasonable ratio for I/O-bound FastAPI (1.5x CPU count).

---

## 7. Cost Optimization

#### 7.1 Image size can be reduced (LOW)

Current estimated image size: ~250-300 MB (python:3.12-slim + dependencies + uv + pip). With multi-stage build (section 1.2), this drops to ~180-200 MB. Faster pulls, less disk, lower egress on cloud platforms.

#### 7.2 UpCloud box is over-provisioned (INFO)

A 1 CPU / 2 GB instance would be sufficient for current load. The 2 CPU / 8 GB box is appropriate if the plan is to run additional services (monitoring, database, reverse proxy) on the same host.

#### 7.3 No unnecessary services in compose (PASS)

docker-compose.yml has a single service. No Redis, no database, no sidecar containers. Lean and appropriate for the current architecture.

---

## Summary of Findings

| # | Severity | Finding | Section |
|---|---|---|---|
| 1.1 | HIGH | No lockfile in image -- non-reproducible builds, supply chain risk | 1, 3 |
| 2.1 | HIGH | No resource limits in docker-compose | 2 |
| 1.2 | MEDIUM | No multi-stage build -- bloated image | 1 |
| 1.3 | LOW | Suboptimal layer caching order | 1 |
| 2.2 | MEDIUM | Port exposed on all interfaces | 2 |
| 2.3 | MEDIUM | No log rotation configured | 2 |
| 3.3 | MEDIUM | Admin key in URL query parameter | 3 |
| 2.4 | LOW | Unused second volume | 2 |
| 3.4 | LOW | `data/` not in .dockerignore | 3 |
| 4.1 | LOW | Railway duplicates CMD | 4 |
| 5 | MEDIUM | No monitoring, no backups, no structured logging | 5 |
| 1.5 | INFO | Workers not configurable via env var | 1 |
| 6 | INFO | UpCloud box over-provisioned (fine if intentional) | 6 |

**Priority order for fixes:**
1. Copy `uv.lock` into image and use `--locked` flag (HIGH, 2-minute fix)
2. Add resource limits to docker-compose.yml (HIGH, 1-minute fix)
3. Bind port to 127.0.0.1 in compose for VPS deployments (MEDIUM)
4. Add log rotation to compose (MEDIUM)
5. Implement multi-stage build (MEDIUM, 10-minute refactor)
6. Set up a backup cron for feedback data (MEDIUM)
