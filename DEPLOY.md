# CartPath — Deploy to Oracle Cloud (Free Tier)

Host CartPath for **$0/mo** on Oracle Cloud's Always Free ARM instance.

**What you get for free (forever):**
- 4 ARM CPUs (Ampere A1)
- 24 GB RAM
- 200 GB storage
- 10 TB/mo outbound data

This is massive overkill for CartPath (OSRM needs ~1-2 GB). It will run great.

## Prerequisites

- A **domain name** (e.g., from Namecheap, ~$10/year)
- A **Mapbox access token** — free at [mapbox.com](https://account.mapbox.com/access-tokens/)
- A credit/debit card for Oracle sign-up (you won't be charged)

## 1. Create an Oracle Cloud Account

1. Go to [cloud.oracle.com/free](https://www.oracle.com/cloud/free/)
2. Click **"Start for free"**
3. Fill in your details and add a payment method (required for verification, **never charged** on free tier)
4. Choose your **Home Region** — pick the one closest to Baldwin Park, FL:
   - **US East (Ashburn)** — best option
   - US Southeast (Vinhedo) if Ashburn is unavailable
5. Wait for account activation (usually 5-15 minutes)

> **Tip:** If sign-up is rejected (Oracle sometimes does this), try a different browser, clear cookies, or use a different payment method. This is a known issue.

## 2. Create an ARM Instance

1. Log into the Oracle Cloud Console
2. Click **"Create a VM instance"** (or go to Compute → Instances → Create Instance)
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `cartpath` |
| **Image** | **Ubuntu 24.04** (click "Change image" → Ubuntu → 24.04) |
| **Shape** | Click "Change shape" → **Ampere** → **VM.Standard.A1.Flex** |
| **OCPUs** | 4 (max free) |
| **Memory** | 24 GB (max free) |
| **Boot volume** | 100 GB (default, can go up to 200 GB free) |
| **SSH key** | Upload your public key or generate one |

4. Under **Networking**, use the default VCN or create one
5. Click **"Create"**
6. Wait for the instance to show **RUNNING** (1-2 minutes)
7. Copy the **Public IP address**

### Generate an SSH Key (if you don't have one)

```bash
ssh-keygen -t ed25519 -C "cartpath"
cat ~/.ssh/id_ed25519.pub
# Copy this output and paste it into the Oracle instance creation form
```

## 3. Open Firewall Ports

Oracle has **two firewalls** — you must open ports in both.

### A. Security List (Oracle Console)

1. Go to **Networking → Virtual Cloud Networks** → click your VCN
2. Click **Security Lists** → **Default Security List**
3. Click **"Add Ingress Rules"** and add:

| Source CIDR | Protocol | Dest Port | Description |
|-------------|----------|-----------|-------------|
| `0.0.0.0/0` | TCP | 80 | HTTP |
| `0.0.0.0/0` | TCP | 443 | HTTPS |

(Port 22/SSH is already open by default)

### B. Instance Firewall (iptables)

SSH into the instance and open the ports in the OS firewall:

```bash
ssh ubuntu@YOUR_PUBLIC_IP

# Open HTTP and HTTPS
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT

# Save so rules persist across reboots
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```

> **This is the #1 gotcha on Oracle Cloud.** The security list alone is not enough — you must also open ports in iptables.

## 4. Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Add your user to the docker group (no sudo needed for docker commands)
sudo usermod -aG docker ubuntu
newgrp docker

# Verify
docker --version
docker compose version
```

## 5. Install Python and Clone the Repo

```bash
# Install Python deps for data pipeline
sudo apt install -y python3-pip python3-venv gdal-bin libgdal-dev

# Clone
cd ~
git clone https://github.com/rileywiley/cart-path.git
cd cart-path

# Install Python dependencies
pip3 install --break-system-packages -r requirements.txt
```

> **Note:** `--break-system-packages` is needed on Ubuntu 24.04 which enforces PEP 668. Alternatively, use a venv: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

## 6. Configure Environment

```bash
cp deploy/.env.example deploy/.env
nano deploy/.env
```

Set these values:

```env
MAPBOX_ACCESS_TOKEN=pk.your_token_here
CARTPATH_JWT_SECRET=paste_output_of_openssl_rand_hex_32
CARTPATH_ENV=production
CARTPATH_CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

Generate the JWT secret:

```bash
openssl rand -hex 32
```

## 7. Bootstrap the Data Pipeline

This downloads road data, classifies speeds/surfaces, and builds the routing graph. Takes **5-10 minutes**:

```bash
make init
```

Verify:

```bash
ls -la pipeline/data/health.json          # Should exist
ls -la routing/data/cartpath_roads.osrm   # Should exist
```

## 8. Build and Start

```bash
make prod
```

This builds and starts 4 Docker containers:
- **client** — builds the React app (runs once, exits)
- **osrm** — OSRM routing engine
- **api** — FastAPI backend
- **nginx** — serves the app + reverse proxy

Verify:

```bash
make status
curl http://localhost/api/health
```

Your app is now running at **http://YOUR_PUBLIC_IP**.

## 9. DNS Setup

Point your domain to the Oracle instance's public IP:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_PUBLIC_IP | 300 |
| A | www | YOUR_PUBLIC_IP | 300 |

Verify DNS propagation (takes 5-30 minutes):

```bash
dig +short yourdomain.com
```

## 10. SSL Setup (HTTPS)

Once DNS is pointing to your server:

```bash
# Install certbot
sudo apt install -y certbot

# Create webroot for ACME challenges
sudo mkdir -p /var/www/certbot

# Get your certificate
sudo certbot certonly --webroot -w /var/www/certbot \
  -d yourdomain.com -d www.yourdomain.com
```

After certbot succeeds, edit `deploy/nginx.conf`:

1. **Uncomment** the HTTPS server block at the bottom of the file
2. **Replace** `cartpath.app` with your domain (3 places: `server_name`, `ssl_certificate`, `ssl_certificate_key`)
3. **Add** this line inside the HTTP server block (right after `listen 80;`):
   ```
   return 301 https://$host$request_uri;
   ```
4. Restart:
   ```bash
   make restart
   ```

Set up **auto-renewal**:

```bash
sudo crontab -e
# Add this line:
0 0 1 * * certbot renew --quiet && cd /home/ubuntu/cart-path && docker compose -f deploy/docker-compose.yml restart nginx
```

## 11. Weekly Data Refresh

Set up a cron job to keep road data current:

```bash
crontab -e
# Add this line (runs every Sunday at 3 AM):
0 3 * * 0 cd /home/ubuntu/cart-path && bash deploy/cron/weekly_refresh.sh
```

## 12. Monitoring

```bash
# Service status
make status

# Follow logs
make logs

# Just API logs
docker logs cartpath-api -f --tail 50

# Check data freshness
curl -s http://localhost/api/health | python3 -m json.tool

# Restart everything
make restart

# Rebuild from scratch
make down
make init --force
make prod
```

Check weekly refresh logs:

```bash
cat /var/log/cartpath/weekly_refresh_*.log
```

## Troubleshooting

**Can't connect from browser?**
- Check **both** firewalls: Oracle Security List AND iptables (see Step 3)
- Verify: `sudo iptables -L INPUT -n | grep 80`
- Test locally: `curl http://localhost` (if this works, it's a firewall issue)

**OSRM container unhealthy?**
- Data pipeline may not have run: `make init`
- Check: `ls routing/data/cartpath_roads.osrm`
- View OSRM logs: `docker logs cartpath-osrm`

**Out of memory?**
- Unlikely with 24 GB, but check: `free -h`
- OSRM uses ~1-2 GB for the pilot region graph

**Docker images slow to pull?**
- First pull downloads ARM64 images — may take a few minutes
- Subsequent pulls are cached

**Certbot fails?**
- Make sure DNS is pointing to this server: `dig +short yourdomain.com`
- Make sure port 80 is open: `curl -I http://yourdomain.com`
- Check nginx is running: `docker logs cartpath-nginx`

**Instance stopped/disappeared?**
- Oracle may reclaim idle free-tier instances. Check the instance status in the console.
- Keep the instance active by ensuring CartPath receives traffic or set up a simple health check cron.

## Architecture

```
Oracle Cloud ARM Instance (4 OCPU, 24 GB RAM)
├── nginx (:80/:443)   → Serves React app + proxies API + SSL
├── api (:8000)        → FastAPI backend
├── osrm (:5000)       → OSRM routing engine
└── client (build)     → Builds React app (runs once)

Storage:
├── pipeline/data/     → Road classifications, health.json, SQLite DB
└── routing/data/      → OSRM graph files
```

## Cost

| Component | Cost |
|-----------|------|
| Oracle Cloud (Always Free Tier) | **$0/mo** |
| Mapbox (free tier: 50K loads/mo) | $0 |
| Domain | ~$10/year |
| SSL (Let's Encrypt) | $0 |
| Data sources (OSM, FDOT) | $0 |
| **Total** | **~$1/mo** (just the domain) |
