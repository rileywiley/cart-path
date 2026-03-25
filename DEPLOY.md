# CartPath — Deployment Guide

Deploy CartPath on a single VPS with Docker.

## Prerequisites

- A **domain name** (e.g., `cartpath.app`) — you'll need DNS access
- A **VPS** with 2-4 GB RAM, 2 vCPUs, 50 GB SSD
- A **Mapbox access token** — free at [mapbox.com](https://account.mapbox.com/access-tokens/)

## 1. Provision a VPS

**DigitalOcean** (recommended for simplicity):
1. Create a Droplet: Ubuntu 24.04, $12/mo (2 GB RAM / 1 vCPU) or $24/mo (4 GB / 2 vCPU)
2. Add your SSH key during creation
3. Note the droplet's IP address

**Hetzner** (better value):
1. Create a Cloud Server: Ubuntu 24.04, CX22 (~€4/mo for 2 vCPU / 4 GB RAM)
2. Add your SSH key
3. Note the server's IP address

## 2. DNS Setup

Add an **A record** pointing your domain to the VPS IP:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_SERVER_IP | 300 |
| A | www | YOUR_SERVER_IP | 300 |

Wait for DNS to propagate (5-30 minutes). Verify with:
```bash
dig +short yourdomain.com
```

## 3. Server Setup

SSH into your server and install Docker:

```bash
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Python 3 + pip (for data pipeline)
apt update && apt install -y python3-pip python3-venv git

# Clone the repo
git clone https://github.com/rileywiley/cart-path.git
cd cart-path

# Install Python dependencies
pip install -r requirements.txt
```

## 4. Configure Environment

```bash
cp deploy/.env.example deploy/.env
nano deploy/.env
```

Fill in at minimum:
- `MAPBOX_ACCESS_TOKEN` — your Mapbox token
- `CARTPATH_JWT_SECRET` — generate with `openssl rand -hex 32`
- `CARTPATH_ENV=production`
- `CARTPATH_CORS_ORIGINS=https://yourdomain.com`

Optional but recommended:
- `VITE_PLAUSIBLE_DOMAIN=yourdomain.com` (if using Plausible analytics)
- SMTP settings (for email verification)

## 5. Bootstrap Data

Run the data pipeline to generate road data and the OSRM routing graph. This takes **5-10 minutes** on first run (the Overpass API is the bottleneck):

```bash
make init
```

This runs `deploy/init.sh` which:
1. Extracts ~240K road segments from OpenStreetMap
2. Downloads FDOT speed limit data
3. Classifies roads by speed and surface
4. Builds the OSRM routing graph
5. Generates the coverage boundary

Verify the output:
```bash
ls -la pipeline/data/health.json     # Should exist
ls -la routing/data/cartpath_roads.osrm  # Should exist
```

## 6. Build and Start

```bash
make prod
```

This builds all Docker images (API, client, OSRM) and starts them. The client build takes ~1-2 minutes on first run.

Verify everything is running:
```bash
make status
# Should show: osrm (healthy), api (running), nginx (running)

curl http://localhost/api/health
# Should return {"status": "ok", ...}
```

Your app is now running on **http://YOUR_SERVER_IP**.

## 7. SSL Setup (HTTPS)

SSL is required for the PWA and browser geolocation to work properly.

```bash
# Install certbot
apt install -y certbot

# Create webroot directory (used by nginx for ACME challenges)
mkdir -p /var/www/certbot

# Get your certificate (replace with your domain)
certbot certonly --webroot -w /var/www/certbot -d yourdomain.com -d www.yourdomain.com
```

After certbot succeeds, edit `deploy/nginx.conf`:

1. **Uncomment** the entire HTTPS server block at the bottom
2. **Replace** `cartpath.app` with your domain (3 places: `server_name`, `ssl_certificate`, `ssl_certificate_key`)
3. **Add** this line inside the HTTP server block (after `listen 80;`):
   ```
   return 301 https://$host$request_uri;
   ```
4. Restart nginx:
   ```bash
   make restart
   ```

Set up **auto-renewal**:
```bash
crontab -e
# Add this line:
0 0 1 * * certbot renew --quiet && docker compose -f /root/cart-path/deploy/docker-compose.yml restart nginx
```

## 8. Weekly Data Refresh

Set up a cron job to refresh road data weekly:

```bash
crontab -e
# Add this line (runs every Sunday at 3 AM):
0 3 * * 0 cd /root/cart-path && bash deploy/cron/weekly_refresh.sh
```

This re-downloads OSM data, re-classifies roads, rebuilds the OSRM graph, and restarts the routing engine.

## 9. Monitoring

**Check service health:**
```bash
make status
make logs          # Follow all logs
docker logs cartpath-api -f --tail 100   # API logs only
```

**Check data freshness:**
```bash
curl -s http://localhost/api/health | python3 -m json.tool
```

If `data_freshness` is `stale`, the weekly cron job may have failed. Check logs:
```bash
ls /var/log/cartpath/
cat /var/log/cartpath/weekly_refresh_$(date +%Y%m%d).log
```

**Restart a single service:**
```bash
docker compose -f deploy/docker-compose.yml restart api    # Just the API
docker compose -f deploy/docker-compose.yml restart osrm   # Just OSRM
docker compose -f deploy/docker-compose.yml restart nginx   # Just nginx
```

**Full restart:**
```bash
make restart
```

**Rebuild everything from scratch:**
```bash
make down
make init --force
make prod
```

## Architecture Overview

```
Internet → Nginx (:80/:443)
              ├── /          → Static React SPA (built by Dockerfile.client)
              ├── /api/*     → FastAPI (:8000) → OSRM (:5000)
              └── /data/*    → FastAPI (serves coverage boundary, health.json)

Data:  pipeline/data/ (classified roads, health.json, SQLite DB)
       routing/data/  (OSRM graph files)
```

## Cost Summary

| Component | Cost |
|-----------|------|
| VPS (2-4 GB) | $12-24/mo |
| Domain | ~$1/mo |
| Mapbox (free tier: 50K loads/mo) | $0 |
| SSL (Let's Encrypt) | $0 |
| Data sources (OSM, FDOT) | $0 |
| Plausible analytics (optional) | $0-9/mo |
| **Total** | **$13-34/mo** |
