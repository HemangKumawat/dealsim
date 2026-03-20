# UpCloud Resource Plan — DealSim Production Deployment

**Server:** UpCloud General Purpose, 2 vCPU / 8 GB RAM, Ubuntu 24.04 LTS, Frankfurt DC
**Stack:** Docker (3 containers: FastAPI app, nginx, certbot)
**Date:** 2026-03-19

---

## 1. Memory Budget (8192 MB total)

| Component                        | Estimate     | Notes                                                |
|----------------------------------|-------------|------------------------------------------------------|
| Ubuntu 24.04 base OS             | ~400 MB      | systemd, kernel, sshd, journald, cron               |
| Docker engine (dockerd + containerd) | ~200 MB  | Daemon overhead, image layer caching                 |
| DealSim container (Python 3.12 + FastAPI + uvicorn, 1 worker) | ~150-250 MB | python:3.12-slim base ~120 MB, app code ~20 MB, per-request ~0.5-2 MB |
| Nginx container (nginx:1.27-alpine) | ~15-30 MB | Alpine base + 2 worker processes, minimal footprint  |
| Certbot container                | ~30-50 MB    | Sleeps 12h between renewal checks, near-zero active RAM |
| Filesystem cache (kernel)        | ~1-2 GB      | Linux uses free RAM for page cache — improves I/O, released under pressure |
| **Spike reserve**                | **~1.5 GB**  | For sudden traffic bursts, log processing, apt upgrades |
| **Total committed**              | **~850 MB**  | Without page cache                                   |
| **Available for growth**         | **~5.8 GB**  | Comfortable headroom for scaling workers             |

**Key insight:** With 1 uvicorn worker, the app uses under 1 GB committed memory. This server has substantial headroom. You could run 4 uvicorn workers (each ~150 MB) and still have 5+ GB free.

**Memory limits to set in docker-compose.production.yml:**
```yaml
dealsim:
  deploy:
    resources:
      limits:
        memory: 2G      # Hard ceiling — prevents runaway processes
      reservations:
        memory: 256M     # Guaranteed minimum
nginx:
  deploy:
    resources:
      limits:
        memory: 256M
```

---

## 2. CPU Budget (2 vCPU)

### Uvicorn Workers

The Dockerfile specifies `--workers 1`. The standard formula is `2 * CPU_cores + 1`, but that assumes CPU-bound work. DealSim is I/O-bound (HTTP request/response, JSON serialization, file I/O to `/tmp/dealsim_data`), so:

| Config             | Workers | When to use                                      |
|--------------------|---------|--------------------------------------------------|
| **Conservative**   | 1       | Current setting. Fine for <50 concurrent users   |
| **Recommended**    | 2       | Matches core count. Good for 50-200 concurrent   |
| **Maximum**        | 3       | Leaves 1 core shared between nginx + OS + Docker |

