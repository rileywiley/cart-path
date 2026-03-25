# CartPath — Self-Hosting on a Mac

Host CartPath on a spare Mac on your local network. Everything runs in Docker.

## Prerequisites

- A Mac (Intel or Apple Silicon) with **4 GB+ free RAM**
- macOS 13 (Ventura) or newer
- The Mac stays on and connected to your network

## 1. Install Docker Desktop

Download and install Docker Desktop for Mac:

```bash
# Option A: Download from https://www.docker.com/products/docker-desktop/

# Option B: Install via Homebrew
brew install --cask docker
```

Open Docker Desktop and let it finish starting up. Verify:

```bash
docker --version
docker compose version
```

## 2. Install Python and Dependencies

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3 and GDAL (needed for data pipeline)
brew install python@3.11 gdal

# Verify
python3 --version
```

## 3. Clone the Repo

```bash
cd ~
git clone https://github.com/rileywiley/cart-path.git
cd cart-path

# Install Python dependencies
pip3 install -r requirements.txt
```

## 4. Configure Environment

```bash
cp deploy/.env.example deploy/.env
```

Edit `deploy/.env` with your editor:

```bash
nano deploy/.env   # or: open -e deploy/.env
```

Set at minimum:

```env
MAPBOX_ACCESS_TOKEN=pk.your_mapbox_token_here
CARTPATH_JWT_SECRET=run-openssl-rand-hex-32-to-generate
```

Generate the JWT secret:

```bash
openssl rand -hex 32
```

Get a free Mapbox token at [mapbox.com](https://account.mapbox.com/access-tokens/).

## 5. Bootstrap the Data Pipeline

This downloads road data, classifies speeds/surfaces, and builds the routing graph. Takes **5-10 minutes** on first run:

```bash
make init
```

Verify the output:

```bash
ls -la pipeline/data/health.json          # Pipeline health
ls -la routing/data/cartpath_roads.osrm   # OSRM routing graph
```

## 6. Build and Start

```bash
make prod
```

This builds 4 Docker containers:
- **client** — builds the React app (runs once, then exits)
- **osrm** — routing engine
- **api** — FastAPI backend
- **nginx** — serves the web app + reverse proxy

Check status:

```bash
make status
```

Open in your browser: **http://localhost**

## 7. Access from Other Devices on Your Network

Find your Mac's local IP:

```bash
make lan-ip
# Example output: Your LAN IP: 192.168.1.42
```

On any device connected to the same Wi-Fi/network, open:

```
http://192.168.1.42
```

To make this easier, you can assign a static IP to the Mac:
1. System Settings → Network → Wi-Fi → Details → TCP/IP
2. Configure IPv4: Manually
3. Set IP address (e.g., `192.168.1.100`)
4. Save

## 8. Keep It Running

### Prevent Sleep

The Mac needs to stay awake to serve requests:

1. System Settings → Energy Saver (or Battery → Options)
2. Enable **"Prevent automatic sleeping when the display is off"**
3. Optionally: **"Wake for network access"**

Or from the terminal:

```bash
# Prevent sleep permanently (until you cancel with Ctrl+C)
caffeinate -s &
```

### Auto-Start on Boot

Create a launch agent so CartPath starts when the Mac boots:

```bash
mkdir -p ~/Library/LaunchAgents

cat > ~/Library/LaunchAgents/com.cartpath.server.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cartpath.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/docker</string>
        <string>compose</string>
        <string>-f</string>
        <string>deploy/docker-compose.yml</string>
        <string>up</string>
        <string>-d</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/cart-path</string>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/cartpath/startup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/cartpath/startup-error.log</string>
</dict>
</plist>
PLIST
```

**Important:** Replace `YOUR_USERNAME` with your Mac username (run `whoami` to check), then:

```bash
mkdir -p ~/Library/Logs/cartpath
launchctl load ~/Library/LaunchAgents/com.cartpath.server.plist
```

### Weekly Data Refresh

Set up a weekly refresh so road data stays current:

```bash
cat > ~/Library/LaunchAgents/com.cartpath.refresh.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cartpath.refresh</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>deploy/cron/weekly_refresh.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/cart-path</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/cartpath/refresh.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/cartpath/refresh-error.log</string>
</dict>
</plist>
PLIST
```

Replace `YOUR_USERNAME` and load:

```bash
launchctl load ~/Library/LaunchAgents/com.cartpath.refresh.plist
```

## 9. Optional: Access from Outside Your Network

### Option A: Cloudflare Tunnel (Recommended — Free, No Port Forwarding)

Cloudflare Tunnel gives you a public HTTPS URL without opening ports on your router:

```bash
brew install cloudflare/cloudflare/cloudflared

# Login to Cloudflare (you need a free account + a domain on Cloudflare DNS)
cloudflared tunnel login

# Create a tunnel
cloudflared tunnel create cartpath

# Route your domain to the tunnel
cloudflared tunnel route dns cartpath cartpath.yourdomain.com

# Run the tunnel (points your domain to localhost:80)
cloudflared tunnel --url http://localhost:80 run cartpath
```

To run the tunnel permanently, create a launchd plist similar to the ones above.

### Option B: Port Forwarding + Dynamic DNS

1. Forward ports **80** and **443** on your router to your Mac's IP
2. Set up a free dynamic DNS service (e.g., DuckDNS):
   ```bash
   # See https://www.duckdns.org/install.jsp for Mac instructions
   ```
3. Run certbot for SSL:
   ```bash
   brew install certbot
   sudo certbot certonly --webroot -w /tmp/certbot -d yourname.duckdns.org
   ```
4. Enable the HTTPS block in `deploy/nginx.conf` (see comments in that file)

## 10. Monitoring

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

Check refresh logs:

```bash
cat ~/Library/Logs/cartpath/refresh.log
```

## Troubleshooting

**Docker not starting?**
- Open Docker Desktop app and wait for it to initialize
- Check: `docker info` — should show "Server Version"

**OSRM container unhealthy?**
- Data pipeline may not have run: `make init`
- Check: `ls routing/data/cartpath_roads.osrm`

**Slow on Apple Silicon?**
- Make sure `platform: linux/amd64` is NOT in `docker-compose.yml`
- Docker Desktop uses native ARM containers which are much faster

**Can't access from other devices?**
- Check Mac's firewall: System Settings → Network → Firewall → allow incoming
- Verify IP: `make lan-ip`
- Make sure other device is on the same network

**Pipeline fails with GDAL error?**
- Install GDAL via Homebrew: `brew install gdal`
- Then: `pip3 install --prefer-binary geopandas fiona`

## Architecture

```
Your Mac (Docker Desktop)
├── nginx (:80)        → Serves React app + proxies API
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
| Mac (you already have it) | $0 |
| Electricity | ~$5-10/mo |
| Mapbox (free tier: 50K loads/mo) | $0 |
| Domain (optional) | $0-1/mo |
| Cloudflare Tunnel (optional) | $0 |
| **Total** | **$0-11/mo** |
