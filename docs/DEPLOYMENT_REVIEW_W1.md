# DealSim Deployment Configuration Review (W1)

Date: 2026-03-19
Reviewer: DevOps Engineer (automated review)

---

## CRITICAL Issues

### 1. CORS Environment Variable Name Mismatch (BROKEN in production)

**Severity: CRITICAL** -- CORS will default to `*` (allow all) on every deployment.

The app reads `CORS_ORIGINS`:
```python
# src/dealsim_mvp/app.py line 71
allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
```

But every config file sets `DEALSIM_CORS_ORIGINS`:
- `.env.example`: `DEALSIM_CORS_ORIGINS=https://yourdomain.com`
- `render.yaml`: `key: DEALSIM_CORS_ORIGINS`
- `DEPLOY.md`: `fly secrets set DEALSIM_CORS_ORIGINS=...`

The variable is never read. CORS is wide open on all deployments.

**Fix (choose one):**

Option A -- change the app to match configs (preferred, no config redeploy needed):
```python
# src/dealsim_mvp/app.py line 71
allowed_origins = os.environ.get("DEALSIM_CORS_ORIGINS", "*").split(",")
```

Option B -- change all configs to match the app (requires redeploying everything):
Replace `DEALSIM_CORS_ORIGINS` with `CORS_ORIGINS` in `.env.example`, `render.yaml`, `DEPLOY.md`.

---

## HIGH Issues

### 2. Dockerfile runs as root

The container runs all processes as `root`. If the uvicorn process is compromised, the attacker has full container access.

**Fix -- add a non-root user after the RUN install step:**
```dockerfile
# After RUN uv pip install --system .
RUN useradd --create-home --shell /bin/bash dealsim
USER dealsim
```

Also ensure the data directory is owned by that user:
```dockerfile
RUN mkdir -p /tmp/dealsim_data && chown dealsim:dealsim /tmp/dealsim_data
```

### 3. docker-compose.yml health check uses `curl`, but the image has no `curl`

The Dockerfile uses `python:3.12-slim`, which does not include `curl`. The Dockerfile's own HEALTHCHECK correctly uses Python's `urllib`, but `docker-compose.yml` line 16 uses:
```yaml
test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
```

This health check will always fail with "exec: curl: not found".

**Fix:**
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s
```

### 4. `uv.lock` excluded by `.dockerignore` (via `*.md` not being the issue, but `uv.lock` not being copied)

The `Dockerfile` does `COPY pyproject.toml .` but does not copy `uv.lock`. This means builds are not reproducible -- `uv pip install` will resolve to whatever versions are latest at build time, not the locked versions.

**Fix -- add uv.lock to the COPY:**
```dockerfile
COPY pyproject.toml uv.lock ./
```

And use it during install:
```dockerfile
RUN uv pip install --system --frozen .
```

(Note: `--frozen` tells uv to use the lockfile strictly. If uv does not support `--frozen` with `pip install`, use `uv sync --system --frozen` instead, depending on your uv version.)

### 5. No `data/` directory in Docker image but `docker-compose.yml` mounts to `/app/data`

`docker-compose.yml` line 13 mounts `dealsim-analytics:/app/data`, but the Dockerfile never creates `/app/data` and nothing in the app code references `/app/data` as a path. The `data/` folder in the repo contains runtime JSONL files that should not be baked into the image.

**Fix:** Either remove the volume mount if unused:
```yaml
volumes:
  - dealsim-data:/tmp/dealsim_data
  # Remove: - dealsim-analytics:/app/data
```

Or, if analytics data should persist at `/app/data`, add to the Dockerfile:
```dockerfile
RUN mkdir -p /app/data
```
And ensure the app actually writes there (currently it writes to `DEALSIM_DATA_DIR=/tmp/dealsim_data`).

---

## MEDIUM Issues

### 6. render.yaml uses Render free plan with ephemeral disk

`render.yaml` sets `plan: free` and stores data at `/tmp/dealsim_data`. On free plan, the filesystem is ephemeral -- all feedback and analytics data is lost on every redeploy or spin-down.

The `DEPLOY.md` mentions this but does not include the Render Disk config inline.

**Fix -- add disk config to render.yaml for paid plans, or add a comment:**
```yaml
# For data persistence, add a Render Disk:
# disk:
#   name: dealsim-data
#   mountPath: /tmp/dealsim_data
#   sizeGB: 1
```

### 7. fly.toml sets `min_machines_running = 0` with `auto_stop_machines = "stop"`

This means the app will be completely stopped when idle. Combined with 256MB RAM, cold starts will be slow (~10-30s). The health check may fail during cold start since `grace_period` is only 10s and the Python image + uvicorn startup can take longer.

**Fix -- increase grace period:**
```toml
[[http_service.checks]]
  grace_period = "30s"
