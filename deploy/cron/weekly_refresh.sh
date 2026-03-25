#!/usr/bin/env bash
# CartPath — Weekly Data Refresh
# ================================
# Run via cron: 0 3 * * 0 /path/to/weekly_refresh.sh
# Refreshes OSM data, FDOT speeds, classifications, and rebuilds the OSRM graph.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Use platform-appropriate log directory
if [[ "$OSTYPE" == "darwin"* ]]; then
    LOG_DIR="$HOME/Library/Logs/cartpath"
else
    LOG_DIR="/var/log/cartpath"
fi
LOG_FILE="$LOG_DIR/weekly_refresh_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== CartPath Weekly Data Refresh ==="

cd "$PROJECT_ROOT"

# Step 1: OSM extraction
log "Step 1/5: Extracting OSM data..."
python3 pipeline/osm_extract.py --verbose >> "$LOG_FILE" 2>&1

# Step 2: FDOT speed ingestion
log "Step 2/5: Ingesting FDOT speed data..."
python3 pipeline/fdot_speed_ingest.py --verbose >> "$LOG_FILE" 2>&1

# Step 3: Speed classification
log "Step 3/5: Classifying speeds..."
python3 pipeline/classify_speeds.py --verbose >> "$LOG_FILE" 2>&1

# Step 4: Surface classification
log "Step 4/5: Classifying surfaces..."
python3 pipeline/classify_surfaces.py --verbose >> "$LOG_FILE" 2>&1

# Step 5: Build OSRM graph
log "Step 5/5: Building OSRM graph..."
python3 pipeline/build_graph.py --verbose >> "$LOG_FILE" 2>&1

# Rebuild OSRM routing data
log "Rebuilding OSRM routing data..."
bash routing/scripts/build_osrm.sh >> "$LOG_FILE" 2>&1

# Restart OSRM container to load new data
log "Restarting OSRM..."
cd deploy && docker compose restart osrm >> "$LOG_FILE" 2>&1

log "=== Weekly refresh complete ==="
