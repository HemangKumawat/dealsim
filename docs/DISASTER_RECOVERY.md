# DealSim Disaster Recovery Plan

**Infrastructure:** Single UpCloud VPS (2 CPU, 8GB RAM, Ubuntu 24.04, Frankfurt)
**Application:** FastAPI in Docker (nginx reverse proxy + certbot)
**Storage:** File-based (JSONL analytics, JSON sessions, no database)
**Last updated:** 2026-03-19

---

## 1. Data Inventory

| Data | Path on VPS | Type | Loss Impact |
|------|------------|------|-------------|
| Analytics events | `/tmp/dealsim_data/events.jsonl` (Docker volume `dealsim-data`) | Append-only JSONL | Medium -- lose usage metrics |
| Feedback | `/tmp/dealsim_data/feedback.jsonl` (Docker volume `dealsim-data`) | Append-only JSONL | High -- lose user feedback |
| Challenge submissions | `/tmp/dealsim_data/challenge_submissions.jsonl` (Docker volume `dealsim-data`) | Append-only JSONL | Low |
| User history | `/tmp/dealsim_data/user_history.jsonl` (Docker volume `dealsim-data`) | Append-only JSONL | Medium |
| Session store | `.dealsim_sessions.json` (project root in container) | Overwritten JSON | Low -- sessions are ephemeral (1hr TTL) |
| Environment vars | `/opt/dealsim/.env` | Secrets | Critical -- contains ADMIN_KEY, CORS config |
| nginx config | `/opt/dealsim/nginx/` | Config files | Medium -- rebuild takes 15min |
| SSL certificates | Docker volume `certbot-certs` (`/etc/letsencrypt/`) | Let's Encrypt certs | Low -- certbot re-issues in minutes |
| Docker compose | `/opt/dealsim/docker-compose.production.yml` | Config | Low -- in git |
| Application code | `/opt/dealsim/` (git clone) | Source | None -- in GitHub |

---

## 2. Recovery Objectives

### RPO (Recovery Point Objective): 1 hour

Analytics and feedback data are append-only JSONL files. Losing 1 hour of data is acceptable for an early-stage product. Backups run hourly.

### RTO (Recovery Time Objective): 30 minutes

Target breakdown:
- 5 min: Spin up new VPS (UpCloud API or console)
- 5 min: Run provisioning script (Docker, firewall, SSH keys)
- 5 min: Restore data from backup
- 5 min: Deploy application (`docker compose up`)
- 5 min: DNS update propagation (low TTL) + SSL cert issuance
- 5 min: Verification

---

## 3. Backup Strategy

### 3a. What Gets Backed Up

```
/opt/dealsim/.env                              # secrets
/opt/dealsim/nginx/                            # nginx configs
Docker volume: dealsim-data -> /tmp/dealsim_data/  # all JSONL + session data
Docker volume: certbot-certs -> /etc/letsencrypt/  # SSL certs (optional)
```

### 3b. Backup Schedule

| Data | Frequency | Retention | Method |
|------|-----------|-----------|--------|
| JSONL data files | Every hour | 7 daily + 4 weekly | Cron -> rsync to UpCloud Object Storage |
| `.env` + nginx configs | On change (daily minimum) | 30 days | Cron -> Object Storage |
| SSL certificates | Weekly | 2 copies | Cron -> Object Storage |
| Full VPS snapshot | Weekly (Sunday 03:00 UTC) | 4 snapshots | UpCloud API snapshot |

### 3c. Backup Destination

**Primary:** UpCloud Object Storage (S3-compatible, Frankfurt region, same DC = fast transfers)
- Bucket: `dealsim-backups`
- Path structure: `s3://dealsim-backups/{daily,weekly,monthly}/YYYY-MM-DD_HH-MM/`

**Secondary (optional future):** Cross-region copy to UpCloud Amsterdam or Backblaze B2 for geographic redundancy. Not required at current scale.

### 3d. Backup Verification

Automated (weekly, Sunday 04:00 UTC after snapshot):
1. Download latest backup tarball from Object Storage
2. Extract to `/tmp/backup-verify/`
3. Validate JSON/JSONL files parse without errors
4. Check file sizes are non-zero and within expected range
5. Compare line counts against previous backup (detect truncation)
6. Log result to `/var/log/dealsim-backup-verify.log`
7. Send alert on failure (see Monitoring section)

