#!/usr/bin/env bash
# =============================================================================
# DealSim Production Deployment Script
# Target: UpCloud VPS - Ubuntu 24.04 LTS, 2 CPU / 8GB RAM
# Usage:  scp deploy.sh root@94.237.87.238:~ && ssh root@94.237.87.238 'bash deploy.sh'
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit these before running
# ---------------------------------------------------------------------------
DOMAIN="${DEALSIM_DOMAIN:-dealsim.app}"
EMAIL="${DEALSIM_EMAIL:-admin@dealsim.app}"
GITHUB_REPO="${DEALSIM_REPO:-https://github.com/YOUR_USERNAME/dealsim.git}"
APP_DIR="/opt/dealsim"
BACKUP_DIR="/opt/backups/dealsim"
DOZZLE_PORT="9999"  # internal only, behind auth

# Generate a cryptographically secure admin key
ADMIN_KEY=$(openssl rand -hex 32)

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root."
fi

if [[ "$DOMAIN" == "dealsim.app" ]]; then
    warn "Using default domain 'dealsim.app'. Set DEALSIM_DOMAIN env var to override."
    warn "Make sure DNS A record points $DOMAIN -> $(curl -4s ifconfig.me || echo '94.237.87.238')"
    echo ""
    read -rp "Continue with domain '$DOMAIN'? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
fi

info "Starting DealSim deployment on $(hostname)"
info "Domain: $DOMAIN"
info "Server: $(nproc) CPUs, $(free -h | awk '/Mem:/{print $2}') RAM"

# =========================================================================
# PHASE 1: System Preparation
# =========================================================================
info "=== Phase 1: System Preparation ==="

# Update system packages
info "Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

# Install essential packages
info "Installing essential packages..."
apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    ufw \
    fail2ban \
    logrotate \
    unattended-upgrades \
    jq \
    git \
    htop

# =========================================================================
# PHASE 2: Docker Installation
# =========================================================================
info "=== Phase 2: Docker Installation ==="

if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    info "Docker $(docker --version) installed."
else
    info "Docker already installed: $(docker --version)"
fi

# Verify docker compose plugin
if ! docker compose version &>/dev/null; then
    error "Docker Compose plugin not found. Reinstall Docker."
fi
info "Docker Compose $(docker compose version --short) available."

# =========================================================================
# PHASE 3: Security Hardening
# =========================================================================
info "=== Phase 3: Security Hardening ==="

# --- UFW Firewall ---
info "Configuring UFW firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
info "UFW active. Allowed ports: 22, 80, 443."

# --- Fail2Ban ---
info "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << 'FAIL2BAN'
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
FAIL2BAN

systemctl enable fail2ban
systemctl restart fail2ban
info "Fail2ban configured: 3 SSH attempts, 24h ban."

# --- SSH Hardening ---
info "Hardening SSH configuration..."
SSHD_CONFIG="/etc/ssh/sshd_config"

# Backup original
cp "$SSHD_CONFIG" "${SSHD_CONFIG}.bak.$(date +%s)"

# Apply hardening — only if key auth is possible
if [[ -f /root/.ssh/authorized_keys ]] && [[ -s /root/.ssh/authorized_keys ]]; then
    # Disable password auth since keys exist
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "$SSHD_CONFIG"
    sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "$SSHD_CONFIG"
    sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' "$SSHD_CONFIG"
    info "Password authentication disabled (SSH keys detected)."
else
    warn "No SSH keys found in /root/.ssh/authorized_keys."
    warn "Password authentication left ENABLED. Add SSH keys and re-run hardening."
fi

# Common hardening regardless of key presence
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' "$SSHD_CONFIG"
sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/' "$SSHD_CONFIG"
sed -i 's/^#\?X11Forwarding.*/X11Forwarding no/' "$SSHD_CONFIG"

# Validate config before restarting
if sshd -t; then
    systemctl restart sshd
    info "SSH hardened and restarted."
else
    warn "SSH config validation failed. Restoring backup."
    cp "${SSHD_CONFIG}.bak."* "$SSHD_CONFIG" 2>/dev/null
    systemctl restart sshd
fi

