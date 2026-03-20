# Nginx + SSL Production Setup Guide

Server: UpCloud 2 CPU / 8GB RAM, Ubuntu 24.04, Frankfurt DC (94.237.87.238)

## Prerequisites

- Domain `dealsim.io` DNS A record pointing to `94.237.87.238`
- Docker and Docker Compose installed on the server
- Ports 80 and 443 open in UpCloud firewall

## Directory Structure on Server

```
/opt/dealsim/
  docker-compose.production.yml
  .env
  Dockerfile
  src/
  static/
  nginx/
    nginx.conf
    sites-available/
      dealsim.conf
```

## Step-by-Step Deployment

### 1. Clone and prepare

```bash
ssh root@94.237.87.238
mkdir -p /opt/dealsim
cd /opt/dealsim
# Copy or clone your project files here
```

### 2. DNS verification

Before requesting certificates, confirm DNS is resolving:

```bash
dig +short dealsim.io
# Should return: 94.237.87.238
```

### 3. Initial SSL certificate (first time only)

Certbot needs a running nginx to serve the ACME challenge, but nginx needs certs to start the HTTPS block. Break the cycle with a temporary HTTP-only config.

**Option A: Init script (recommended)**

Create `init-letsencrypt.sh` on the server:

```bash
#!/bin/bash
set -euo pipefail

DOMAIN="dealsim.io"
EMAIL="your-email@example.com"   # <-- change this
STAGING=0                         # Set to 1 for testing (avoids rate limits)

echo ">>> Starting temporary nginx for ACME challenge..."

# Start just nginx with a minimal HTTP config (no SSL block)
docker compose -f docker-compose.production.yml run --rm --entrypoint "" \
  -p 80:80 \
  -v $(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro \
  -v certbot-webroot:/var/www/certbot \
  nginx sh -c "
    echo 'server { listen 80; server_name $DOMAIN www.$DOMAIN; location /.well-known/acme-challenge/ { root /var/www/certbot; } location / { return 200 \"ok\"; } }' > /etc/nginx/conf.d/default.conf
    nginx -g 'daemon off;'
  " &

sleep 3

echo ">>> Requesting certificate..."

STAGING_ARG=""
if [ $STAGING -eq 1 ]; then
  STAGING_ARG="--staging"
fi

docker compose -f docker-compose.production.yml run --rm certbot \
  certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN" \
  -d "www.$DOMAIN" \
  $STAGING_ARG

echo ">>> Stopping temporary nginx..."
docker stop $(docker ps -q --filter ancestor=nginx:1.27-alpine) 2>/dev/null || true

echo ">>> Done. Now run: docker compose -f docker-compose.production.yml up -d"
```

```bash
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
```

**Option B: Manual certbot (standalone)**

If you prefer not to use the script:

```bash
# Stop anything on port 80
sudo systemctl stop nginx 2>/dev/null || true

# Run certbot standalone
docker run --rm -p 80:80 \
  -v certbot-certs:/etc/letsencrypt \
  -v certbot-webroot:/var/www/certbot \
  certbot/certbot certonly --standalone \
  --email your-email@example.com \
  --agree-tos --no-eff-email \
  -d dealsim.io -d www.dealsim.io
```

### 4. Generate DH parameters (optional but recommended)

```bash
openssl dhparam -out /opt/dealsim/nginx/dhparam.pem 2048
```

Then uncomment the `ssl_dhparam` line in `nginx/sites-available/dealsim.conf` and add a volume mount for it in `docker-compose.production.yml`:

```yaml
# Under nginx volumes:
- ./nginx/dhparam.pem:/etc/nginx/dhparam.pem:ro
```

### 5. Start the full stack

```bash
cd /opt/dealsim
docker compose -f docker-compose.production.yml up -d
```

### 6. Verify

```bash
# Check all containers are running
docker compose -f docker-compose.production.yml ps

# Test HTTP redirect
curl -I http://dealsim.io
# Should return 301 -> https://dealsim.io

# Test HTTPS
curl -I https://dealsim.io/health
# Should return 200

# Check SSL grade
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=dealsim.io
```

## SSL Certificate Renewal

The certbot container handles renewal automatically every 12 hours. After renewal, nginx must reload to pick up new certs.

### Automated reload via cron

On the **host** (not inside a container), add a cron job:

```bash
crontab -e
```

Add:

```
0 5 * * * cd /opt/dealsim && docker compose -f docker-compose.production.yml exec nginx nginx -s reload >> /var/log/dealsim-nginx-reload.log 2>&1
```

This reloads nginx daily at 5 AM. Certbot renews certs that are within 30 days of expiry, so the daily reload ensures new certs are picked up promptly.

### Manual renewal test

```bash
docker compose -f docker-compose.production.yml run --rm certbot certbot renew --dry-run
```

## Configuration Notes

### Rate Limits

| Zone         | Limit        | Burst | Applies to                              |
|--------------|-------------|-------|----------------------------------------|
| api_general  | 100 req/min | 20    | All routes (default)                    |
| api_auth     | 10 req/min  | 5     | `/api/auth*`, `/api/login*`, etc.      |

Clients exceeding limits receive HTTP 429 with a JSON body.

### Admin Panel Access

The `/admin/` path is IP-restricted. Edit `dealsim.conf` to add allowed IPs:

```nginx
location /admin/ {
    allow 94.237.87.238;
    allow 127.0.0.1;
    allow YOUR.HOME.IP.HERE;
    deny all;
    ...
}
```

After editing, reload nginx:

```bash
docker compose -f docker-compose.production.yml exec nginx nginx -s reload
```

### CORS Origins

Allowed origins are set via regex in `dealsim.conf`. To add a new origin (e.g., a staging frontend):

```nginx
if ($http_origin ~* "^https://(dealsim\.io|www\.dealsim\.io|staging\.dealsim\.io|localhost:3000)$") {
    set $cors_origin $http_origin;
}
```

### WebSocket

The `/ws/` path is pre-configured for WebSocket upgrade. The read/send timeouts are set to 24 hours to keep connections alive.

## Troubleshooting

### nginx won't start — "certificate not found"

You need to run the init script (step 3) before starting the full stack. The SSL server block references cert files that don't exist yet.

### 502 Bad Gateway

The FastAPI container isn't healthy yet. Check:

```bash
docker compose -f docker-compose.production.yml logs dealsim
docker compose -f docker-compose.production.yml exec dealsim python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
```

### Rate limit testing

```bash
# Fire 20 rapid requests to test rate limiting
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code}\n" https://dealsim.io/health
done
```

### Check nginx config syntax

```bash
docker compose -f docker-compose.production.yml exec nginx nginx -t
```

### View real-time logs

```bash
docker compose -f docker-compose.production.yml logs -f nginx
```

## Security Checklist

- [ ] DNS A record points to 94.237.87.238
- [ ] SSL certificate obtained via certbot
- [ ] UpCloud firewall allows only ports 22, 80, 443
- [ ] Admin IPs updated in dealsim.conf
- [ ] DH params generated and mounted
- [ ] `.env` file has production secrets (not committed to git)
- [ ] Cron job for daily nginx reload is active
- [ ] SSL Labs test shows A or A+ grade
- [ ] Rate limiting verified with burst test
- [ ] HSTS header present in responses
