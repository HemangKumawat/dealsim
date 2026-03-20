# DealSim — Deployment Guide

---

## Prerequisites

For VPS deployment (the recommended production path):

- A VPS with at least 1 vCPU and 512 MB RAM (the app itself uses under 200 MB)
- Ubuntu 24.04 or Debian 12
- A domain name with an A record pointing to the VPS IP
- Ports 80 and 443 open in the firewall
- Docker and the compose plugin installed (see below)
- Git

For cloud platform deployment (Render, Fly.io, Railway), only a GitHub account is needed.

---

## Option A: VPS with Docker (Recommended)

This is the full production setup: nginx + FastAPI + certbot in three containers, SSL via Let's Encrypt, automatic certificate renewal.

### 1. Install Docker

```bash
ssh root@YOUR_VPS_IP
apt update && apt install -y docker.io docker-compose-plugin
systemctl enable --now docker
```

### 2. Clone and configure

```bash
cd /opt
git clone https://github.com/YOUR_USERNAME/dealsim.git
cd dealsim
cp .env.example .env
nano .env
```

Minimum required changes in `.env`:

```bash
DEALSIM_ADMIN_KEY=<output of: openssl rand -hex 32>
DEALSIM_CORS_ORIGINS=https://yourdomain.com
DEALSIM_DOMAIN=yourdomain.com
DEALSIM_EMAIL=you@yourdomain.com
```

### 3. Set your domain in the nginx config

```bash
DOMAIN="yourdomain.com"
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" nginx/dealsim.conf
```

### 4. Obtain the initial SSL certificate

The HTTPS server block in nginx cannot start without a certificate. Bootstrap it in two stages:

```bash
# Stage 1: start nginx in HTTP-only mode
# Comment out the HTTPS server block in nginx/dealsim.conf, then:
docker compose up -d nginx

# Stage 2: issue the certificate
docker compose run --rm certbot \
  certbot certonly --webroot -w /var/www/certbot \
  --email "$DEALSIM_EMAIL" \
  --agree-tos --no-eff-email \
  -d "$DOMAIN"

# Stage 3: uncomment the HTTPS server block, then bring up the full stack
docker compose down
docker compose up -d
```

Or use the automated deploy script, which handles this sequence for you:

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### 5. Verify

```bash
# All three containers should be healthy
docker compose ps

# Health check
curl https://yourdomain.com/health
# Expected: {"status":"healthy","version":"..."}

# Admin dashboard (requires the key you set in .env)
curl -H "Authorization: YOUR_ADMIN_KEY" https://yourdomain.com/api/admin/stats
```

---

## Option B: Render.com (Free Tier, One-Click)

**Time: ~3 minutes**

1. Push the repo to GitHub:

   ```bash
   git init && git add -A && git commit -m "Initial commit"
   gh repo create dealsim --public --push
   ```

2. Go to [dashboard.render.com/new/web-service](https://dashboard.render.com/new/web-service) and connect the repo. Render auto-detects `render.yaml`.

3. Click **Create Web Service** and wait for the build (~2 min).

4. In Render dashboard → Environment, add:
   - `DEALSIM_ADMIN_KEY` = your secret key
   - `DEALSIM_CORS_ORIGINS` = `https://your-app.onrender.com`

5. Verify: `curl https://your-app.onrender.com/health`

**Note:** The free tier spins down after 15 minutes of inactivity. The first request after spin-down takes ~30 seconds.

For persistent data (feedback, analytics), add a Render Disk ($0.25/GB/mo) mounted at `/app/data` and set `DEALSIM_DATA_DIR=/app/data`.

---

## Option C: Fly.io (Free Tier)

**Time: ~4 minutes**

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Authenticate
fly auth login   # or: fly auth signup

# Deploy (fly.toml is pre-configured for Frankfurt)
cd dealsim
fly launch --copy-config --yes

# Set secrets
fly secrets set DEALSIM_ADMIN_KEY=your-secret-key
fly secrets set DEALSIM_CORS_ORIGINS=https://dealsim.fly.dev

fly deploy
```

Verify:

```bash
fly status
curl https://dealsim.fly.dev/health
fly logs
```

For persistent data: `fly volumes create dealsim_data --size 1` and set `DEALSIM_DATA_DIR=/app/data` in the secrets.

**Note:** The free tier includes 3 shared-cpu-1x VMs with 256 MB RAM. Auto-stop/start is enabled in `fly.toml` to stay within the free allowance.

---

## Option D: Railway

**Time: ~3 minutes**

1. Go to [railway.com/new](https://railway.com/new), click **Deploy from GitHub repo**, select the `dealsim` repo.

2. Railway auto-detects `railway.json` and the Dockerfile.

3. Add environment variables in the Railway dashboard:
   - `DEALSIM_ADMIN_KEY`
   - `DEALSIM_ENV=production`
   - `DEALSIM_CORS_ORIGINS=https://your-app.up.railway.app`

4. Railway assigns a public URL automatically. Settings → Networking → Generate Domain.

5. Verify: `curl https://your-app.up.railway.app/health`

**Note:** The free tier gives $5/month credit (~500 hours of a small container).

---

## Environment Configuration

All configuration is via `.env`. Copy `.env.example` to `.env` — never commit `.env`.

| Variable | Required | Description |
|---|---|---|
| `DEALSIM_ENV` | no | `production` or `development` |
| `DEALSIM_HOST` | no | Uvicorn bind address (default `0.0.0.0`) |
| `DEALSIM_PORT` | no | Internal port (default `8000`) |
| `DEALSIM_WORKERS` | no | Uvicorn workers (default `2`) |
| `DEALSIM_CORS_ORIGINS` | **yes** | Comma-separated allowed origins |
| `DEALSIM_ADMIN_KEY` | **yes** | Admin dashboard key — `openssl rand -hex 32` |
| `DEALSIM_MAX_SESSIONS` | no | Max in-memory sessions (default `1000`) |
| `DEALSIM_SESSION_TTL_HOURS` | no | Idle session expiry (default `1`) |
| `DEALSIM_DATA_DIR` | no | JSONL data directory (default `/app/data`) |
| `DEALSIM_DOMAIN` | yes (SSL) | Domain name, no scheme, no trailing slash |
| `DEALSIM_EMAIL` | yes (SSL) | Let's Encrypt contact address |
| `BACKUP_DIR` | no | Local backup archive path |
| `BACKUP_RETAIN_DAYS` | no | Days of archives to keep (default `7`) |
| `TELEGRAM_BOT_TOKEN` | no | Backup alert bot token |
| `TELEGRAM_CHAT_ID` | no | Backup alert chat ID |

---

## Updates and Rollbacks

### Deploying an update

```bash
cd /opt/dealsim
git pull
docker compose up -d --build
```

The compose file uses `restart: unless-stopped` — the app comes back automatically after the build. Downtime during a rebuild is typically under 10 seconds.

### Rolling back

```bash
git log --oneline -10        # find the commit to roll back to
git checkout <commit-hash>
docker compose up -d --build
```

Or restore from a backup (see Backup and Restore below).

---

## Monitoring and Health Checks

### Container health

```bash
docker compose ps                  # shows health status of all three containers
docker compose logs -f app         # follow app logs
docker compose logs -f nginx       # follow nginx access/error logs
```

### Health endpoint

```
GET /health
```

Returns:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "active_sessions": 3,
  "uptime_seconds": 14400,
  "error_count": 0
}
```

The Docker healthcheck polls this endpoint every 30 seconds. If it fails 3 times in a row, Docker marks the container unhealthy and restarts it.

### Admin dashboard

Browser: `https://yourdomain.com/admin/stats` (prompts for key)