# --- Auto security updates ---
info "Enabling automatic security updates..."
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'AUTOUPDATE'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
AUTOUPDATE

# =========================================================================
# PHASE 4: Application Setup
# =========================================================================
info "=== Phase 4: Application Setup ==="

# Clone or update the repo
if [[ -d "$APP_DIR/.git" ]]; then
    info "Updating existing repo..."
    cd "$APP_DIR"
    git pull --ff-only
else
    info "Cloning repository..."
    rm -rf "$APP_DIR"
    git clone "$GITHUB_REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

# Create production .env
info "Generating production .env..."
cat > "$APP_DIR/.env" << ENVFILE
# DealSim Production Configuration
# Generated: $(date -Iseconds)
DEALSIM_ENV=production
DEALSIM_HOST=0.0.0.0
DEALSIM_PORT=8000
DEALSIM_WORKERS=2
DEALSIM_CORS_ORIGINS=https://${DOMAIN}
DEALSIM_ADMIN_KEY=${ADMIN_KEY}
DEALSIM_MAX_SESSIONS=1000
DEALSIM_SESSION_TTL_HOURS=1
DEALSIM_DATA_DIR=/tmp/dealsim_data
ENVFILE

chmod 600 "$APP_DIR/.env"
info "Environment configured. Admin key saved."

# =========================================================================
# PHASE 5: Production Docker Compose
# =========================================================================
info "=== Phase 5: Docker Compose (Production) ==="

cat > "$APP_DIR/docker-compose.prod.yml" << 'COMPOSE'
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
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  dozzle:
    image: amir20/dozzle:latest
    container_name: dealsim-dozzle
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - DOZZLE_ADDR=:9999
      - DOZZLE_BASE=/logs
      - DOZZLE_USERNAME=admin
      - DOZZLE_PASSWORD=${DOZZLE_PASSWORD:?DOZZLE_PASSWORD must be set in .env}
    restart: unless-stopped
    networks:
      - dealsim-net
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: '0.25'
    logging:
      driver: json-file
      options:
        max-size: "5m"
        max-file: "2"

volumes:
  dealsim-data:
  dealsim-analytics:

networks:
  dealsim-net:
    driver: bridge
COMPOSE

# Add Dozzle password to .env
DOZZLE_PASS=$(openssl rand -hex 16)
echo "" >> "$APP_DIR/.env"
echo "# Dozzle log viewer" >> "$APP_DIR/.env"
echo "DOZZLE_PASSWORD=${DOZZLE_PASS}" >> "$APP_DIR/.env"

# =========================================================================
# PHASE 6: Nginx Configuration
# =========================================================================
info "=== Phase 6: Nginx Reverse Proxy ==="

mkdir -p "$APP_DIR/nginx/conf.d"