**Recommendation: 2 workers.** Change Dockerfile CMD to:
```
CMD ["uvicorn", "dealsim_mvp.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### CPU consumers breakdown

| Component               | CPU share  | Notes                                           |
|-------------------------|-----------|--------------------------------------------------|
| Uvicorn workers (2)     | ~70-80%    | Primary workload                                |
| Nginx (2 workers)       | ~5-10%     | TLS termination, static serving, proxying       |
| Docker engine           | ~2-5%      | Container orchestration, health checks          |
| OS (systemd, sshd, etc) | ~2-5%     | Minimal background load                         |
| Certbot                 | ~0%        | Wakes briefly every 12h                         |

**TLS impact:** Nginx handles TLS termination. With TLS 1.3 and session resumption enabled in your config, the CPU cost per connection is ~0.5ms for resumed sessions. Not a bottleneck at this scale.

---

## 3. Disk Budget

UpCloud General Purpose plans include 80 GB NVMe storage.

| Item                     | Size estimate | Growth rate              |
|--------------------------|--------------|--------------------------|
| Ubuntu 24.04 base        | ~3 GB         | Slow (apt upgrades)     |
| Docker images (pulled)   | ~500 MB       | python:3.12-slim ~150 MB, nginx:alpine ~45 MB, certbot ~100 MB, built dealsim image ~200 MB |
| Docker build cache        | ~500 MB-1 GB | Grows with rebuilds — prune periodically |
| App data (dealsim-data volume) | ~10-100 MB | Depends on session/analytics volume |
| Analytics data (dealsim-analytics) | ~10-100 MB | JSON files, grows with usage |
| SSL certificates         | <1 MB         | Negligible                |
| Nginx logs               | ~50-500 MB/mo | Depends on traffic — configure rotation |
| System logs (journald)   | ~200 MB       | With default retention   |
| **Backups (local copy)**  | ~1-5 GB      | If keeping 7 daily snapshots of app data |
| **Total baseline**       | **~6-8 GB**   |                          |
| **Available**            | **~70 GB**    | Plenty of room           |

**Maintenance commands to schedule (weekly cron):**
```bash
docker system prune -f --filter "until=168h"   # Remove dangling images/containers older than 7 days
journalctl --vacuum-size=200M                    # Cap system logs
```

**Log rotation for nginx** — add to nginx container or host:
```
/var/log/nginx/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
}
```

---

## 4. Network

### UpCloud Transfer Limits

UpCloud General Purpose plans include **5 TB/month outbound** transfer on the Frankfurt DC. Inbound is free and unlimited.

### Expected bandwidth

| Traffic type               | Per request  | At 10k requests/day | At 100k req/day |
|----------------------------|-------------|----------------------|------------------|
| API responses (JSON)       | ~2-10 KB     | ~50-100 MB/day      | ~500 MB-1 GB/day |
| Static files (index.html)  | ~135 KB      | ~135 MB/day (if every request loads it) | ~1.3 GB/day |
| TLS overhead               | ~5 KB/conn   | Negligible           | ~50 MB/day       |
| **Monthly total (10k/day)** |             | **~3-5 GB/month**    |                  |
| **Monthly total (100k/day)** |            | **~30-60 GB/month**  |                  |

**Verdict:** Even at 100k requests/day, you use ~1-2% of the 5 TB allowance. Network is not a constraint.

### Latency

Frankfurt DC provides <20ms latency to most of Western Europe, <50ms to Eastern Europe. For a negotiation simulator where users read and type, sub-100ms API response time is more than adequate.

---

## 5. Scaling Limits

### When this server becomes inadequate

| Metric                          | Comfortable | Warning zone    | Need to upgrade  |
|---------------------------------|------------|-----------------|------------------|
| Concurrent WebSocket connections | <200       | 200-500          | >500             |
| API requests/second             | <50         | 50-100           | >100 sustained   |
| Memory usage                    | <5 GB       | 5-7 GB           | >7 GB            |
| CPU utilization (5-min avg)     | <60%        | 60-80%           | >80% sustained   |
| Response time (p95)             | <200ms      | 200-500ms        | >500ms           |
| Active concurrent users         | <200        | 200-500          | >500             |

### Warning signs to monitor

1. **Response time creeping up** — p95 latency above 300ms means workers are saturated
2. **CPU sustained >80%** — Time to add workers or upgrade plan
3. **Memory >6 GB** — Likely a leak or too many workers; investigate before upgrading
4. **429 rate limit responses increasing** — Legitimate users hitting limits = need more capacity
5. **Health check failures** — Workers too busy to respond in 5s = critical

### Monitoring setup (minimal)

```bash
# Add to crontab — logs system stats every 5 minutes
*/5 * * * * echo "$(date -Iseconds) CPU:$(top -bn1 | grep 'Cpu(s)' | awk '{print $2}') MEM:$(free -m | awk '/Mem:/{printf "%.0f", $3/$2*100}')% DISK:$(df -h / | awk 'NR==2{print $5}')" >> /var/log/dealsim-metrics.log
```

For production, consider adding a lightweight monitoring agent (Netdata at ~50 MB RAM, or UpCloud's built-in server monitoring).

### Upgrade path

| Plan                    | vCPU | RAM  | Monthly | When to move            |
|------------------------|------|------|---------|-------------------------|
| Current (General 2/8)  | 2    | 8 GB | ~€26    | Now — up to ~200 users  |
| General 4/16           | 4    | 16 GB| ~€52    | >200 concurrent users   |
| General 8/32           | 8    | 32 GB| ~€104   | >500 concurrent users   |

UpCloud allows live resizing (CPU/RAM) without downtime on General Purpose plans.

---

## 6. Cost Optimization

### Current plan assessment

The UpCloud General Purpose 2 vCPU / 8 GB plan costs approximately **€26/month**. For the current DealSim workload (single-worker FastAPI app, nginx, certbot), this is appropriately sized. A smaller plan would work but leaves less room for spikes.

### Could you go smaller?

| Option                          | Specs         | Price      | Verdict                          |
|--------------------------------|---------------|------------|----------------------------------|
| UpCloud Developer 1/2           | 1 CPU, 2 GB   | ~€7/mo    | Too tight — OS + Docker + app barely fits |
| UpCloud Developer 2/4           | 2 CPU, 4 GB   | ~€14/mo   | Viable for early stage (<50 users), but thin margin for spikes |
| **UpCloud General 2/8 (current)** | 2 CPU, 8 GB | **~€26/mo** | **Good balance — room to grow to ~200 users** |

### Competitor comparison

| Provider          | Plan              | Specs         | Price     | Pros                             | Cons                        |
|-------------------|-------------------|---------------|-----------|----------------------------------|-----------------------------|
| **UpCloud**       | General 2/8       | 2 CPU, 8 GB   | ~€26/mo   | MaxIOPS storage, Frankfurt DC, live resize | Slightly pricier than Hetzner |
| **Hetzner**       | CX32              | 4 vCPU, 8 GB  | €7.59/mo  | Half the price, 4 cores          | Shared vCPU (noisy neighbor risk), 20 TB transfer, Falkenstein/Helsinki only for cheapest |
| **Hetzner**       | CPX21             | 3 vCPU, 4 GB  | €6.49/mo  | Even cheaper, AMD EPYC            | 4 GB RAM is tighter         |
| **DigitalOcean**  | Basic 2/4         | 2 vCPU, 4 GB  | $24/mo    | Good ecosystem, managed DB addons | Shared CPU, less storage    |
| **DigitalOcean**  | Basic 2/8         | 2 vCPU, 8 GB  | $48/mo    | Same specs, premium pricing       | Overpriced vs alternatives  |

**Honest recommendation:**

- **If cost is the primary concern:** Hetzner CX32 at €7.59/mo gives you 4 shared vCPU and 8 GB RAM — more than enough for DealSim. The shared CPU means occasional latency spikes under neighbor load, but for a negotiation simulator this is unlikely to matter. Hetzner's Frankfurt DC is available. This saves ~€220/year.

- **If reliability and performance predictability matter more:** Stay on UpCloud. Dedicated vCPUs, MaxIOPS NVMe, and live resize are worth the premium for a production SaaS tool.

### Monthly cost breakdown (UpCloud)

| Item                    | Cost        |
|------------------------|-------------|
| Server (General 2/8)   | ~€26/mo     |
| Automated backups (UpCloud) | ~€5/mo (20% of server cost) |
| Domain (dealsim.org)    | ~€1-2/mo amortized |
| SSL (Let's Encrypt)    | Free        |
| **Total**              | **~€32-33/mo** |

---

## 7. High Availability — Single Point of Failure Analysis

This is a **single-server deployment**. Every component is a single point of failure.

| Component     | Failure mode           | Impact              | Mitigation                           |
|--------------|------------------------|---------------------|--------------------------------------|
| Server hardware | Hardware failure     | Total outage         | UpCloud SLA + automated backups      |
| Docker engine | Daemon crash           | All containers stop  | `restart: unless-stopped` auto-recovers |
| DealSim container | App crash/OOM      | API unavailable     | Health check restarts container in ~40s |
| Nginx container | Config error/crash   | No external access   | Health check + restart policy        |
| Certbot       | Renewal failure        | SSL expires (90 days) | Monitor cert expiry; manual renewal fallback |
| Disk          | Full disk              | Everything breaks    | Monitor disk usage, auto-prune       |
| Network       | DC-level outage        | Total outage         | Rare at Frankfurt DC; DNS failover if critical |

### What happens when the server goes down?

1. **Users see:** Connection refused or timeout (immediately)
2. **Recovery time:**
   - Docker restart: ~30-60 seconds (automatic via restart policies)
   - Server reboot: ~2-5 minutes (UpCloud fast boot)
   - Full rebuild from backup: ~15-30 minutes
3. **Data loss risk:** Minimal — session data in Docker volumes survives container restarts. Server hardware failure could lose data since last backup.

### What this deployment does NOT have (and when to add it)

| Feature                | When to add                        | Cost impact         |
|-----------------------|------------------------------------|---------------------|
| Load balancer          | >500 users or SLA requirement     | +€10-20/mo          |
| Second server (redundancy) | Revenue justifies uptime SLA  | +€26/mo             |
| Managed database       | When app needs persistent SQL     | +€15-30/mo          |
| CDN (Cloudflare Free)  | Now — free, reduces origin load   | Free                |
| External uptime monitor | Now — Uptime Robot free tier     | Free                |

**Immediate free wins:**
1. **Cloudflare (free tier):** Put Cloudflare in front for DDoS protection, caching of static assets, and DNS-level failover. This is the single highest-value change at zero cost.
2. **Uptime Robot:** Free external monitoring with email/Telegram alerts when the site goes down.

---

## 8. Backup Strategy

### What needs backing up

| Data                    | Location (on server)           | Criticality | Frequency  |
|------------------------|--------------------------------|-------------|------------|
| App session data        | Docker volume `dealsim-data`   | Medium      | Daily      |
| Analytics data          | Docker volume `dealsim-analytics` | Medium   | Daily      |
| SSL certificates        | Docker volume `certbot-certs`  | Low (re-issuable) | Weekly |
| Nginx config            | `./nginx/` directory           | Low (in git) | Git is the backup |
| Docker compose + Dockerfile | Project root               | Low (in git) | Git is the backup |
| `.env` file             | Project root                   | High (secrets) | After any change |

### Backup plan

**Tier 1 — UpCloud automated server backups:**
- Enable UpCloud's backup service (~€5/mo)
- Daily snapshots, 7-day retention
- Full server image — fastest recovery path
- Restores entire server in minutes

**Tier 2 — Application-level backup script:**

```bash
#!/bin/bash
# /opt/dealsim/backup.sh — Run daily via cron
set -euo pipefail

