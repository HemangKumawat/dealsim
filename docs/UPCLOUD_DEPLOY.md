# DealSim UpCloud VPS Deployment Guide

**Server:** UpCloud 2 CPU / 8GB RAM, Ubuntu 24.04 LTS, Frankfurt (de-fra1)
**IP:** 94.237.87.238

---

## Resource Feasibility

The 2 CPU / 8GB RAM server is well-suited for this deployment:

| Service         | Memory  | CPU     | Notes                           |
|-----------------|---------|---------|--------------------------------|
| DealSim (FastAPI) | ~200MB  | 0.5 CPU | Python + uvicorn, 2 workers    |
| Nginx           | ~30MB   | minimal | Reverse proxy + TLS termination |
| Dozzle          | ~50MB   | minimal | Log viewer                      |
| Docker overhead | ~150MB  | minimal | Engine + networking              |
| OS + fail2ban   | ~400MB  | minimal | Ubuntu 24.04 baseline           |
| **Total**       | **~830MB** | **~1 CPU** |                             |

That leaves ~7GB free RAM and a full spare CPU. You could run ~10x the current load before hitting limits. The bottleneck will be Python's GIL and single-threaded request handling, not system resources. For this app, the server is overkill in the best way.

**Scaling limits:** With 2 uvicorn workers, expect ~200-500 concurrent users comfortably. Beyond that, increase `DEALSIM_WORKERS` to 4 (still fits) or add a second app container.

---

## Prerequisites

1. **DNS**: Create an A record pointing your domain to `94.237.87.238`
2. **SSH key**: Uploaded to UpCloud during server creation
3. **Code**: DealSim repo pushed to GitHub (or available as a tarball)

---

## Option 1: Automated Deployment (Recommended)

Upload and run the all-in-one script:

```bash
# From your local machine
scp deploy.sh root@94.237.87.238:~

# Set your domain and email, then run
ssh root@94.237.87.238
export DEALSIM_DOMAIN="dealsim.app"
export DEALSIM_EMAIL="you@example.com"
export DEALSIM_REPO="https://github.com/YOUR_USER/dealsim.git"
bash deploy.sh
```

The script handles everything: Docker, firewall, SSL, nginx, backups, monitoring. Save the admin key it prints at the end.

---

## Option 2: Manual Step-by-Step

### Step 1: Connect and Update

```bash
ssh root@94.237.87.238

# Update system
apt update && apt upgrade -y

# Install essentials
apt install -y \
    curl git ufw fail2ban jq htop \
    unattended-upgrades apt-transport-https \
    ca-certificates gnupg lsb-release
```

### Step 2: Install Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker
docker --version
docker compose version
```

### Step 3: Firewall (UFW)

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

### Step 4: Fail2Ban

```bash
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5
backend  = systemd

[sshd]
enabled  = true
port     = ssh
filter   = sshd
maxretry = 3
bantime  = 86400
EOF

systemctl enable fail2ban && systemctl restart fail2ban
```

### Step 5: SSH Hardening

Only do this if you have SSH keys configured:

```bash
# Verify you have keys first
cat /root/.ssh/authorized_keys

# Then harden
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config
sshd -t && systemctl restart sshd
```

### Step 6: Clone and Configure

```bash
git clone https://github.com/YOUR_USER/dealsim.git /opt/dealsim
cd /opt/dealsim

# Generate admin key
ADMIN_KEY=$(openssl rand -hex 32)
echo "Your admin key: $ADMIN_KEY"

# Create .env
cat > .env << EOF
DEALSIM_ENV=production
DEALSIM_HOST=0.0.0.0
DEALSIM_PORT=8000
DEALSIM_WORKERS=2
DEALSIM_CORS_ORIGINS=https://dealsim.app
DEALSIM_ADMIN_KEY=${ADMIN_KEY}
DEALSIM_MAX_SESSIONS=1000
DEALSIM_SESSION_TTL_HOURS=1
DEALSIM_DATA_DIR=/tmp/dealsim_data
DOZZLE_PASSWORD=$(openssl rand -hex 16)
EOF

