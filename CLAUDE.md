# CartPath — Implementation Guide

## What is CartPath?

CartPath is a web-based navigation app for street-legal golf carts. It routes users only on roads with speed limits ≤35 MPH and prefers paved surfaces. The pilot region is a 30-mile radius around Baldwin Park, FL (center: 28.5641, -81.3089).

The full product requirements are in `docs/PRD.md`. Read it before starting any phase.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data pipeline | Python 3.10+, geopandas, shapely, requests, pandas, osmnx |
| Routing engine | OSRM with custom Lua profile |
| Backend API | FastAPI (Python) |
| Frontend | Vite + React SPA (PWA-enabled) |
| Map | Mapbox GL JS |
| Geocoding | Mapbox Geocoding API |
| Analytics | Plausible Cloud |
| Hosting | Single VPS (2-4 GB RAM, DigitalOcean or Hetzner) |
| Data storage | Local JSON/GeoJSON files, browser localStorage for user data |

## Project Structure

```
cartpath/
├── CLAUDE.md                  # This file
├── docs/
│   └── PRD.md                 # Full product requirements document
├── pipeline/                  # Phase 1: Data pipeline scripts
│   ├── osm_extract.py         # Overpass API extraction
│   ├── fdot_speed_ingest.py   # FDOT speed limit download + spatial join
│   ├── classify_speeds.py     # 4-tier speed classification
│   ├── classify_surfaces.py   # 3-tier surface classification
│   ├── build_graph.py         # Generate OSRM-ready graph
│   └── data/                  # Downloaded/processed data files
├── routing/                   # Phase 2: OSRM + API
│   ├── profiles/
│   │   └── cart.lua           # Custom OSRM Lua profile
│   ├── api/
│   │   ├── main.py            # FastAPI application
│   │   ├── routes.py          # /route endpoint
│   │   ├── geocode.py         # /geocode proxy endpoint
│   │   └── health.py          # /health endpoint
│   └── scripts/
│       └── build_osrm.sh      # Script to build OSRM graph from data
├── client/                    # Phase 3: React web app
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Map.jsx
│   │   │   ├── SearchBar.jsx
│   │   │   ├── RoutePanel.jsx
│   │   │   ├── FallbackBanner.jsx
│   │   │   ├── SavedRoutes.jsx
│   │   │   ├── Onboarding.jsx
│   │   │   └── ErrorStates.jsx
│   │   ├── hooks/
│   │   ├── utils/
│   │   │   ├── analytics.js
│   │   │   └── boundary.js    # Coverage polygon check
│   │   └── styles/
│   ├── public/
│   │   ├── manifest.json      # PWA manifest
│   │   └── sw.js              # Service worker
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── deploy/
    ├── docker-compose.yml
    ├── nginx.conf
    └── cron/
        └── weekly_refresh.sh  # Cron job for data pipeline
```

## Key Constants

```python
# Pilot region
CENTER_LAT = 28.5641
CENTER_LON = -81.3089
RADIUS_MILES = 30

# Routing
MAX_SPEED_MPH = 35           # Cart-legal speed threshold
DEFAULT_CART_SPEED_MPH = 23  # For ETA calculations
SERVICE_ROAD_SPEED_MPH = 10  # Routing penalty for service roads

# Data audit results (240,878 total segments)
# These are reference numbers — do not hardcode into app logic
```

## Implementation Phases

### Phase 1: Data Pipeline (2 weeks)

Build the offline data pipeline that produces an OSRM-ready road graph. Everything in this phase is Python scripts that run locally or via cron.

**Task 1.1 — OSM Extraction (`osm_extract.py`)**
- Query the Overpass API for all drivable roads within the 30-mile pilot radius
- Road types to include: primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, residential, unclassified, living_street, service
- Extract tags: highway, maxspeed, surface, service (subtype), name, lanes, oneway
- Output: GeoJSON file with all road segments and their tags
- Reference: PRD Section 6.1

