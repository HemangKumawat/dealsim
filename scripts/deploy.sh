#!/usr/bin/env bash
# =============================================================================
# scripts/deploy.sh — Rolling deploy for DealSim
#
# Pulls the latest code, rebuilds the app image, and restarts the app
# container with zero nginx downtime. Nginx continues serving existing
# requests while the new app container comes up and passes its health check.
#
# Also handles first-time SSL certificate issuance via certbot when no cert
# exists yet for the configured domain.
#
# Usage (run on the VPS as root or the deploy user):
#   cd /opt/dealsim && bash scripts/deploy.sh
#
# Requirements:
#   - docker compose v2 (docker compose, not docker-compose)
#   - .env file present at /opt/dealsim/.env with DEALSIM_DOMAIN and DEALSIM_EMAIL set
#   - git repo cloned at APP_DIR
#
# Exit codes:
#   0 — deploy succeeded, app is healthy
#   1 — deploy failed (image build, health check, or rollback failure)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_DIR="${APP_DIR:-/opt/dealsim}"
COMPOSE_FILE="${APP_DIR}/docker-compose.production.yml"
APP_SERVICE="app"
HEALTH_URL="http://localhost:8000/health"
# How long to wait for the new container to become healthy (seconds)
HEALTH_TIMEOUT=120
HEALTH_INTERVAL=3

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${GREEN}[deploy]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[deploy]${NC}  $*"; }
error()   { echo -e "${RED}[deploy]${NC}  $*" >&2; exit 1; }
step()    { echo -e "${CYAN}[deploy]${NC}  >>> $*"; }

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
step "Pre-flight checks"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
    error "Compose file not found: ${COMPOSE_FILE}"
fi

if [[ ! -f "${APP_DIR}/.env" ]]; then
    error ".env file missing at ${APP_DIR}/.env — copy .env.example and fill in values."
fi

if ! docker compose version &>/dev/null; then
    error "docker compose v2 not found. Install the Docker Compose plugin."
fi

info "Pre-flight OK"
info "App directory : ${APP_DIR}"
info "Compose file  : ${COMPOSE_FILE}"
echo ""

# ---------------------------------------------------------------------------
# Step 0b: Load domain from .env and substitute placeholders in nginx config
#
# nginx/sites-available/dealsim.conf ships with "dealsim.org" as the domain.
# If DEALSIM_DOMAIN is set in .env, replace it in the live config.
# The source file is never modified — we work on the checked-out copy.
# ---------------------------------------------------------------------------
step "Domain configuration"

# Load .env into shell
set -o allexport
# shellcheck disable=SC1090
source "${APP_DIR}/.env"
set +o allexport

DOMAIN="${DEALSIM_DOMAIN:-}"
EMAIL="${DEALSIM_EMAIL:-}"

if [[ -z "${DOMAIN}" ]]; then
    warn "DEALSIM_DOMAIN is not set in .env — nginx config will use 'dealsim.org' as server_name."
    warn "Set DEALSIM_DOMAIN=yourdomain.com in .env before the first deploy."
else
    NGINX_CONF="${APP_DIR}/nginx/sites-available/dealsim.conf"
    # Substitute domain only if still set to the placeholder default
    if grep -q "dealsim\.io" "${NGINX_CONF}"; then
        sed -i "s/dealsim\.io/${DOMAIN}/g" "${NGINX_CONF}"
        info "Substituted domain '${DOMAIN}' in ${NGINX_CONF}"
    else
        info "Domain already set to '${DOMAIN}' in nginx config"
    fi
fi
echo ""

# ---------------------------------------------------------------------------
# Step 1: Pull latest code
# ---------------------------------------------------------------------------
step "Pulling latest code"

cd "${APP_DIR}"

if [[ -d ".git" ]]; then
    BEFORE_SHA=$(git rev-parse --short HEAD)
    git fetch --quiet origin
    git pull --ff-only --quiet
    AFTER_SHA=$(git rev-parse --short HEAD)

    if [[ "${BEFORE_SHA}" == "${AFTER_SHA}" ]]; then
        warn "No new commits (still at ${AFTER_SHA}). Continuing to rebuild anyway."
    else
        info "Updated ${BEFORE_SHA} -> ${AFTER_SHA}"
        git log --oneline "${BEFORE_SHA}..${AFTER_SHA}"
    fi
else
    warn "Not a git repo — skipping git pull. Deploying from current files."
fi
echo ""

# ---------------------------------------------------------------------------
# Step 2: Build new image
# ---------------------------------------------------------------------------
step "Building application image"

docker compose -f "${COMPOSE_FILE}" build "${APP_SERVICE}"

info "Image built successfully"
echo ""

# ---------------------------------------------------------------------------
# Step 3: Run migrations (placeholder)
# DealSim currently uses flat JSONL files, so there are no schema migrations.
# If you add a database in the future, run migration commands here before
# restarting the app. Example:
#   docker compose -f "${COMPOSE_FILE}" run --rm "${APP_SERVICE}" python -m dealsim_mvp.migrate
# ---------------------------------------------------------------------------
step "Migrations"
info "No database migrations required (JSONL data store)"
echo ""

# ---------------------------------------------------------------------------
# Step 3b: First-time SSL certificate issuance
#
# If no certificate exists yet for the domain, bring nginx up on HTTP only
# (the HTTPS server block will fail to start if certs are missing, so we use
# a temporary HTTP-only config), issue the cert, then do a full stack bring-up.
#
# On subsequent deploys this block is skipped because the cert already exists.
# ---------------------------------------------------------------------------
step "SSL certificate check"