chmod 600 .env
```

### Step 7: Nginx Configuration

```bash
mkdir -p /opt/dealsim/nginx/conf.d
```

Create `/opt/dealsim/nginx/nginx.conf`:

```bash
cat > /opt/dealsim/nginx/nginx.conf << 'EOF'
user nginx;
worker_processes auto;
pid /var/run/nginx.pid;
error_log /var/log/nginx/error.log warn;

events {
    worker_connections 1024;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent"';
    access_log /var/log/nginx/access.log main;

    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout 65;
    client_max_body_size 1m;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 4;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;
    limit_conn_zone $binary_remote_addr zone=addr:10m;

    include /etc/nginx/conf.d/*.conf;
}
EOF
```

Create the server block at `/opt/dealsim/nginx/conf.d/dealsim.conf`:

```bash
cat > /opt/dealsim/nginx/conf.d/dealsim.conf << 'EOF'
limit_req_status 429;
limit_conn_status 429;

upstream dealsim_backend {
    server dealsim:8000;
    keepalive 16;
}

server {
    listen 80;
    server_name dealsim.app;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name dealsim.app;

    ssl_certificate     /etc/letsencrypt/live/dealsim.app/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dealsim.app/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location = /health {
        proxy_pass http://dealsim_backend;
        proxy_set_header Host $host;
        access_log off;
    }

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_conn addr 10;
        proxy_pass http://dealsim_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location /admin/ {
        limit_req zone=api burst=5 nodelay;
        proxy_pass http://dealsim_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /logs/ {
        limit_req zone=api burst=5 nodelay;
        proxy_pass http://dozzle:9999/logs/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        limit_req zone=general burst=50 nodelay;
        proxy_pass http://dealsim_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location ~ /\.(git|env|htaccess) {
        deny all;
        return 404;
    }
}
EOF
```

Replace `dealsim.app` with your actual domain in the commands above.

### Step 8: SSL Certificate

```bash
apt install -y certbot
mkdir -p /var/www/certbot

# Get cert (nginx must be reachable on port 80 first — use standalone)
certbot certonly --standalone -d dealsim.app --email you@example.com --agree-tos --non-interactive

# Auto-renewal cron
cat > /etc/cron.d/certbot-renew << 'EOF'
0 3,15 * * * root certbot renew --quiet --deploy-hook "docker restart dealsim-nginx" >> /var/log/certbot-renew.log 2>&1
EOF
```

### Step 9: Production Docker Compose

Create `/opt/dealsim/docker-compose.prod.yml`:

```bash
cat > /opt/dealsim/docker-compose.prod.yml << 'EOF'
services:
  dealsim:
    build: .
    container_name: dealsim-app
    env_file:
      - .env
    environment:
      - DEALSIM_ENV=production
      - DEALSIM_DATA_DIR=/tmp/dealsim_data
    volumes:
      - dealsim-data:/tmp/dealsim_data
      - dealsim-analytics:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    networks:
      - dealsim-net
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  nginx:
    image: nginx:1.27-alpine
    container_name: dealsim-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - /var/www/certbot:/var/www/certbot:ro
    depends_on:
      dealsim:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - dealsim-net
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: '0.25'

  dozzle:
    image: amir20/dozzle:latest
    container_name: dealsim-dozzle
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - DOZZLE_ADDR=:9999
      - DOZZLE_BASE=/logs
      - DOZZLE_USERNAME=admin
      - DOZZLE_PASSWORD=${DOZZLE_PASSWORD:-changeme}
    restart: unless-stopped
    networks:
      - dealsim-net
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: '0.25'

volumes:
  dealsim-data:
  dealsim-analytics:

networks:
  dealsim-net:
    driver: bridge
EOF
```

### Step 10: Backup Script

```bash
mkdir -p /opt/backups/dealsim

cat > /opt/dealsim/backup.sh << 'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="/opt/backups/dealsim"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

docker run --rm \
    -v dealsim_dealsim-data:/data \
    -v dealsim_dealsim-analytics:/analytics \
    -v "${BACKUP_DIR}:/backup" \
    alpine:3.19 \
    tar czf "/backup/dealsim_backup_${TIMESTAMP}.tar.gz" /data /analytics

cp /opt/dealsim/.env "${BACKUP_DIR}/env_backup_${TIMESTAMP}"

find "$BACKUP_DIR" -name "dealsim_backup_*.tar.gz" -mtime +14 -delete
find "$BACKUP_DIR" -name "env_backup_*" -mtime +14 -delete

echo "[$(date)] Backup done: dealsim_backup_${TIMESTAMP}.tar.gz"
SCRIPT

chmod +x /opt/dealsim/backup.sh

cat > /etc/cron.d/dealsim-backup << 'EOF'
30 2 * * * root /opt/dealsim/backup.sh >> /var/log/dealsim-backup.log 2>&1
EOF
```

### Step 11: Launch

```bash
cd /opt/dealsim
docker compose -f docker-compose.prod.yml up -d --build
```

### Step 12: Verify

```bash
# Container status
docker compose -f docker-compose.prod.yml ps

# Health check
curl -s https://dealsim.app/health | jq .

# Admin stats
curl -s "https://dealsim.app/admin/stats?key=YOUR_ADMIN_KEY" | jq .

# Resource usage
docker stats --no-stream

# Logs
docker logs --tail 20 dealsim-app
```

---

## UptimeRobot Setup

1. Go to https://uptimerobot.com and create a free account
2. Add a new monitor:
   - **Type:** HTTP(s)
   - **URL:** `https://dealsim.app/health`
   - **Interval:** 5 minutes
   - **Keyword:** `healthy` (select "keyword exists")
3. The `/health` endpoint is excluded from rate limiting in the nginx config

---

## Operational Commands

```bash
# View logs (real-time)
docker logs -f dealsim-app

# Restart app only
docker restart dealsim-app

# Full restart (all services)
cd /opt/dealsim && docker compose -f docker-compose.prod.yml restart

# Update and redeploy
cd /opt/dealsim && git pull && docker compose -f docker-compose.prod.yml up -d --build

# Stop everything
cd /opt/dealsim && docker compose -f docker-compose.prod.yml down

# Manual backup
/opt/dealsim/backup.sh

# Restore from backup
docker run --rm \
    -v dealsim_dealsim-data:/data \
    -v dealsim_dealsim-analytics:/analytics \
    -v /opt/backups/dealsim:/backup \
    alpine:3.19 \
    tar xzf /backup/dealsim_backup_YYYYMMDD_HHMMSS.tar.gz -C /

# Check fail2ban status
fail2ban-client status sshd

# Check firewall
ufw status verbose

# Renew SSL manually
certbot renew --force-renewal --deploy-hook "docker restart dealsim-nginx"

# View Dozzle log dashboard
# Open https://dealsim.app/logs/ in browser
# Login with credentials from /opt/dealsim/.env
```

---

## Troubleshooting

**App not starting:**
```bash
docker logs dealsim-app
docker inspect dealsim-app | jq '.[0].State'
```

**502 Bad Gateway:**
```bash
# Check if app container is healthy
docker inspect --format='{{.State.Health.Status}}' dealsim-app
# Check nginx can reach the app
docker exec dealsim-nginx wget -qO- http://dealsim:8000/health
```

**SSL certificate issues:**
```bash
certbot certificates
# Re-obtain if needed
certbot certonly --webroot --webroot-path=/var/www/certbot -d dealsim.app
docker restart dealsim-nginx
```

**High memory usage:**
```bash
docker stats --no-stream
# Reduce workers if needed
# Edit /opt/dealsim/.env: DEALSIM_WORKERS=1
docker restart dealsim-app
```

**Locked out of SSH:**
Use UpCloud console access to fix `/etc/ssh/sshd_config` if password auth was disabled without keys.

---

## Security Checklist

- [x] UFW firewall: only 22, 80, 443 open
- [x] Fail2ban: 3 SSH attempts, 24h ban
- [x] SSH: key-only auth, root login restricted
- [x] HTTPS: TLS 1.2+, HSTS, security headers
- [x] Rate limiting: 10r/s API, 30r/s general
- [x] Docker: non-root user in container, resource limits
- [x] .env: chmod 600, not in git
- [x] Sensitive paths (.git, .env) blocked in nginx
- [x] Automatic security updates enabled
- [x] Log rotation configured
- [x] Daily backups with 14-day retention