**Task 1.2 — FDOT Speed Limit Ingestion (`fdot_speed_ingest.py`)**
- This is fully specced in PRD Section 6.4 with a requirements table. Follow it exactly.
- Download FDOT Maximum Speed Limit TDA from gis-fdot.opendata.arcgis.com
- Clip to pilot region, reproject to EPSG:4326
- Spatial join to OSM ways (15-meter buffer, sjoin_nearest)
- Conflict resolution: FDOT wins for primary/secondary, OSM wins for tertiary/residential
- Output: `osm_speed_enrichment.json` mapping OSM way IDs → speed limits + source
- CLI with flags: --center-lat, --center-lon, --radius-miles, --max-age, --osm-graph, --output, --verbose, --dry-run

**Task 1.3 — Speed Classification (`classify_speeds.py`)**
- Implement the 4-tier classification from PRD Section 6.2:
  - Tier 1: Explicit OSM maxspeed tags (6.4% of segments)
  - Tier 2: FDOT enrichment data (from Task 1.2)
  - Tier 3: osm-legal-default-speeds library inference
  - Tier 4: Flag remaining ~2.6% as "unknown" — exclude from default graph
- Output: each segment gets a `speed_limit`, `speed_source` (osm_tag|fdot|inferred|unknown), and `cart_legal` (true|false|unknown)

**Task 1.4 — Surface Classification (`classify_surfaces.py`)**
- Implement the 3-tier classification from PRD Section 6.2:
  - Tier 1: Explicit OSM surface tags (20.7% of segments)
  - Tier 2: Road-type heuristic — residential, tertiary, secondary, primary, service = "paved" by default in the pilot region
  - Tier 3: Mapillary dataset for remaining gaps (optional for v1 — heuristic covers ~98%)
- Output: each segment gets `surface_type` (paved|unpaved|unknown) and `surface_source` (osm_tag|heuristic|mapillary)

**Task 1.5 — Service Road Filtering**
- Apply the rules from PRD Section 6.3:
  - INCLUDE: service roads with no subtype, service=alley, service=parking
  - EXCLUDE: service=driveway, service=parking_aisle
  - All included service roads: cart_legal=true, surface=paved, routing_speed=10 MPH

**Task 1.6 — OSRM Graph Build (`build_graph.py`)**
- Generate an OSM PBF or XML file from the classified data
- Write the custom Lua profile (see Phase 2 Task 2.1 — do this first or in parallel)
- Build the OSRM graph with `osrm-extract`, `osrm-partition`, `osrm-customize`
- Generate a coverage boundary GeoJSON (convex hull of the cart-legal graph) for the client

**Task 1.7 — Pipeline Health Check**
- After each run, write `data/health.json` with: timestamp, segment counts by tier, FDOT match rate, surface classification counts
- Reference: PRD Section 6.8

**Validation for Phase 1:**
- [ ] Total segments extracted matches ~240K (±10%)
- [ ] Speed classification produces ~91% cart-legal, ~6% illegal, ~3% unknown
- [ ] Surface classification produces ~98% paved, ~2% unpaved/unknown
- [ ] OSRM graph builds successfully and fits in <2 GB RAM
- [ ] Coverage boundary GeoJSON is a valid polygon
- [ ] `fdot_speed_ingest.py --dry-run` completes without error

---

### Phase 2: Routing Engine (2-3 weeks)

Build the OSRM instance with custom profile and wrap it in a FastAPI service.

**Task 2.1 — Custom OSRM Lua Profile (`profiles/cart.lua`)**
The Lua profile controls how OSRM builds its routing graph. Key rules:
- Default graph: EXCLUDE all edges where speed_limit > 35 MPH
- Unpaved segments: apply a 0.5x speed penalty (makes OSRM prefer paved alternatives)
- Service roads: use 10 MPH speed factor (last-mile only, never through-routes)
- service=driveway, service=parking_aisle: exclude entirely
- All other cart-legal roads: 23 MPH travel speed for ETA
- Read the `cart_legal` and `surface_type` attributes from the enriched OSM data

**Task 2.2 — FastAPI Routing Service (`api/main.py`)**

