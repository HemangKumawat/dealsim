# DealSim Production Deployment Guide

Target: UpCloud VPS (2 CPU, 8GB RAM, Ubuntu 24.04, IP 94.237.87.238)

## Architecture

```
Internet -> :80/:443 -> nginx (SSL termination, rate limiting)
                           |
                     [backend network]
                           |
                        dealsim :8000 (FastAPI)
```

Three containers:
- **nginx** - reverse proxy, SSL, security headers, rate limiting
- **dealsim** - FastAPI application (non-root, resource-capped at 1GB/1CPU)
- **certbot** - automatic Let's Encrypt certificate renewal every 12 hours

## Prerequisites

```bash
# On the UpCloud VPS
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and back in for group change
```

## Initial Setup

### 1. Clone and configure

```bash
ssh root@94.237.87.238
cd /opt
git clone <your-repo-url> dealsim
cd dealsim

# Create .env from example
cp .env.example .env
nano .env   # Set DEALSIM_ADMIN_KEY and DEALSIM_CORS_ORIGINS
```

### 2. Set your domain in nginx config

Replace every occurrence of `YOUR_DOMAIN` in `nginx/dealsim.conf`:

```bash
DOMAIN="dealsim.yourdomain.com"
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" nginx/dealsim.conf
```

### 3. Obtain initial SSL certificate

Before the HTTPS server block can work, you need a certificate. Run nginx in HTTP-only mode first:

```bash
# Temporarily comment out the entire HTTPS server block in nginx/dealsim.conf
# Then start nginx:
docker compose -f docker-compose.production.yml up -d nginx

# Request the certificate:
docker compose -f docker-compose.production.yml run --rm certbot \
  certbot certonly --webroot -w /var/www/certbot \
  --email you@example.com \
  --agree-tos --no-eff-email \
  -d $DOMAIN

# Uncomment the HTTPS server block, then restart everything:
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

### 4. Verify

```bash
# Check all containers are healthy
docker compose -f docker-compose.production.yml ps

# Test HTTP redirect
curl -I http://$DOMAIN

# Test HTTPS
curl -I https://$DOMAIN

# Test health endpoint
curl https://$DOMAIN/health
```

## Day-to-Day Operations

### View logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Single service
docker compose -f docker-compose.production.yml logs -f dealsim

# Nginx access logs (on disk)
docker exec dealsim-nginx cat /var/log/nginx/access.log | tail -50
```

### Redeploy after code changes

```bash
cd /opt/dealsim
git pull
docker compose -f docker-compose.production.yml build dealsim
docker compose -f docker-compose.production.yml up -d dealsim
```

### Force certificate renewal

```bash
docker compose -f docker-compose.production.yml run --rm certbot \
  certbot renew --force-renewal
docker compose -f docker-compose.production.yml exec nginx nginx -s reload
```

### Check resource usage

```bash
docker stats --no-stream
```

## Resource Budget (8GB total)

| Service  | RAM limit | CPU limit | Notes                   |
|----------|-----------|-----------|-------------------------|
| dealsim  | 1 GB      | 1.0 CPU   | FastAPI + uvicorn       |
| nginx    | 256 MB    | 0.5 CPU   | Alpine, low footprint   |
| certbot  | 128 MB    | 0.25 CPU  | Sleeps between renewals |
| OS + Docker | ~2 GB  | -         | Ubuntu 24.04 baseline   |
| **Headroom** | **~4.5 GB** | **0.25 CPU** | Room for monitoring, SSH, etc. |

## Security Notes

- Nginx drops connections to common scanner paths (`.env`, `.git`, `wp-admin`)
- Rate limiting: 10 req/s general, 5 req/s on `/api/` endpoints
- TLS 1.2+ only, strong cipher suite, HSTS enabled
- App runs as non-root `dealsim` user inside the container
- Backend network is `internal: true` -- dealsim container is not reachable from the internet directly
- `server_tokens off` hides nginx version

## Troubleshooting

**Container won't start (health check failing):**
```bash
docker compose -f docker-compose.production.yml logs dealsim
# Check if .env is present and correct
```

**502 Bad Gateway:**
```bash
# dealsim container is down or still starting
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml restart dealsim
```

**Certificate renewal failing:**
```bash
docker compose -f docker-compose.production.yml logs certbot
# Ensure port 80 is open and DNS points to 94.237.87.238
```

**Rate limited (429 errors):**
Adjust `rate` and `burst` values in `nginx/nginx.conf` and reload:
```bash
docker compose -f docker-compose.production.yml exec nginx nginx -s reload
```