Manual (monthly):
1. Spin up a throwaway VPS from the latest UpCloud snapshot
2. Restore from Object Storage backup
3. Verify the application serves `/health` and `/admin/stats`
4. Destroy the throwaway VPS

---

## 4. Failure Scenarios and Runbook

### Scenario A: Application Crash (Container Dies)

**Detection:** Health check fails, uptime monitor alerts.
**Impact:** Service unavailable. No data loss (volumes persist).
**Resolution:**

```bash
# SSH into the VPS
ssh root@YOUR_VPS_IP

# Check what happened
cd /opt/dealsim
docker compose -f docker-compose.production.yml logs --tail=100 dealsim

# Restart the stack
docker compose -f docker-compose.production.yml restart dealsim

# If restart fails, rebuild
docker compose -f docker-compose.production.yml up -d --build dealsim

# Verify
curl -s https://dealsim.io/health | jq .
```

**RTO:** 2 minutes.

---

### Scenario B: VPS Unresponsive (Kernel Panic, Hardware Failure)

**Detection:** Uptime monitor alerts, SSH unreachable.
**Impact:** Full outage. Data on disk may be lost.
**Resolution:**

```bash
# 1. Try reboot via UpCloud console
#    UpCloud Hub -> Servers -> dealsim -> Restart

# 2. If reboot fails, restore from snapshot
#    UpCloud Hub -> Storage -> Backups -> Latest snapshot -> Deploy new server

# 3. If snapshot is stale, provision fresh VPS + restore from Object Storage
#    See "Full Recovery from Scratch" below
```

**RTO:** 15-30 minutes.

---

### Scenario C: Data Corruption

**Detection:** Application errors in logs, admin dashboard shows unexpected zeros.
**Impact:** Partial data loss.
**Resolution:**

```bash
ssh root@YOUR_VPS_IP
cd /opt/dealsim

# Stop the app to prevent further writes
docker compose -f docker-compose.production.yml stop dealsim

# Identify the corrupt file
docker run --rm -v dealsim-data:/data alpine sh -c \
  'for f in /data/*.jsonl; do echo "--- $f ---"; wc -l "$f"; python3 -c "
import json, sys
bad=0
for i,line in enumerate(open(\"$f\")):
  try: json.loads(line)
  except: bad+=1; print(f\"Line {i}: corrupt\")
print(f\"Bad lines: {bad}\")
" 2>/dev/null || echo "no python"; done'

# Restore specific file from latest backup
./scripts/restore.sh --file feedback.jsonl

# Restart
docker compose -f docker-compose.production.yml start dealsim
```

**RTO:** 10 minutes.

---

### Scenario D: Bad Deployment (Broken Code)

**Detection:** Health check fails immediately after deploy, error rate spikes.
**Impact:** Service unavailable or degraded.
**Resolution:**

```bash
ssh root@YOUR_VPS_IP
cd /opt/dealsim

# Rollback to previous git commit
git log --oneline -5          # find the last known-good commit
git checkout <GOOD_COMMIT>

# Rebuild and restart
docker compose -f docker-compose.production.yml up -d --build

# Verify
curl -s https://dealsim.io/health | jq .
```

Alternative -- rollback to previous Docker image:

```bash
# List recent images
docker images dealsim --format '{{.ID}} {{.CreatedAt}}'

# Tag current as broken, restore previous
docker tag dealsim:latest dealsim:broken
docker tag <PREVIOUS_IMAGE_ID> dealsim:latest

# Restart with old image (no rebuild)
docker compose -f docker-compose.production.yml up -d --no-build
```

**RTO:** 5 minutes.

---

### Scenario E: SSL Certificate Expiry

**Detection:** Browser warnings, monitoring alerts on cert expiry date.
**Impact:** Users see security warning, may not be able to access site.
**Resolution:**

```bash
ssh root@YOUR_VPS_IP
cd /opt/dealsim

# Force renewal
docker compose -f docker-compose.production.yml run --rm certbot \
  certbot renew --force-renewal

# Reload nginx to pick up new cert
docker compose -f docker-compose.production.yml exec nginx nginx -s reload
```

**RTO:** 2 minutes.

---

### Scenario F: Disk Full