JSON API (for external monitoring):

```bash
curl -H "Authorization: YOUR_ADMIN_KEY" https://yourdomain.com/api/admin/stats
```

Returns: total sessions, completion rate, average score, feature usage counts, scenario popularity, and recent feedback.

Extended analytics (scores by scenario and difficulty, sessions today/this week):

```bash
curl -H "Authorization: YOUR_ADMIN_KEY" https://yourdomain.com/api/admin/analytics
```

### Certificate expiry

The certbot container attempts renewal every 12 hours. Certbot skips renewal if the certificate is not within 30 days of expiry. To check certificate status:

```bash
docker compose exec certbot certbot certificates
```

---

## Backup and Restore

### What needs backing up

All persistent state lives in the `app-data` Docker volume, mounted at `/app/data` inside the container. This directory contains:

- `sessions/*.json` — completed session records
- `events.jsonl` — analytics event log
- `feedback.jsonl` — user feedback submissions

The application code, nginx config, and certificates are all version-controlled or renewable — they do not need to be backed up separately.

### Manual backup

```bash
# Dump the app-data volume to a compressed archive
docker run --rm \
  -v dealsim_app-data:/data:ro \
  -v /opt/backups:/backup \
  alpine tar czf /backup/dealsim-data-$(date +%Y%m%d).tar.gz -C /data .
```

### Automated backup

The repo includes `scripts/backup.sh`. Configure `BACKUP_DIR` and `BACKUP_RETAIN_DAYS` in `.env`, then schedule it:

```bash
chmod +x scripts/backup.sh

# Add to root crontab (runs daily at 3 AM)
crontab -e
# Add: 0 3 * * * /opt/dealsim/scripts/backup.sh >> /var/log/dealsim-backup.log 2>&1
```

With `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` set, the script sends a Telegram message on success or failure.

### Restore

```bash
# Stop the app
docker compose down

# Restore the volume from archive
docker run --rm \
  -v dealsim_app-data:/data \
  -v /opt/backups:/backup:ro \
  alpine sh -c "cd /data && tar xzf /backup/dealsim-data-YYYYMMDD.tar.gz"

# Restart
docker compose up -d
```

---

## Disaster Recovery

If the VPS is unrecoverable:

1. Provision a new VPS (same or different provider)
2. Install Docker
3. Clone the repo: `git clone ...`
4. Restore `.env` (keep a copy outside the VPS — it contains secrets)
5. Restore the data volume from the most recent backup
6. Update the DNS A record to the new IP
7. Run `./scripts/deploy.sh` to get a fresh SSL certificate
8. Verify with `curl https://yourdomain.com/health`

Full RTO from a blank VPS with a backup archive available: approximately 15 minutes.

---

## Resource Requirements

The production Docker resource limits are set in `docker-compose.yml`:

| Container | CPU limit | Memory limit |
|---|---|---|
| `app` (FastAPI) | 0.50 CPU | 512 MB |
| `nginx` | 0.25 CPU | 128 MB |
| `certbot` | 0.10 CPU | 64 MB |

A VPS with 1 shared vCPU and 1 GB RAM handles these limits comfortably under normal load. The in-memory session store is capped at `DEALSIM_MAX_SESSIONS` (default 1000) — at roughly 10 KB per session, that is 10 MB of session data at maximum capacity.