```

### 8. railway.json overrides Dockerfile CMD with a `startCommand`

The `railway.json` has:
```json
"startCommand": "uvicorn dealsim_mvp.app:app --host 0.0.0.0 --port $PORT --workers 1"
```

This uses `$PORT` (Railway's dynamic port) which is correct for Railway, but it bypasses the Dockerfile's CMD (which uses port 8000). This is technically correct behavior for Railway, but means the health check in the Dockerfile (which hits port 8000) will fail during Railway's build-phase health check if Railway runs a container health check before applying its own start command.

**Status:** Acceptable as-is. Railway replaces CMD with startCommand. No fix needed, but worth documenting.

### 9. Admin key exposed in HTML response

`app.py` line 239 renders the admin key directly into the HTML:
```python
<a href="/api/admin/stats?key={admin_key}" ...>
```

If someone accesses the admin dashboard URL, the key is embedded in the page source and could be cached by browsers or proxies.

**Fix:** Remove the key from the rendered HTML link:
```python
<a href="/api/admin/stats?key=YOUR_KEY" style="color:#f95c5c;">/api/admin/stats?key=...</a>
```

### 10. Rate limiter memory leak

`_rate_store` in `app.py` (line 41) grows unboundedly. Each unique IP adds an entry that is never fully removed -- old timestamps within a key are pruned, but empty keys persist forever. Under sustained traffic from many IPs, this will consume increasing memory.

**Fix -- prune empty keys periodically, or use a TTL dict:**
```python
def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    window = now - 60.0
    timestamps = _rate_store[client_ip]
    _rate_store[client_ip] = [t for t in timestamps if t > window]
    if not _rate_store[client_ip]:
        del _rate_store[client_ip]  # <-- add this line
        # First request from this IP in the window, allow it
        _rate_store[client_ip].append(now)
        return True
    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        return False
    _rate_store[client_ip].append(now)
    return True
```

---

## LOW Issues

### 11. `.dockerignore` excludes `*.md` which removes `README.md` (acceptable) but also `CHANGELOG.md`

Not a functional issue since neither is needed at runtime. Noted for awareness.

### 12. No `.env` file in `.dockerignore` pattern handles `.env.*` variants

`.dockerignore` excludes `.env` but not `.env.local`, `.env.production`, etc. If someone creates these, they could be copied into the image.

**Fix:**
```
.env*
!.env.example
```

### 13. No Procfile for Heroku compatibility

If Heroku deployment is ever needed, a `Procfile` is required.

**Fix -- create `Procfile`:**
```
web: uvicorn dealsim_mvp.app:app --host 0.0.0.0 --port $PORT --workers 1
```

### 14. No `vercel.json` for Vercel

DealSim is a Python FastAPI app. Vercel's Python support is limited to serverless functions and would require significant restructuring. A `vercel.json` is not recommended unless the architecture changes. Not a gap -- just not a fit for Vercel's model.

---

## Summary Table

| # | Severity | Issue | File(s) |
|---|----------|-------|---------|
| 1 | CRITICAL | CORS env var name mismatch -- CORS wide open | app.py, .env.example, render.yaml, DEPLOY.md |
| 2 | HIGH | Container runs as root | Dockerfile |
| 3 | HIGH | docker-compose health check uses missing `curl` | docker-compose.yml |
| 4 | HIGH | uv.lock not copied -- non-reproducible builds | Dockerfile |
| 5 | HIGH | Phantom volume mount `/app/data` | docker-compose.yml |
| 6 | MEDIUM | Ephemeral disk on Render free plan | render.yaml |
| 7 | MEDIUM | Cold start may exceed health check grace period | fly.toml |
| 8 | MEDIUM | Railway startCommand overrides Dockerfile CMD | railway.json |
| 9 | MEDIUM | Admin key leaked in HTML source | app.py |
| 10 | MEDIUM | Rate limiter unbounded memory growth | app.py |
| 11 | LOW | .dockerignore excludes all .md files | .dockerignore |
| 12 | LOW | .env variants not excluded from Docker build | .dockerignore |
| 13 | LOW | No Procfile for Heroku | (missing file) |
| 14 | LOW | No vercel.json | N/A (not recommended) |

---

## What Works Well

- **Dockerfile structure** is clean -- slim base, uv for fast installs, single-stage build.
- **Health check endpoint** at `/health` is consistent across all platforms.
- **Static file serving** has a robust multi-path fallback strategy.
- **fly.toml** has correct internal port, auto-stop, and shared CPU config.
- **railway.json** correctly uses `$PORT` for Railway's dynamic port assignment.
- **DEPLOY.md** is thorough with four deployment options and verification steps.
- **Rate limiting** exists and skips health checks (correct).
- **App factory pattern** (`create_app()`) is clean and testable.