**Detection:** Application write errors, monitoring disk usage alert.
**Impact:** New data cannot be written, application may crash.
**Resolution:**

```bash
ssh root@YOUR_VPS_IP

# Check disk usage
df -h
du -sh /var/lib/docker/volumes/*

# Clean Docker resources
docker system prune -f
docker image prune -a -f

# If JSONL files are huge, archive old data
docker run --rm -v dealsim-data:/data alpine sh -c \
  'wc -l /data/*.jsonl'

# Archive events older than 30 days (keep recent, compress old)
# See backup script for archive rotation
```

**RTO:** 5 minutes.

---

## 5. Full Recovery from Scratch

If the VPS is completely gone and snapshots are unavailable:

```bash
# ---------------------------------------------------------------
# Step 1: Provision new VPS (UpCloud console or API)
# ---------------------------------------------------------------
# - Plan: 2 CPU, 8GB RAM, Ubuntu 24.04, Frankfurt
# - Add SSH key during creation

# ---------------------------------------------------------------
# Step 2: Initial setup (SSH in as root)
# ---------------------------------------------------------------
ssh root@NEW_VPS_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install s3cmd for Object Storage access
apt update && apt install -y s3cmd

# Configure s3cmd for UpCloud Object Storage
s3cmd --configure
# Enter: Access Key, Secret Key, Host = YOUR_BUCKET.s3.REGION.upcloud.com

# ---------------------------------------------------------------
# Step 3: Clone application
# ---------------------------------------------------------------
mkdir -p /opt
cd /opt
git clone https://github.com/YOUR_USERNAME/dealsim.git
cd dealsim

# ---------------------------------------------------------------
# Step 4: Restore secrets and configs from backup
# ---------------------------------------------------------------
# Run the restore script
./scripts/restore.sh --full

# Or manually:
s3cmd get s3://dealsim-backups/latest/env-backup.enc /opt/dealsim/.env
s3cmd get s3://dealsim-backups/latest/nginx-backup.tar.gz /tmp/
tar xzf /tmp/nginx-backup.tar.gz -C /opt/dealsim/nginx/

# ---------------------------------------------------------------
# Step 5: Restore data volumes
# ---------------------------------------------------------------
# Create the Docker volumes
docker volume create dealsim-data
docker volume create dealsim-analytics

# Restore JSONL data
s3cmd get s3://dealsim-backups/latest/data-backup.tar.gz /tmp/
docker run --rm -v dealsim-data:/data -v /tmp:/backup alpine \
  tar xzf /backup/data-backup.tar.gz -C /data

# ---------------------------------------------------------------
# Step 6: Deploy
# ---------------------------------------------------------------
docker compose -f docker-compose.production.yml up -d --build

# ---------------------------------------------------------------
# Step 7: SSL certificate
# ---------------------------------------------------------------
# Initial cert issuance (see docs/NGINX_SSL_GUIDE.md for full steps)
# Temporarily comment out SSL lines in nginx config, start with HTTP only
# Then run certbot and uncomment SSL

# ---------------------------------------------------------------
# Step 8: DNS
# ---------------------------------------------------------------
# Update A record for dealsim.io to point to NEW_VPS_IP
# TTL should be 300s (5 min) for fast propagation

# ---------------------------------------------------------------
# Step 9: Verify
# ---------------------------------------------------------------
curl -s https://dealsim.io/health | jq .
curl -s "https://dealsim.io/admin/stats?key=YOUR_ADMIN_KEY" | head -20
```

---

## 6. Failover Plan

### Current: Manual Failover (appropriate for single-VPS, early-stage)

There is no automatic failover. When the VPS dies:

1. Monitoring detects the outage (target: within 5 minutes)
2. Engineer receives alert (PagerDuty/email/Telegram)
3. Engineer SSHes in or provisions new VPS
4. Recovery follows the runbook above

### Future: Automated Failover (when revenue justifies cost)

When the product grows beyond hobby stage:
- Add a second VPS in a different UpCloud region (Amsterdam)
- Use UpCloud load balancer or Cloudflare as DNS-based failover
- Replicate data via rsync cron between the two VPS instances
- Estimated additional cost: ~10 EUR/month

This is not justified yet. The manual RTO of 30 minutes is acceptable for a pre-revenue product.

---

## 7. Monitoring

