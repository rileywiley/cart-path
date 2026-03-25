#!/usr/bin/env bash
# CartPath — First-Deploy Bootstrap
# ====================================
# Runs the data pipeline and builds the OSRM graph.
# Must run BEFORE docker compose up on a fresh server.
#
# Usage:
#   bash deploy/init.sh           # Full bootstrap
#   bash deploy/init.sh --force   # Force re-run even if data exists

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/pipeline/data"
ROUTING_DATA="$PROJECT_ROOT/routing/data"
FORCE=false

if [[ "${1:-}" == "--force" ]]; then
    FORCE=true
fi

echo "=== CartPath First-Deploy Bootstrap ==="
echo "Project root: $PROJECT_ROOT"
echo ""

cd "$PROJECT_ROOT"

# Check if data already exists
if [[ -f "$DATA_DIR/health.json" && "$FORCE" != "true" ]]; then
    echo "Data already exists (pipeline/data/health.json found)."
    echo "Use --force to re-run the pipeline."
    echo ""

    # Still check if OSRM data exists
    if [[ ! -f "$ROUTING_DATA/cartpath_roads.osrm" ]]; then
        echo "OSRM graph not found — building..."
    else
        echo "OSRM graph exists. Nothing to do."
        exit 0
    fi
fi

# Check Python dependencies
echo "Checking Python dependencies..."
python3 -c "import requests, json" 2>/dev/null || {
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
}

# Create output directories
mkdir -p "$DATA_DIR" "$ROUTING_DATA"

# Step 1: OSM extraction (~2-5 minutes)
echo ""
echo "[1/6] Extracting OSM road data (this takes 2-5 minutes)..."
python3 pipeline/osm_extract.py --verbose

# Step 2: FDOT speed ingestion
echo ""
echo "[2/6] Ingesting FDOT speed limit data..."
python3 pipeline/fdot_speed_ingest.py --osm-graph "$DATA_DIR/osm_roads.geojson" --verbose

# Step 3: Speed classification
echo ""
echo "[3/6] Classifying road speeds..."
python3 pipeline/classify_speeds.py --verbose

# Step 4: Surface classification
echo ""
echo "[4/6] Classifying road surfaces..."
python3 pipeline/classify_surfaces.py --verbose

# Step 5: Build graph (generates OSM XML + coverage boundary + health.json)
echo ""
echo "[5/6] Building OSRM-ready graph..."
python3 pipeline/build_graph.py --verbose

# Step 6: Build OSRM routing data
echo ""
echo "[6/6] Building OSRM routing index..."
bash routing/scripts/build_osrm.sh

echo ""
echo "=== Bootstrap Complete ==="
echo "Data files: $DATA_DIR/"
echo "OSRM graph: $ROUTING_DATA/"
echo ""
echo "Next steps:"
echo "  1. cp deploy/.env.example deploy/.env"
echo "  2. Edit deploy/.env with your tokens"
echo "  3. docker compose -f deploy/docker-compose.yml up -d --build"