CERT_PATH="/etc/letsencrypt/live/${DOMAIN:-dealsim.org}/fullchain.pem"

if [[ -z "${DOMAIN}" ]]; then
    warn "DEALSIM_DOMAIN not set — skipping SSL issuance. Nginx will not start without a domain."
elif docker run --rm \
        -v "$(docker compose -f "${COMPOSE_FILE}" config --format json 2>/dev/null | python3 -c "import sys,json; vols=[v for k,v in json.load(sys.stdin).get('volumes',{}).items() if 'certbot' in k.lower()]; print('')" 2>/dev/null || echo 'certbot-conf'):/etc/letsencrypt:ro" \
        alpine sh -c "test -f ${CERT_PATH}" 2>/dev/null; then
    info "SSL certificate exists for ${DOMAIN} — skipping issuance"
else
    warn "No SSL certificate found for ${DOMAIN}. Attempting first-time issuance..."

    if [[ -z "${EMAIL}" ]]; then
        error "DEALSIM_EMAIL must be set in .env for Let's Encrypt certificate issuance."
    fi

    # Bring up nginx on HTTP only so certbot can complete the ACME challenge.
    # The HTTPS server block will fail without certs, so we use --no-deps and
    # rely on the nginx conf's /.well-known/acme-challenge/ pass-through.
    info "Starting nginx for ACME challenge (HTTP only)..."
    docker compose -f "${COMPOSE_FILE}" up -d --no-deps nginx 2>/dev/null || \
        warn "nginx may already be running — continuing to certbot"

    sleep 5   # give nginx a moment to bind port 80

    info "Running certbot for ${DOMAIN}..."
    docker compose -f "${COMPOSE_FILE}" run --rm certbot \
        certbot certonly \
            --webroot \
            --webroot-path /var/www/certbot \
            --email "${EMAIL}" \
            --agree-tos \
            --no-eff-email \
            --non-interactive \
            -d "${DOMAIN}" \
            -d "www.${DOMAIN}" 2>&1 || \
        error "certbot issuance failed. Check DNS for ${DOMAIN} and try again."

    info "SSL certificate issued successfully for ${DOMAIN}"
fi
echo ""

# ---------------------------------------------------------------------------
# Step 4: Rolling restart — nginx stays up throughout
#
# Strategy:
#   1. Start a new app container with the new image
#   2. Wait for it to pass the health check
#   3. Old container is replaced (Docker handles this via --no-deps)
#
# nginx depends_on app with condition: service_healthy, so it will not
# restart unless explicitly told to. We only reload nginx config at the end,
# which is near-instant and does not drop connections.
# ---------------------------------------------------------------------------
step "Rolling restart of app service"

# Bring up the new app container. Docker Compose replaces the old one.
# --no-deps ensures nginx and certbot are not restarted.
docker compose -f "${COMPOSE_FILE}" up -d --no-deps --build "${APP_SERVICE}"

info "New app container started. Waiting for health check..."

# Wait for the container to report healthy
ELAPSED=0
until docker inspect --format='{{.State.Health.Status}}' dealsim-app 2>/dev/null | grep -q "^healthy$"; do
    if (( ELAPSED >= HEALTH_TIMEOUT )); then
        warn "Health check timed out after ${HEALTH_TIMEOUT}s."
        warn "Container logs:"
        docker logs --tail 30 dealsim-app 2>&1 || true
        error "Deploy failed — new container did not become healthy."
    fi
    sleep "${HEALTH_INTERVAL}"
    ELAPSED=$(( ELAPSED + HEALTH_INTERVAL ))
    printf "  Waiting... %ds\r" "${ELAPSED}"
done

echo ""
info "App container is healthy (${ELAPSED}s)"
echo ""

# ---------------------------------------------------------------------------
# Step 5: Reload nginx config (picks up any config file changes)
# This is non-disruptive: nginx finishes in-flight requests before reloading.
# ---------------------------------------------------------------------------
step "Reloading nginx config"

if docker ps --filter "name=dealsim-nginx" --filter "status=running" -q | grep -q .; then
    docker exec dealsim-nginx nginx -t 2>&1 && \
        docker exec dealsim-nginx nginx -s reload
    info "Nginx config reloaded"
else
    warn "Nginx container not running — skipping nginx reload"
fi
echo ""

# ---------------------------------------------------------------------------
# Step 6: Health check verification
# ---------------------------------------------------------------------------
step "Verifying deployment"

# Try the internal health endpoint (works even without public DNS)
if docker exec dealsim-app \
    python -c "import urllib.request; r = urllib.request.urlopen('${HEALTH_URL}'); print(r.read().decode())" \
    2>/dev/null; then
    echo ""
    info "Internal health check PASSED"
else
    warn "Internal health check failed — checking container state:"
    docker compose -f "${COMPOSE_FILE}" ps
    docker logs --tail 20 dealsim-app 2>&1 || true
    error "Deploy completed but health check failed. Investigate before sending traffic."
fi

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "============================================================="
info "Deploy complete."
echo ""
docker compose -f "${COMPOSE_FILE}" ps
echo ""
echo "  App logs    : docker logs -f dealsim-app"
echo "  All services: docker compose -f ${COMPOSE_FILE} ps"
echo "  Rollback    : git revert HEAD && bash scripts/deploy.sh"
echo "============================================================="
