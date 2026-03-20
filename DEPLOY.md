# DealSim Deployment Guide

Deploy DealSim to the cloud in under 5 minutes.

## Prerequisites

- Git repository with DealSim code pushed to GitHub
- Docker installed locally (for Option D or local testing)

---

## Option A: Render.com (Free, One-Click)

**Time: ~3 minutes**

1. Push code to GitHub:
   ```bash
   git init && git add -A && git commit -m "Initial commit"
   gh repo create dealsim --public --push
   ```

2. Go to https://dashboard.render.com/new/web-service

3. Connect your GitHub repo, select `dealsim`

4. Render auto-detects `render.yaml`. Click **Create Web Service**.

5. Wait for build (~2 min). Your app is live at `https://dealsim.onrender.com`

6. **Verify:**
   ```bash
   curl https://dealsim.onrender.com/health
   # Expected: {"status":"healthy","version":"0.1.0"}
   ```

7. Set your admin key in Render dashboard > Environment:
   - `DEALSIM_ADMIN_KEY` = your-secret-key

8. View analytics: `https://dealsim.onrender.com/admin/stats?key=your-secret-key`

**Note:** Free tier spins down after 15 min of inactivity. First request after spin-down takes ~30s.

---

## Option B: Fly.io (Free Tier, CLI Deploy)

**Time: ~4 minutes**

1. Install Fly CLI:
   ```bash
   # macOS/Linux
   curl -L https://fly.io/install.sh | sh
   # Windows
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. Sign up and authenticate:
   ```bash
   fly auth signup   # or: fly auth login
   ```

3. Launch the app:
   ```bash
   cd dealsim
   fly launch --copy-config --yes
   ```

4. Set secrets:
   ```bash
   fly secrets set DEALSIM_ADMIN_KEY=your-secret-key
   fly secrets set DEALSIM_CORS_ORIGINS=https://dealsim.fly.dev
   ```

5. Deploy:
   ```bash
   fly deploy
   ```

6. **Verify:**
   ```bash
   fly status
   curl https://dealsim.fly.dev/health
   # Expected: {"status":"healthy","version":"0.1.0"}
   ```

7. View logs:
   ```bash
   fly logs
   ```

**Note:** Free tier includes 3 shared-cpu-1x VMs with 256MB RAM. Auto-stop/start enabled to stay within limits.

---

## Option C: Railway (Free Tier)

**Time: ~3 minutes**

1. Go to https://railway.com/new

2. Click **Deploy from GitHub repo**, select your `dealsim` repo

3. Railway auto-detects `railway.json` and Dockerfile

4. Add environment variables in the Railway dashboard:
   - `DEALSIM_ADMIN_KEY` = your-secret-key
   - `DEALSIM_ENV` = production
   - `DEALSIM_CORS_ORIGINS` = https://your-app.up.railway.app

5. Railway assigns a public URL automatically. Click **Settings > Networking > Generate Domain**.

6. **Verify:**
   ```bash
   curl https://your-app.up.railway.app/health
   # Expected: {"status":"healthy","version":"0.1.0"}
   ```

**Note:** Free tier gives $5/month credit (~500 hours of a small container).

---

## Option D: VPS (Hetzner, ~$4/mo)

**Time: ~5 minutes**

1. Create a Hetzner Cloud account at https://hetzner.cloud

2. Create a CX22 server (2 vCPU, 4GB RAM, ~$4/mo):
   - Image: Ubuntu 24.04
   - Location: closest to your users
   - Add your SSH key

3. SSH in and install Docker:
   ```bash
   ssh root@YOUR_IP
   curl -fsSL https://get.docker.com | sh
   ```

4. Clone and deploy:
   ```bash
   git clone https://github.com/YOUR_USERNAME/dealsim.git
   cd dealsim
   cp .env.example .env
   # Edit .env: set DEALSIM_ADMIN_KEY and DEALSIM_CORS_ORIGINS
   nano .env
   docker compose up -d --build
   ```

5. **Verify:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status":"healthy","version":"0.1.0"}
   ```

6. (Optional) Add HTTPS with Caddy:
   ```bash
   apt install caddy
   cat > /etc/caddy/Caddyfile << 'EOF'
   dealsim.yourdomain.com {
       reverse_proxy localhost:8000
   }
   EOF
   systemctl restart caddy
   ```

---

## Local Testing

```bash
# With Docker
docker compose up --build
# Open http://localhost:8000

# Without Docker
pip install -e ".[dev]"
uvicorn dealsim_mvp.app:app --reload --port 8000
```

---

## Admin Dashboard

After deploying, view analytics at:
```
https://YOUR_DOMAIN/admin/stats?key=YOUR_ADMIN_KEY
```

Shows: total sessions, completion rate, average score, and recent feedback.

---

## Collecting Feedback

The feedback modal appears automatically after each scorecard. Data is stored in `/tmp/dealsim_data/feedback.json` (newline-delimited JSON). On platforms without persistent disk, feedback resets on redeploy. For persistence:

- **Render:** Add a Render Disk ($0.25/GB/mo) mounted at `/tmp/dealsim_data`
- **Fly.io:** Create a volume: `fly volumes create dealsim_data --size 1`
- **Railway:** Data persists within deploy lifecycle
- **VPS:** Docker volume persists automatically