# Main nginx.conf
cat > "$APP_DIR/nginx/nginx.conf" << 'NGINXMAIN'
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

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 1m;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 4;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;
    limit_conn_zone $binary_remote_addr zone=addr:10m;

    # Include server blocks
    include /etc/nginx/conf.d/*.conf;
}
NGINXMAIN

# Server block — starts as HTTP-only, SSL added after certbot
cat > "$APP_DIR/nginx/conf.d/dealsim.conf" << NGINXSERVER
# Rate limit status codes
limit_req_status 429;
limit_conn_status 429;

# Upstream
upstream dealsim_backend {
    server dealsim:8000;
    keepalive 16;
}

# HTTP -> HTTPS redirect (active after SSL cert obtained)
server {
    listen 80;
    server_name ${DOMAIN};

    # Certbot challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect all other HTTP to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # SSL certificates (will exist after certbot runs)
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # SSL hardening
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # OCSP stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    # Health check endpoint (no rate limit, for UptimeRobot)
    location = /health {
        proxy_pass http://dealsim_backend;
        proxy_set_header Host \$host;
        access_log off;
    }

    # API endpoints with rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_conn addr 10;

        proxy_pass http://dealsim_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Admin endpoints — tighter rate limit
    location /admin/ {
        limit_req zone=api burst=5 nodelay;

        proxy_pass http://dealsim_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Dozzle log viewer (password protected via Dozzle itself)
    location /logs/ {
        limit_req zone=api burst=5 nodelay;

        proxy_pass http://dozzle:9999/logs/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files and general routes
    location / {
        limit_req zone=general burst=50 nodelay;

        proxy_pass http://dealsim_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Block common attack paths
    location ~ /\.(git|env|htaccess) {
        deny all;
        return 404;
    }
}
NGINXSERVER

# =========================================================================
# PHASE 7: SSL Certificate
# =========================================================================
info "=== Phase 7: SSL Certificate ==="

# Install certbot
apt-get install -y -qq certbot

# Create webroot directory
mkdir -p /var/www/certbot

# We need nginx running on port 80 for the ACME challenge, but the full
# SSL config won't work yet (no cert). Use a temporary HTTP-only config.
cat > "$APP_DIR/nginx/conf.d/dealsim-temp.conf" << TEMPNGINX
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'DealSim setup in progress...';
        add_header Content-Type text/plain;
    }
}
TEMPNGINX

# Temporarily replace the SSL config
mv "$APP_DIR/nginx/conf.d/dealsim.conf" "$APP_DIR/nginx/conf.d/dealsim.conf.ssl"
cd "$APP_DIR"

# Build the app and start nginx with temp config
info "Building DealSim Docker image..."
docker compose -f docker-compose.prod.yml build dealsim

info "Starting nginx for ACME challenge..."
docker compose -f docker-compose.prod.yml up -d nginx 2>/dev/null || true

# Give nginx a moment to start
sleep 3

# Obtain certificate
info "Requesting SSL certificate for ${DOMAIN}..."
if certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --force-renewal; then
    info "SSL certificate obtained."
else
    warn "SSL certificate request failed. Common causes:"
    warn "  - DNS A record for $DOMAIN does not point to this server"
    warn "  - Port 80 is not reachable from the internet"
    warn ""
    warn "Continuing with HTTP-only setup. Run this to retry later:"
    warn "  certbot certonly --webroot --webroot-path=/var/www/certbot -d $DOMAIN --email $EMAIL"
    warn ""
    # Keep the temp config so the app works on HTTP
    SKIP_SSL=true
fi

# Stop temp nginx
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

# Restore SSL config (or keep temp if SSL failed)
if [[ "${SKIP_SSL:-false}" != "true" ]]; then
    rm "$APP_DIR/nginx/conf.d/dealsim-temp.conf"
    mv "$APP_DIR/nginx/conf.d/dealsim.conf.ssl" "$APP_DIR/nginx/conf.d/dealsim.conf"
else
    # Modify temp config to proxy to the app
    cat > "$APP_DIR/nginx/conf.d/dealsim-temp.conf" << HTTPONLY
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location = /health {
        proxy_pass http://dealsim:8000;
        proxy_set_header Host \$host;
        access_log off;
    }

    location /logs/ {
        proxy_pass http://dozzle:9999/logs/;
        proxy_set_header Host \$host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass http://dealsim:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
HTTPONLY
    rm -f "$APP_DIR/nginx/conf.d/dealsim.conf.ssl"
fi

# Certbot auto-renewal cron
cat > /etc/cron.d/certbot-renew << 'CERTCRON'
# Renew Let's Encrypt certificates twice daily
0 3,15 * * * root certbot renew --quiet --deploy-hook "docker restart dealsim-nginx" >> /var/log/certbot-renew.log 2>&1
CERTCRON

# =========================================================================
# PHASE 8: Backup System
# =========================================================================
info "=== Phase 8: Backup System ==="

mkdir -p "$BACKUP_DIR"

cat > /opt/dealsim/backup.sh << 'BACKUPSCRIPT'
#!/usr/bin/env bash
# DealSim daily backup script
set -euo pipefail

BACKUP_DIR="/opt/backups/dealsim"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/dealsim_backup_${TIMESTAMP}.tar.gz"
RETENTION_DAYS=14

# Create backup of Docker volumes
echo "[$(date)] Starting DealSim backup..."

# Export volume data
docker run --rm \
    -v dealsim_dealsim-data:/data \
    -v dealsim_dealsim-analytics:/analytics \
    -v "${BACKUP_DIR}:/backup" \
    alpine:3.19 \
    tar czf "/backup/dealsim_backup_${TIMESTAMP}.tar.gz" /data /analytics

# Also backup .env and compose files
cp /opt/dealsim/.env "${BACKUP_DIR}/env_backup_${TIMESTAMP}"
cp /opt/dealsim/docker-compose.prod.yml "${BACKUP_DIR}/compose_backup_${TIMESTAMP}.yml"

# Prune old backups
find "$BACKUP_DIR" -name "dealsim_backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "env_backup_*" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "compose_backup_*" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup complete: $BACKUP_FILE"
echo "[$(date)] Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
BACKUPSCRIPT

chmod +x /opt/dealsim/backup.sh

# Daily backup cron at 2:30 AM
cat > /etc/cron.d/dealsim-backup << 'BACKUPCRON'
30 2 * * * root /opt/dealsim/backup.sh >> /var/log/dealsim-backup.log 2>&1
BACKUPCRON

info "Daily backup configured at 02:30. Retention: 14 days."

# =========================================================================
# PHASE 9: Launch
# =========================================================================
info "=== Phase 9: Launching DealSim ==="

cd "$APP_DIR"
docker compose -f docker-compose.prod.yml up -d --build

# Wait for health check
info "Waiting for application to become healthy..."
RETRIES=0
MAX_RETRIES=30
until docker inspect --format='{{.State.Health.Status}}' dealsim-app 2>/dev/null | grep -q healthy; do
    RETRIES=$((RETRIES + 1))
    if [[ $RETRIES -ge $MAX_RETRIES ]]; then
        warn "Health check timed out after ${MAX_RETRIES} attempts."
        warn "Check logs: docker logs dealsim-app"
        break
    fi
    sleep 2
done

# =========================================================================
# PHASE 10: Verification
# =========================================================================
info "=== Phase 10: Verification ==="

echo ""
echo "-------------------------------------------------------------"

# Container status
info "Container status:"
docker compose -f docker-compose.prod.yml ps
echo ""

# Health check
PROTO="https"
if [[ "${SKIP_SSL:-false}" == "true" ]]; then
    PROTO="http"
fi

info "Health check:"
if curl -sf "${PROTO}://${DOMAIN}/health" 2>/dev/null; then
    echo ""
    info "Health check PASSED."
elif curl -sf "http://localhost:8000/health" 2>/dev/null; then
    echo ""
    info "App is healthy on localhost (external access may need DNS)."
else
    echo ""
    warn "Health check failed. Checking container logs..."
    docker logs --tail 20 dealsim-app
fi
echo ""

# Recent logs
info "Recent app logs:"
docker logs --tail 10 dealsim-app 2>&1
echo ""

# Resource usage
info "Resource usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true
echo ""

# =========================================================================
# Summary
# =========================================================================
echo "============================================================="
echo ""
info "DealSim deployment complete."
echo ""
echo "  Application:    ${PROTO}://${DOMAIN}"
echo "  Health check:   ${PROTO}://${DOMAIN}/health"
echo "  Admin stats:    ${PROTO}://${DOMAIN}/admin/stats"
echo "  Log viewer:     ${PROTO}://${DOMAIN}/logs/"
echo ""
echo "  Credentials stored securely in /opt/dealsim/.env (chmod 600)"
echo "  To view:  cat /opt/dealsim/.env | grep -E 'ADMIN_KEY|DOZZLE'"
echo ""
echo "  UptimeRobot:    Monitor ${PROTO}://${DOMAIN}/health"
echo "                  Expected: {\"status\":\"healthy\"}"
echo "                  Keyword:  healthy"
echo ""
echo "  Backups:        /opt/backups/dealsim/ (daily at 02:30)"
echo "  Logs:           docker logs dealsim-app"
echo "  Restart:        cd /opt/dealsim && docker compose -f docker-compose.prod.yml restart"
echo "  Full redeploy:  cd /opt/dealsim && git pull && docker compose -f docker-compose.prod.yml up -d --build"
echo ""
echo "============================================================="
echo ""
warn "Admin key and Dozzle password are stored in /opt/dealsim/.env (chmod 600)"
echo ""