### Health Checks

| Check | Tool | Interval | Alert Threshold |
|-------|------|----------|-----------------|
| HTTP health endpoint | UptimeRobot (free tier) or `curl` cron | 1 min | 3 consecutive failures |
| SSL certificate expiry | UptimeRobot SSL monitor | Daily | < 14 days remaining |
| Disk usage | Cron script on VPS | 5 min | > 80% |
| Docker container status | Cron script on VPS | 1 min | Any container unhealthy |
| Backup freshness | Cron script on VPS | Hourly | Last backup > 2 hours old |

### Alerting

Set up a lightweight alert pipeline:

```bash
# /opt/dealsim/scripts/monitor.sh (run via cron every minute)

#!/usr/bin/env bash
HEALTH=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HEALTH" != "200" ]; then
  # Send Telegram alert (or email via msmtp, or webhook)
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" \
    -d text="ALERT: DealSim health check failed (HTTP $HEALTH) at $(date -u)"
fi

# Disk check
DISK_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt 80 ]; then
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" \
    -d text="WARNING: DealSim disk usage at ${DISK_PCT}% at $(date -u)"
fi
```

### Log Monitoring

```bash
# Watch for errors in real-time
docker compose -f docker-compose.production.yml logs -f --tail=50 dealsim 2>&1 | grep -i error

# Check nginx error log
docker compose -f docker-compose.production.yml exec nginx cat /var/log/nginx/error.log | tail -20
```

---

## 8. Deployment Safety

### Pre-deploy Checklist

1. Run tests locally: `pytest tests/`
2. Build Docker image locally: `docker compose build`
3. Check health endpoint on local build: `curl localhost:8000/health`
4. Commit and push to GitHub
5. SSH to VPS, `git pull`, rebuild, verify

### Deploy Script (safe rollback built in)

```bash
#!/usr/bin/env bash
# deploy-safe.sh -- deploy with automatic rollback on health check failure
set -euo pipefail

cd /opt/dealsim

# Save current commit for rollback
PREV_COMMIT=$(git rev-parse HEAD)

# Pull latest
git pull origin main

# Build new image
docker compose -f docker-compose.production.yml build

# Restart with new image
docker compose -f docker-compose.production.yml up -d

# Wait for health check
echo "Waiting 15s for container startup..."
sleep 15

HEALTH=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
if [ "$HEALTH" != "200" ]; then
  echo "HEALTH CHECK FAILED ($HEALTH) -- rolling back to $PREV_COMMIT"
  git checkout "$PREV_COMMIT"
  docker compose -f docker-compose.production.yml up -d --build
  sleep 10
  echo "Rollback complete. Verify: curl https://dealsim.io/health"
  exit 1
fi

echo "Deploy successful. Health: $HEALTH"
```

---

## 9. Secrets Management

### Current Secrets

| Secret | Location | Rotation Schedule |
|--------|----------|-------------------|
| `DEALSIM_ADMIN_KEY` | `.env` | Every 90 days |
| `DEALSIM_CORS_ORIGINS` | `.env` | On domain change |
| UpCloud API credentials | Local machine only | Every 90 days |
| S3 access keys (Object Storage) | `/root/.s3cfg` on VPS | Every 90 days |
| SSH key | `~/.ssh/authorized_keys` on VPS | On compromise only |

### Backup of Secrets

The `.env` file is included in backups but is encrypted with `gpg` symmetric encryption before upload to Object Storage. The passphrase is stored separately (password manager, never on the VPS).

```bash
# Encrypt before backup
gpg --symmetric --cipher-algo AES256 -o /tmp/env-backup.enc /opt/dealsim/.env

# Decrypt during restore
gpg --decrypt /tmp/env-backup.enc > /opt/dealsim/.env
```

---

## 10. Testing This Plan

### Quarterly DR Drill (15 minutes)

1. Verify backup script runs and produces non-empty tarballs
2. Download latest backup, extract, validate file integrity
3. Confirm monitoring alerts fire (temporarily stop the container)
4. Review and update this document if anything changed

### Annual Full Recovery Test (1 hour)

1. Provision a throwaway VPS
2. Follow "Full Recovery from Scratch" exactly as written
3. Verify application works end-to-end
4. Document any steps that were missing or wrong
5. Destroy the throwaway VPS