BACKUP_DIR="/opt/dealsim/backups"
DATE=$(date +%Y-%m-%d)
RETAIN_DAYS=14

mkdir -p "$BACKUP_DIR"

# Dump Docker volumes to tarball
docker run --rm \
  -v dealsim-data:/data/dealsim-data:ro \
  -v dealsim-analytics:/data/dealsim-analytics:ro \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf "/backup/dealsim-$DATE.tar.gz" -C /data .

# Backup .env (contains secrets)
cp /opt/dealsim/.env "$BACKUP_DIR/env-$DATE.bak"

# Prune old backups
find "$BACKUP_DIR" -name "dealsim-*.tar.gz" -mtime +$RETAIN_DAYS -delete
find "$BACKUP_DIR" -name "env-*.bak" -mtime +$RETAIN_DAYS -delete

echo "Backup completed: dealsim-$DATE.tar.gz"
```

**Crontab entry:**
```
0 3 * * * /opt/dealsim/backup.sh >> /var/log/dealsim-backup.log 2>&1
```

**Tier 3 — Off-server backup (disaster recovery):**

For critical data, sync backups to a second location:

```bash
# Option A: UpCloud Object Storage (~€5/mo for 250 GB in Frankfurt)
# Option B: Hetzner Storage Box (BX11, 1 TB, €3.81/mo)
# Option C: rsync to a second cheap VPS