Endpoints:

`POST /route`
- Input: `{ start: {lat, lon}, end: {lat, lon} }`
- First, query OSRM on the **filtered** (cart-legal) graph
- If no route found, re-query on the **full** graph (fallback mode)
- Response includes:
  - `route_geometry` (GeoJSON LineString)
  - `distance_miles`, `duration_minutes` (at 23 MPH)
  - `compliance`: "full" | "partial" | "fallback"
  - `warnings[]`: array of non-compliant segments with road name, speed limit, distance
  - `route_id`: unique ID for error reporting
  - `segments[]`: per-segment breakdown with distance, time, road name, speed, surface

`GET /geocode?q={query}`
- Proxy to Mapbox Geocoding API
- Bias results to the pilot region bounding box
- Return top 5 suggestions

`GET /health`
- Check OSRM is responding
- Check data freshness from `data/health.json`
- Return staleness warning if data is >10 days old

**Task 2.3 — Fallback Routing Logic**
- When the filtered graph returns no route, re-query OSRM on the full graph
- Compare the fallback route segments against the speed classification data
- Annotate each non-compliant segment: road name, speed limit, distance in miles
- The client will display these as the inline warning banner (see Phase 3)

**Validation for Phase 2:**
- [ ] OSRM responds to queries in <500ms for routes within the pilot area
- [ ] Cart-legal routes never include segments >35 MPH
- [ ] Fallback routes correctly identify and annotate non-compliant segments
- [ ] /geocode returns relevant Baldwin Park area results
- [ ] /health correctly reports data staleness

---

### Phase 3: Web Client (3-4 weeks)

Build the React PWA. Mobile-first, minimum viewport 375px. Primary users are older and non-technical — simplicity is the top priority.

**Task 3.1 — Onboarding Flow (`Onboarding.jsx`)**
Per PRD Section 5.7:
1. Splash screen: logo + "Safe routes for your golf cart" + "Get Started" button
2. Location permission: browser-native prompt with context text and "Not now" fallback
3. Legal disclaimer: one-time "I understand" button, persist in localStorage
4. Land on map centered on user location (or Baldwin Park center at 28.5641, -81.3089)

**Task 3.2 — Map Component (`Map.jsx`)**
- Mapbox GL JS as the map layer
- Speed limit color overlay: green (≤25 MPH), yellow (26-35 MPH), red/dashed (>35 MPH)
- Coverage boundary: subtle dashed line at the edge of the pilot region
- Route overlay: green for compliant, orange/red for flagged segments
- Unpaved segments: dashed line style
- Touch targets for all map controls: 56px minimum (zoom, locate)

**Task 3.3 — Search and Routing (`SearchBar.jsx`, `RoutePanel.jsx`)**
- Two-field input: start (defaults to "Current Location") and destination
- Address autocomplete via /geocode endpoint
- On submit: call /route, display results in RoutePanel
- Route summary: "~XX min · X.X mi · All roads ≤35 MPH" (or warning if fallback)
- Up to 3 route alternatives (P1 — can defer to v1.5 if needed)

**Task 3.4 — Fallback Warning Banner (`FallbackBanner.jsx`)**
Per PRD Section 5.1 and Open Question #5:
- Inline banner at top of route summary card
- Amber/warning color, persistent (does not auto-dismiss)
- Text: "⚠ This route includes [X] mi on roads above 35 MPH (max: [Y] MPH on [road name])."
- Expandable: tap to show each non-compliant segment with speed limit and distance
- Non-blocking: user can still follow the route

**Task 3.5 — Coverage Boundary Check (`utils/boundary.js`)**
Per PRD Section 5.5:
- Load the coverage boundary GeoJSON (generated in Phase 1)
- Check every destination against it BEFORE calling /route
- If outside: "This destination is outside CartPath's verified coverage area."
- Offer: (1) route to nearest boundary point, or (2) cancel