# Example with rsync to remote:
rsync -az --delete /opt/dealsim/backups/ backup-user@remote-host:/backups/dealsim/
```

### Recovery procedure

```bash
# 1. Restore from UpCloud snapshot (fastest — full server)
#    UpCloud Console → Server → Backups → Restore

# 2. Restore from application backup (if server is new/rebuilt)
docker volume create dealsim-data
docker volume create dealsim-analytics
docker run --rm \
  -v dealsim-data:/data/dealsim-data \
  -v dealsim-analytics:/data/dealsim-analytics \
  -v /opt/dealsim/backups:/backup:ro \
  alpine tar xzf /backup/dealsim-YYYY-MM-DD.tar.gz -C /data

# 3. Restore .env
cp /opt/dealsim/backups/env-YYYY-MM-DD.bak /opt/dealsim/.env

# 4. Bring up stack
cd /opt/dealsim
docker compose -f nginx/docker-compose.production.yml up -d
```

---

## Summary — Action Items

| Priority | Action                                              | Effort   |
|----------|-----------------------------------------------------|----------|
| 1        | Increase uvicorn workers from 1 to 2                | 1 minute |
| 2        | Add memory limits to docker-compose.production.yml  | 5 minutes |
| 3        | Enable UpCloud automated backups                    | 2 minutes (console) |
| 4        | Set up Uptime Robot free monitoring                 | 5 minutes |
| 5        | Put Cloudflare in front (free tier)                 | 15 minutes |
| 6        | Add backup script + cron job                        | 10 minutes |
| 7        | Add log rotation for nginx                          | 5 minutes |
| 8        | Set up disk/CPU monitoring alerts                   | 10 minutes |

**Bottom line:** The 2 CPU / 8 GB UpCloud server is well-sized for DealSim's current stage. You have ~6x headroom on memory and comfortable CPU margin. The main risks are not resource-related — they are single-point-of-failure and lack of external monitoring. The free Cloudflare + Uptime Robot combo addresses both at zero cost.