**Task 3.6 — Error States (`ErrorStates.jsx`)**
Per PRD Section 5.6:
- No route found: "We couldn't find any route between these locations."
- GPS unavailable: hide "Current Location", show search bar with note
- Permission denied: non-blocking banner with re-prompt link
- API down: "CartPath is temporarily unavailable." (after 2 retries, 3s timeout each)

**Task 3.7 — Saved Routes (`SavedRoutes.jsx`)**
- Save route with custom label → localStorage
- Home screen shows saved routes for one-tap re-routing
- Store last 10 destinations for quick access (P1)

**Task 3.8 — Report a Problem**
- "Report a problem" link on every route result screen
- Opens pre-filled mailto: link with route start/end coords, route ID, blank description field
- Email target: configurable (e.g., feedback@cartpath.app)

**Task 3.9 — Analytics Instrumentation (`utils/analytics.js`)**
Per PRD Analytics Event Taxonomy — instrument all 10 events:
- app_opened, route_requested, route_displayed, route_started, route_completed
- route_saved, destination_outside_area, error_reported, page_load_time, multi_stop_requested
- Each event: anonymous session ID (uuid in localStorage) + UTC timestamp
- Send to Plausible or custom endpoint

**Task 3.10 — PWA Setup**
- Web app manifest (`manifest.json`): name, icons, theme color, display: standalone
- Service worker: cache app shell for offline loading (NOT offline routing — that's v2)
- "Add to Home Screen" prompt on second visit

**Accessibility requirements (apply to ALL components):**
- Touch targets: ≥48px (map controls: 56px)
- Font sizes: body ≥16px, route info ≥18px, never <14px
- Color contrast: WCAG AA (4.5:1 normal, 3:1 large)
- Speed limit colors must have labels/patterns (not color-only)
- Semantic HTML, screen-reader-friendly route summaries

**Validation for Phase 3:**
- [ ] First-launch flow completes in <15 seconds to routable map
- [ ] Route search → display works on mobile (375px viewport)
- [ ] Fallback banner displays correctly with expandable detail
- [ ] Boundary check catches out-of-area destinations
- [ ] All 5 error states render correctly
- [ ] Saved routes persist across browser sessions
- [ ] Lighthouse score: Performance >80, Accessibility >90
- [ ] All 10 analytics events fire correctly

---

### Phase 4: Integration & QA (2 weeks)

- End-to-end testing: full flow from app open → search → route → follow → complete
- Drive-test 20+ real routes in the pilot area — verify speed limits and surface data
- Test fallback routing on destinations that require >35 MPH roads
- Test boundary handling with destinations outside the 30-mile radius
- Performance: route API response <500ms p95, page load <3s on 4G
- Test with 2+ users over age 60 (accessibility validation)
- Fix any data quality issues found during drive-testing
- Write `data/health.json` monitoring and staleness detection

---

### Phase 5: Pilot Launch (1 week)

- Deploy to production VPS (2-4 GB RAM)
- OSRM + FastAPI + Nginx reverse proxy
- Let's Encrypt SSL via Certbot
- Set up Plausible Cloud analytics
- Configure weekly cron job for data pipeline refresh
- Seed first 20-30 users from local community
- Monitor error_reported events daily for first 2 weeks

---

## Rules for Claude Code

1. **Python for backend, React for frontend.** Do not mix.
2. **All data pipeline scripts must be runnable standalone** via CLI with `--help`. No Jupyter notebooks.
3. **No commercial APIs for data.** OSM, FDOT, and Mapillary are all free. Only Mapbox is paid (free tier).
4. **Never route onto unverified roads silently.** If data confidence is low, warn the user.
5. **Mobile-first.** Every UI component must work at 375px width before you consider desktop.
6. **Accessibility is P0.** 48px touch targets, 16px min font, WCAG AA contrast. Not optional.
7. **The 35 MPH threshold is the single most important number in the app.** Double-check any logic that touches speed classification.
8. **Service roads get a 10 MPH routing penalty.** They are connectors, not through-routes.
9. **Exclude service=driveway and service=parking_aisle** from the routing graph entirely.
10. **When in doubt, read `docs/PRD.md`.** It has the answer.
