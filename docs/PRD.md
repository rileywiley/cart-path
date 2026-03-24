**PRODUCT REQUIREMENTS DOCUMENT**

**CartPath**

AI-Powered Navigation for Street-Legal Golf Carts

| **Version** | 1.1 — Post-Audit Update |
| --- | --- |
| **Date** | March 24, 2026 |
| **Author** | Product Team |
| **Status** | Final — Ready for Build |
| **Pilot Region** | 30-mile radius around Baldwin Park, FL |

**CONFIDENTIAL**

# Table of Contents

# Executive Summary

CartPath is a web-based navigation application purpose-built for drivers of street-legal golf carts. The app uses AI-assisted routing to calculate optimal routes that comply with golf cart road-use laws, specifically restricting navigation to roads with speed limits of 35 MPH or less and preferring paved surfaces.

Street-legal golf carts are a rapidly growing mode of personal transportation in retirement communities, beach towns, college campuses, and mixed-use neighborhoods. Despite this growth, no major navigation platform offers routing tailored to the unique constraints of golf cart travel. Drivers today must manually verify speed limits and road surfaces, creating a frustrating and sometimes unsafe experience.

A data audit of the pilot region (30-mile radius around Baldwin Park, FL) confirmed 240,878 drivable road segments in OpenStreetMap. While only 6.4% have explicit speed limit tags, road-type inference combined with FDOT open data covers an estimated 91.2% of segments for cart-legality classification. Surface tag coverage is 20.7% explicit, but a “paved unless proven otherwise” heuristic is validated by the data: of tagged roads, only 2.5% are unpaved. This eliminates the need for a custom AI vision pipeline, enabling a fully open-data-driven approach at zero API cost.

# Problem Statement

Golf cart drivers face three core problems when navigating beyond their immediate neighborhood:

- **No purpose-built navigation: **Existing apps (Google Maps, Apple Maps, Waze) route for cars, often directing users onto highways, high-speed roads, or multi-lane thoroughfares that are illegal or dangerous for golf carts.

- **Speed limit uncertainty: **Drivers must manually research or memorize which roads fall at or below the 35 MPH legal threshold. Road signage is inconsistent, and speed limits can change block-to-block.

- **Road surface unknowns: **Golf carts perform poorly on unpaved surfaces (gravel, dirt, sand). Drivers have no way to know the road condition in advance, especially on unfamiliar routes.

The result is that many golf cart owners significantly limit their travel range, using their carts only within a few familiar blocks rather than taking advantage of the full network of cart-legal roads available to them.

# Target Users

## Primary Personas

- **Neighborhood Cruisers: **Residents of golf-cart-friendly neighborhoods and planned communities (e.g., Baldwin Park, FL) who use carts for errands, dining, and socializing within a 5–15 mile radius.

- **Beach Town Riders: **Residents and vacationers in coastal towns where golf carts are a primary local transport mode (e.g., 30A, FL; Bald Head Island, NC; Peachtree City, GA).

- **Campus Commuters: **Students and staff on large university campuses or college towns where golf carts are permitted on low-speed roads surrounding the campus.

## Who This Is NOT For

- Commercial golf cart fleets or rental operations (v2+ consideration)

- Off-road or trail-riding golf carts

- Standard automobile drivers

# Product Vision and Design Principles

## Vision Statement

*"**Make every golf cart ride as confident as a car ride.**"*

CartPath should feel as natural and trustworthy as using Google Maps in a car. The driver should never have to think about whether a road is legal, safe, or suitable for their cart.

## Design Principles

- **Simplicity first: **The primary interaction is entering a destination and tapping “Go.” Everything else is optional. Our target users skew older and non-technical; the UI must be effortless.

- **Safety as a default: **The app should always default to the safest route. Riskier options (unpaved roads, roads approaching the 35 MPH limit) require an explicit user choice.

- **Honest when uncertain: **If our data confidence on a road segment is low, we flag it rather than guess. “This road may be unpaved” is better than silently routing through gravel.

- **Local-first: **Start small, get it right. A perfect experience within 30 miles of Baldwin Park is worth more than a mediocre one across all of Florida.

## Competitive Defensibility

A national platform (Google Maps, Waze) could theoretically add a golf cart mode. CartPath’s long-term defensibility rests on three advantages that are structurally difficult for large platforms to replicate:

- **Community data network effect: **Waze-style community road reports (v1.5) create a self-reinforcing data loop: more users generate more reports, which improve routing accuracy, which attract more users. This local data layer is specific to golf cart use and has no value to Google’s broader user base, making it an unlikely investment for them.

- **Local regulatory curation: **County and municipal golf cart ordinances are fragmented, non-standardized, and change frequently. CartPath’s hand-curated ordinance data and community-validated restrictions represent accumulated local knowledge that national platforms have no mechanism to collect.

- **Community brand trust: **If CartPath becomes “the golf cart app” within a tight geographic community, word-of-mouth distribution and identity-based loyalty create switching costs. Golf cart communities are social networks with high in-group trust; a recommendation from a neighbor carries more weight than a feature announcement from Google.

# Feature Requirements

## v1 — Pilot Launch

### 5.1 Core Routing Engine

The routing engine is the heart of CartPath. It must produce routes that satisfy the golf cart constraint: all road segments on the route must have a posted speed limit of 35 MPH or less.

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Speed limit filtering | Exclude all road segments with speed limits above 35 MPH from the default routing graph. Use a tiered approach: (1) OSM maxspeed tags, (2) FDOT open GIS data for state/classified roads, (3) road-type inference via osm-legal-default-speeds library, (4) manual review for remaining unknowns. | P0 |
| Paved road preference | Default routes should prefer paved roads. If an unpaved segment is necessary, present it as a clearly labeled alternative: “This route includes 0.3 mi of unpaved road.” | P0 |
| Fallback routing | When no fully compliant route exists between A and B, show the best available route with an inline warning banner (persistent, expandable, non-blocking) at the top of the route summary. Display the max speed and distance of each non-compliant segment. Highlight non-compliant segments in red/orange on the map. | P0 |
| Default cart speed | Use a fixed 23 MPH for all ETA calculations. Display estimated trip time prominently on the route summary. | P0 |
| Route alternatives | Offer up to 3 route options: (1) Fastest compliant route, (2) Shortest-distance compliant route, (3) Scenic/residential-only route if available. | P1 |

### 5.2 Map Interface and UX

The map experience should feel familiar to anyone who has used Google Maps or Apple Maps, but with golf-cart-specific information layered on top.

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Map base layer | Use Mapbox GL JS or Leaflet with OpenStreetMap tiles. Roads within the pilot region should be color-coded by speed limit (green = ≤25, yellow = 26–35, red/dashed = >35). | P0 |
| Start/end input | Simple two-field input with address autocomplete (geocoding via Mapbox or Nominatim). Support “Current Location” as a starting point via browser geolocation. | P0 |
| Route overlay | Display the route on the map with clear color-coding: green for fully compliant segments, orange/warning for any flagged segments. | P0 |
| Road surface indicators | Show small icons or dashed-line styling for road segments classified as unpaved. | P1 |
| Responsive design | Must work well on mobile browsers (primary use case). Desktop is secondary. Target minimum viewport of 375px wide. | P0 |

### 5.3 ETA and Trip Estimates

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Trip time | Calculate ETA using 23 MPH fixed speed. Display as “~XX min” on route summary. | P0 |
| Trip distance | Display total distance in miles. | P0 |
| Segment breakdown | On route detail view, show distance and estimated time per major road segment. | P1 |

### 5.4 Saved Routes / Favorites

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Save a route | Allow users to save a route with a custom label (e.g., “Home to Publix”). Persist in browser local storage for v1; migrate to backend when user accounts are added. | P0 |
| Quick-launch | Saved routes appear on the home screen for one-tap re-routing. | P0 |
| Recent destinations | Store and display last 10 destinations for quick access. | P1 |

### 5.5 Coverage Boundary Handling

The pilot region is a 30-mile radius around Baldwin Park, FL. Road data outside this boundary has not been audited or enriched. The app must handle out-of-area destinations gracefully.

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Boundary detection | Pre-compute a coverage polygon (convex hull of the routing graph) and check every destination against it before sending to OSRM. This is a lightweight client-side check using a GeoJSON polygon. | P0 |
| Soft boundary with partial route | If the destination is outside the coverage zone, show a clear message: “This destination is outside CartPath’s verified coverage area.” Offer two options: (1) show the route to the nearest point on the coverage boundary, or (2) cancel. Never silently route onto unverified roads. | P0 |
| Boundary visualization | On the map, show a subtle dashed line or shaded overlay at the edge of the coverage area so users understand the boundary before they search. | P1 |

### 5.6 Error States and Feedback

The app must handle failure modes gracefully, especially for a non-technical audience. Additionally, v1 must include a lightweight feedback mechanism to capture data quality issues before community reports launch in v1.5.

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| No route found | When OSRM returns no route even on the full unfiltered graph, display: “We couldn’t find any route between these locations.” Suggest checking the addresses. | P0 |
| GPS unavailable | If geolocation fails or is denied, hide the “Current Location” button and show the search bar prominently with a note: “Enter your starting address to get a route.” Do not block the app. | P0 |
| Location permission denied | Show a non-blocking banner: “Allow location access for one-tap routing, or enter your starting address manually.” Include a link to re-prompt permissions. | P0 |
| API / service down | If the routing API is unreachable after 2 retries (3s timeout each), display: “CartPath is temporarily unavailable. Please try again in a few minutes.” | P0 |
| Report a problem (v1) | Add a “Report a problem” link on every route result screen. Opens a pre-filled mailto: link with the route start/end coordinates, route ID, and a blank field for description. Zero backend cost; captures data for manual review. | P0 |

### 5.7 Onboarding / First-Launch Experience

The first-launch sequence must be simple and fast for a non-technical audience. Goal: user sees a routable map within 15 seconds of opening the app.

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Splash screen | Single screen: CartPath logo, one-line tagline (“Safe routes for your golf cart”), and a “Get Started” button. No carousel, no multi-step tutorial. | P0 |
| Location permission prompt | Browser-native location prompt with context text above it: “CartPath needs your location to find routes near you.” Include a visible “Not now” option that drops the user to manual address entry. | P0 |
| Legal disclaimer | Shown once on first use: “CartPath suggests routes based on available data. Routes are not guaranteed to be legal or safe for all vehicles. Always obey posted signs and local regulations.” Single “I understand” button. Persist acceptance in local storage. | P0 |
| Default map state | After onboarding, land on the map centered on the user’s location (or Baldwin Park center if location denied). Show the speed-limit color overlay immediately so the user sees value before searching. | P0 |

### 5.8 Accessibility Requirements

CartPath’s primary user base skews older. Accessibility is not optional — it is a core UX requirement for this audience.

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Touch targets | All interactive elements (buttons, links, map controls) must be at least 48×48px. Map zoom and locate buttons should be 56px. | P0 |
| Font sizes | Minimum body text: 16px. Route information (ETA, distance, road names): 18px+. Never use text smaller than 14px anywhere in the UI. | P0 |
| Color contrast | All text must meet WCAG AA contrast ratio (4.5:1 for normal text, 3:1 for large text). Test against both light and dark backgrounds on the map. | P0 |
| Color independence | No critical information conveyed by color alone. The speed-limit color coding on the map (green/yellow/red) must be accompanied by labels, patterns, or icons for color-blind users. | P1 |
| Screen reader support | Semantic HTML elements. Route summary must be readable by screen readers: “12-minute route, 4.2 miles, all roads 35 MPH or less.” | P1 |
| User testing | Test with at least 2 users over age 60 during Phase 4 QA. Document and fix any usability issues found. | P0 |

## v1.5 — Fast Follow (4–6 Weeks Post-Launch)

### 5.9 Community Road Reports

User-generated reports are critical for improving data quality and building engagement. This is the “Waze for golf carts” feature.

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Report types | Users can report: road closure, construction, unpaved surface, dangerous intersection, speed limit error, new cart path/trail. | P0 |
| Lightweight submission | One-tap report on the current location; optional text note and photo. No login required for first report (rate-limit by device). | P0 |
| Report display | Active reports shown as icons on the map with recency indicators. Auto-expire after 7 days unless reconfirmed. | P0 |
| Data feedback loop | Community reports feed back into the routing engine’s confidence scoring for road surface and speed data. | P1 |

### 5.10 Share My Route

| **Requirement** | **Description** | **Priority** |
| --- | --- | --- |
| Share link | Generate a unique URL that displays the route on a map. Recipient does not need an account. | P0 |
| ETA sharing | Shared link includes estimated arrival time based on departure time. | P1 |

## v2 — Future Roadmap

- Offline map support (cached tiles + offline routing engine for areas with poor cell coverage)

- Turn-by-turn voice navigation

- Vehicle type toggle: golf cart (≤30 MPH threshold) vs. LSV (≤35 MPH threshold) in settings, with plain-English explanation of the legal distinction

- User accounts with sync across devices

- Native iOS and Android apps (React Native or Flutter)

- Expanded coverage beyond pilot region (see Expansion Criteria below)

- Night/weather awareness: sunset-triggered reminder banner (“Some areas restrict golf carts after dark”), severe weather alerts

- Integration with golf cart OEMs (telemetry, battery range)

- Commercial fleet features (multi-cart tracking, dispatch)

**Expansion Criteria: **Expand to the next region when the pilot achieves all three conditions sustained for 4 consecutive weeks: (1) 100+ weekly active users, (2) <5% data error report rate, (3) 20+ “destination outside area” events pointing to the same geographic cluster. The first expansion target should be wherever the boundary-hit events concentrate. Before expanding, validate the “paved unless proven otherwise” heuristic for the new region and integrate the Mapillary dataset if the region is more rural than suburban Orlando.

# Technical Architecture

## System Overview

CartPath is a three-layer system: a data pipeline that ingests and enriches road network data, a routing API that computes golf-cart-safe routes, and a web client that presents the experience to users.

### 6.1 Data Pipeline

The data pipeline is the foundation of CartPath. It runs as a batch process to build and maintain a golf-cart-optimized road graph for the pilot region. A data audit (March 2026) confirmed 240,878 drivable road segments in the pilot area.

| **Component** | **Approach** | **Notes** |
| --- | --- | --- |
| Speed limit data | Tier 1: OSM Overpass API maxspeed tags (6.4% explicit coverage — 15,314 segments). Tier 2: FDOT Maximum Speed Limit TDA open GIS dataset for state/classified roads (covers primary and secondary road gaps). Tier 3: osm-legal-default-speeds library to infer limits from road class + FL law. Tier 4: Conservative defaults for remaining unknowns (~2.6%). | Combined coverage: ~97%. Primary roads have 81% explicit tags; residential roads are 96% ≤35 MPH when tagged. Re-process weekly. |
| Road surface classification | Tier 1: OSM surface tags (20.7% explicit — 49,895 segments). Tier 2: Road-type heuristic (residential + service = paved by default in suburban FL). Tier 3: Mapillary open road surface dataset for gap-fill. Tier 4: Community reports (v1.5). | Of explicitly tagged roads, 97.5% are paved. Only 1,236 of 49,895 tagged segments are unpaved. “Paved unless proven otherwise” is validated. No AI pipeline needed. |
| Road graph | Build a custom routing graph using OSMnx (Python) or OSRM with a custom Lua profile that penalizes/excludes segments above 35 MPH and applies surface-type weighting. | Store as a pre-built graph in the backend. OSRM with custom profile is recommended for routing speed. |
| Geocoding | Mapbox Geocoding API or Nominatim (self-hosted) for address autocomplete and coordinate resolution. | Mapbox offers better autocomplete UX; Nominatim is free but slower. |

### 6.2 Data Classification Strategy

Based on the pilot region data audit, CartPath does not require a custom AI/ML pipeline for road surface or speed limit classification. The open data ecosystem provides sufficient coverage through a tiered approach.

**Speed Limit Classification (4 tiers):**

- **Tier 1 — Explicit OSM maxspeed tags (6.4%): **15,314 segments have directly tagged speed limits. These are highest-confidence data points and are used as-is.

- **Tier 2 — FDOT GIS open data: **The Florida DOT publishes a free Maximum Speed Limit feature class covering all state and functionally classified roads. This fills the gap for primary roads (81% already tagged) and secondary roads (46% tagged) — the exact categories where incorrect classification is most dangerous.

- **Tier 3 — Road-type inference: **The osm-legal-default-speeds open-source library infers legal speed limits from OSM road classification, lane count, and Florida state law. For the pilot region: residential roads are ≤35 MPH 96% of the time when tagged, service roads are ≤35 MPH 99.5% of the time. These default inferences are high-confidence.

- **Tier 4 — Conservative unknowns (2.6%): **The remaining ~6,305 segments (mostly unclassified roads) are flagged as “unknown” and excluded from the default cart-safe graph. Fallback routing can traverse them with a warning. Community reports (v1.5) will gradually resolve these.

**Road Surface Classification (3 tiers):**

- **Tier 1 — Explicit OSM surface tags (20.7%): **49,895 segments have direct surface tags. Of these, 97.5% are paved (asphalt, concrete, bricks, paving stones) and only 2.5% are unpaved (dirt, gravel, sand, compacted).

- **Tier 2 — Road-type heuristic: **In suburban Central Florida, residential and service roads without surface tags are overwhelmingly paved. The audit validates this: when residential roads do have tags, 97% are paved. Apply a “paved unless proven otherwise” default for residential, tertiary, secondary, and primary road types within the pilot region.

- **Tier 3 — Mapillary open dataset: **For remaining gaps (primarily rural unclassified roads at the periphery of the 30-mile radius), the Mapillary/HeiGIT global road surface dataset provides AI-classified paved/unpaved labels matched to OSM road geometries. This is a free, pre-computed dataset — no custom model training required.

**Why the AI vision pipeline was removed:**

The original PRD (v1.0) proposed training a custom CNN or using Claude’s vision API to classify satellite imagery of road surfaces. The data audit revealed this is unnecessary for the pilot: the combination of OSM tags, road-type heuristics, and the Mapillary open dataset achieves ~98% surface coverage with zero API cost and zero ML infrastructure. The AI approach remains a viable option for future expansion into regions with worse OSM coverage (e.g., rural areas, developing markets), but it is not needed for suburban Orlando.

### 6.3 Service Road Handling

Service roads (parking lots, driveways, alleys, private access roads) represent 143,183 of 240,878 total segments (59.4%) in the pilot region. A clear policy is needed to prevent these from bloating the routing graph while still allowing last-mile connectivity.

**Decision: Cart-legal by default, with a routing weight penalty.**

| **Rule** | **Rationale** |
| --- | --- |
| Classify all service roads as ≤35 MPH (cart-legal) | Of the 416 service roads with explicit speed tags, 414 (99.5%) are ≤35 MPH. The remaining 2 are likely tagging errors. Zero risk of misclassification. |
| Classify all service roads as paved by default | Of the 13,715 service roads with surface tags, 12,922 (94.2%) are paved. The 793 unpaved are predominantly rural. In suburban Orlando the heuristic holds. |
| Apply OSRM routing penalty (10 MPH equivalent speed) | Service roads should be used as last-mile connectors (street-to-parking-lot, entering a shopping center) but never as through-routes. A low speed factor ensures OSRM prefers real streets while still using service roads when they’re the only path to a destination. |
| Exclude service=driveway and service=parking_aisle subtypes | These are too granular for cart routing. Include service=alley, service=parking (main parking lot roads), and untagged service roads. |

**Impact on graph size: **With service subtypes filtered, the routing graph drops from ~240K edges to approximately 120–150K edges. This improves OSRM build times and query performance without sacrificing reachability.

### 6.4 FDOT Data Pipeline

The Florida DOT publishes a free Maximum Speed Limit GIS dataset covering all state highways and roads classified as Rural Major Collector and above. This data fills the critical gap for primary roads (81% OSM-tagged) and secondary roads (46% OSM-tagged) where misclassification is most dangerous. The data is public domain, requires no authentication, and is updated weekly.

**Ingestion strategy: Bulk download and self-host.**

The FDOT Open Data Hub (gis-fdot.opendata.arcgis.com) supports direct downloads in GeoJSON, Shapefile, CSV, KML, and File Geodatabase formats. The recommended approach is a one-time bulk download of the statewide speed limit layer in GeoJSON format, clipped to the pilot region, with a weekly automated refresh.

**FDOT Pipeline Script Requirements (for Claude Code implementation):**

The following script should be implemented as a standalone Python CLI tool that can be run manually or via cron job as part of the weekly data refresh pipeline.

| **Requirement** | **Specification** |
| --- | --- |
| Script name | fdot_speed_ingest.py |
| Language / dependencies | Python 3.10+. Dependencies: geopandas, shapely, requests, pandas, osmnx (for OSM graph loading). No ArcGIS or ArcPy dependency. |
| Input: FDOT data | Download the Maximum Speed Limit TDA feature layer from the FDOT Open Data Hub. Use the GeoJSON download endpoint. If the direct GeoJSON download is unavailable or >500MB, fall back to the ArcGIS Feature Service REST API with pagination (1,000 records per request, iterate with resultOffset). |
| Input: OSM data | Load the pre-built OSM road graph for the pilot region (generated by the Overpass extraction step). Accept as a GeoJSON file, GeoPackage, or osmnx graph pickle. |
| Step 1: Download | Fetch the full statewide FDOT speed limit GeoJSON. Cache locally with a timestamp. Skip download if cached file is <7 days old (configurable via --max-age flag). |
| Step 2: Filter to pilot region | Clip FDOT features to a bounding box or polygon representing the 30-mile Baldwin Park radius. Use geopandas spatial clip. Expected output: ~2,000–5,000 FDOT road segments for the pilot area. |
| Step 3: Reproject | FDOT shapefiles use UTM 17 / NAD 83 (EPSG:26917). GeoJSON downloads are WGS84 (EPSG:4326). Ensure all geometries are in EPSG:4326 before matching. Use geopandas to_crs(). |
| Step 4: Spatial join to OSM | For each FDOT segment, find the nearest OSM way within a 15-meter buffer using a spatial index (geopandas sjoin_nearest or shapely STRtree). Match on geometric proximity, not road name (names are inconsistent between datasets). Output: a mapping of OSM way IDs to FDOT speed limit values. |
| Step 5: Conflict resolution | If an OSM way already has a maxspeed tag AND the FDOT value disagrees: (a) prefer the OSM tag if the difference is ≤5 MPH (likely rounding), (b) log a warning if the difference is >5 MPH, (c) prefer the FDOT value for primary/secondary roads (FDOT is authoritative for state roads), (d) prefer the OSM value for tertiary/residential roads. |
| Step 6: Output | Write a JSON file (osm_speed_enrichment.json) mapping OSM way IDs to enriched speed limit values and their source (osm_tag, fdot, inferred). This file is consumed by the OSRM graph builder. |
| Step 7: Reporting | Print a summary: total FDOT segments downloaded, segments matched to OSM, segments that filled a gap (OSM had no maxspeed), conflicts detected, match rate percentage. |
| CLI flags | --center-lat, --center-lon, --radius-miles (default: 28.5641, -81.3089, 30). --max-age (cache freshness in days, default 7). --osm-graph (path to OSM graph file). --output (path for enrichment JSON). --verbose (detailed logging). |
| Error handling | Retry FDOT download up to 3 times with exponential backoff. Validate GeoJSON structure before processing. If FDOT download fails entirely, exit with error code 1 and clear message (do not silently proceed without FDOT data). |
| Testing | Include a --dry-run flag that downloads and filters FDOT data but skips the OSM matching step, printing segment counts only. Useful for validating the download pipeline independently. |

**FDOT data limitations:**

- **Coverage scope: **FDOT covers state highways and roads classified as Rural Major Collector and above. It does NOT cover residential roads, service roads, or most local streets. These are handled by OSM tags and road-type inference.

- **Temporal lag: **FDOT data reflects the most recent inventory, which may lag behind actual speed limit changes by weeks to months. Community reports (v1.5) are the long-term mitigation.

- **Spatial alignment: **FDOT and OSM use different linear referencing systems and digitization methods. The 15-meter buffer for spatial matching will produce some false matches on parallel roads (e.g., a service road adjacent to a highway). The conflict resolution logic in Step 5 mitigates this by preferring FDOT only for primary/secondary classifications.

### 6.5 Routing API

| **Component** | **Recommendation** |
| --- | --- |
| Routing engine | OSRM (Open Source Routing Machine) with a custom Lua profile that: (a) excludes edges with speed > 35 MPH from the default graph, (b) applies a penalty multiplier to unpaved segments, (c) assigns service roads a low speed factor (10 MPH equivalent) so they serve as last-mile connectors but never as through-routes, (d) excludes service=driveway and service=parking_aisle subtypes entirely, (e) uses 23 MPH as the travel speed for ETA calculations on all other cart-legal roads. |
| Fallback routing | If OSRM returns no route on the filtered graph, re-query on the full graph and annotate non-compliant segments in the response. The client displays an inline warning banner (persistent, expandable, non-blocking) at the top of the route summary card. Banner text: “⚠ This route includes [X] mi on roads above 35 MPH (max: [Y] MPH on [road name]).” Tapping the banner expands to show each non-compliant segment with its speed limit and distance. Non-compliant segments are highlighted in red/orange on the map overlay. |
| API framework | FastAPI (Python) or Express (Node.js). Endpoints: /route (core), /geocode (proxy), /report (community reports in v1.5). |
| Hosting | Single VPS (e.g., DigitalOcean, Hetzner) is sufficient for pilot scale. OSRM is performant enough that one instance handles thousands of routes/day. |

### 6.6 Web Client

| **Component** | **Recommendation** |
| --- | --- |
| Framework | React with Next.js for SSR/SEO. Alternatively, a lightweight Vite + React SPA is simpler for a solo developer. |
| Map library | Mapbox GL JS (free tier: 50K map loads/mo) or Leaflet + OpenStreetMap tiles (fully free, less polished). Mapbox recommended for UX quality. |
| PWA support | Add a service worker and web app manifest so users can “Add to Home Screen” on mobile. This provides a near-native experience without app store distribution. |
| State management | React Context or Zustand for lightweight state. Local storage for saved routes. |

### 6.7 Infrastructure Sizing and Cost

CartPath’s pilot infrastructure is deliberately minimal. The entire stack runs on a single VPS with zero commercial API costs for data.

| **Component** | **Specification** | **Monthly Cost** |
| --- | --- | --- |
| VPS (OSRM + FastAPI) | 2–4 GB RAM, 2 vCPUs, 50 GB SSD. DigitalOcean or Hetzner. OSRM for a regional graph (~150K edges) fits comfortably in 2 GB RAM. | $12–24 |
| Mapbox (maps + geocoding) | Free tier: 50,000 map loads/month, 100,000 geocoding requests/month. At 100 WAU with ~5 routes/week = ~2,000 map loads/month. Headroom: 25x before hitting paid tier. | $0 |
| Domain registration | Single .com or .app domain. | ~$1 (annualized) |
| SSL certificate | Let’s Encrypt (auto-renewing via Certbot). | $0 |
| Analytics | Plausible Cloud ($9/mo) or self-hosted Plausible/Umami on the same VPS ($0). | $0–9 |
| Data sources | OSM (free), FDOT GIS (free), osm-legal-default-speeds (free), Mapillary dataset (free). | $0 |
| Total at pilot scale | 100 WAU, ~500 routes/week. | $13–34/mo |

**Scaling triggers: **(1) Mapbox: if monthly map loads exceed 40,000, evaluate switching to self-hosted tiles with OpenMapTiles (~$0 marginal cost, 1–2 days setup). (2) OSRM: if routing latency exceeds 500ms p95, upgrade VPS to 4 GB RAM. (3) If WAU exceeds 500, consider splitting OSRM and FastAPI onto separate instances.

### 6.8 Data Refresh and Monitoring

The data pipeline runs weekly via cron. A simple monitoring layer prevents silent data rot.

| **Requirement** | **Specification** |
| --- | --- |
| Pipeline health check | After each weekly pipeline run, write a timestamp and summary (segment counts, FDOT match rate) to a health.json file on the VPS. |
| Staleness detection | The FastAPI server checks health.json on startup and every 6 hours. If the data is >10 days old, log a warning and send an alert (email or Slack webhook). |
| FDOT download failure | If the FDOT download fails after 3 retries, the pipeline exits with error code 1. The health.json is NOT updated, triggering the staleness alert. The previous week’s data remains in use (safe degradation). |
| OSM data validation | After each Overpass extraction, compare the total segment count to the previous run. If the count drops by >10%, log a warning (possible API issue or data regression). Do not auto-deploy the new graph; require manual review. |

# Data Strategy and Sources

A comprehensive data audit was conducted on March 24, 2026, querying all 240,878 drivable road segments within the 30-mile pilot radius via the OSM Overpass API. The following table reflects actual measured coverage, not estimates.

| **Data Type** | **Primary Source** | **Gap-Fill Sources** | **Measured Coverage** | **Confidence** |
| --- | --- | --- | --- | --- |
| Speed limits | OSM maxspeed tags | FDOT GIS + osm-legal-default-speeds | 6.4% explicit; 91.2% with inference | High |
| Road surface | OSM surface tags | Road-type heuristic + Mapillary dataset | 20.7% explicit; ~98% with heuristic | High |
| Road geometry | OSM way data | N/A | 100% (240,878 segments) | High |
| Address geocoding | Mapbox Geocoding API | Nominatim | ~99% | High |
| Base map tiles | Mapbox / OSM raster tiles | N/A | 100% | High |

## Audit Key Findings

- **Speed limits are highly inferrable: **85% of all road segments are residential (62,963) or service (143,183) roads, which are nearly universally ≤35 MPH in suburban Orlando. Of the 2,449 residential roads with explicit tags, 96% are ≤35 MPH. Primary roads have 81% explicit tag coverage; secondary roads have 46%.

- **Surface tags confirm paved dominance: **Of 49,895 explicitly tagged roads, 48,659 (97.5%) are paved and only 1,236 (2.5%) are unpaved. The most common surface is asphalt (42,743 segments), followed by paved (3,722), bricks (1,132), and concrete (941). Unpaved roads are predominantly dirt (136), unpaved (879), gravel (52), and sand (51).

- **Zero commercial API costs: **The entire data stack uses free, open-source, or open-data sources: OSM (ODbL), FDOT GIS (public domain), osm-legal-default-speeds (open source), and the Mapillary road surface dataset (open data). No HERE API, no Google Maps API, no satellite imagery provider needed for v1.

- **Service roads dominate the segment count: **143,183 of 240,878 segments (59.4%) are service roads (parking lots, driveways, alleys). These have extremely low explicit tagging but are categorically ≤35 MPH and paved. Consider filtering these from the primary routing graph to reduce noise, or treating them as last-mile connectors only.

## Data Quality Risks

- **Inference errors on edge cases: **Road-type inference works well for residential and service roads but is less reliable for “unclassified” roads (5,162 segments, only 7% tagged). These are the most likely to have unexpected speed limits. FDOT data and community reports are the primary mitigations.

- **Stale speed limits: **Speed limits change when roads are re-zoned. Our weekly re-processing cadence should catch most changes, but community reports (v1.5) are the best long-term defense.

- **Construction and closures: **Neither OSM nor FDOT provides real-time closure data reliably. This is a v1 known limitation, partially addressed by community reports in v1.5.

- **Surface heuristic breaks outside suburban areas: **The “paved unless proven otherwise” heuristic is validated for suburban Orlando but will not hold in rural Florida. Expansion beyond the pilot region will require the Mapillary dataset or a custom classifier to maintain accuracy.

# Success Metrics

## Pilot KPIs (First 90 Days)

| **Metric** | **Target** | **How Measured** |
| --- | --- | --- |
| Active users (WAU) | 100+ weekly active users by day 90 | Analytics (Plausible or Mixpanel) |
| Routes calculated | 500+ routes/week by day 90 | API logging |
| Route compliance rate | >95% of routes are fully ≤35 MPH compliant | Routing engine metrics |
| User retention (D7) | >30% of new users return within 7 days | Analytics cohort analysis |
| Data accuracy reports | <5% of community reports flag a speed limit or surface error | Community report categorization |
| Page load time | <3 seconds on 4G mobile connection | Lighthouse / Web Vitals |

## North Star Metric

**Routes completed per user per week. **This measures whether CartPath is becoming a habitual part of users’ golf cart routine, not just a novelty. Target: 2+ routes/user/week within the active user base by day 90.

## Analytics Event Taxonomy

The following events must be instrumented in the v1 web client to measure the KPIs above. Each event includes an anonymous session ID (no login required) and a UTC timestamp. No PII is collected.

| **Event Name** | **Triggered When** | **Measures KPI** |
| --- | --- | --- |
| app_opened | User opens the app or returns from background | WAU |
| route_requested | User submits start/end and the routing API is called. Payload: start coords, end coords. | Routes calculated |
| route_displayed | Route is rendered on the map. Payload: compliance status (full / partial / fallback), segment count. | Route compliance rate |
| route_started | User taps “Go” or begins following the route. | Route engagement |
| route_completed | User arrives at destination or dismisses the route after >80% progress. | North Star (routes/user/week) |
| route_saved | User saves a route to favorites. | Feature usage |
| destination_outside_area | Destination fails the coverage boundary check. Payload: destination coords. | Expansion demand signal |
| error_reported | User taps “Report a problem.” Payload: route ID, category (if selected). | Data accuracy |
| page_load_time | Web Vitals API measurement on initial load. Payload: LCP, FID, CLS. | Performance |
| multi_stop_requested | User searches for a new destination while a route is active, or attempts to add a waypoint. Payload: current route ID. | Multi-stop demand signal (informs v1.5 prioritization) |

# Go-to-Market Strategy

## Pilot Launch Plan

The pilot is not a marketing event — it’s a learning exercise. The goal is to get 100 real users providing real feedback, not to “launch” publicly.

| **Channel** | **Tactic** | **Expected Reach** |
| --- | --- | --- |
| Local Facebook groups | Post in Baldwin Park community groups and Orlando golf cart owner groups. Offer early access and ask for feedback. Personal, conversational tone. | 50–100 users |
| Golf cart dealerships | Partner with 2–3 local dealers (e.g., Golf Cart Resource in Orlando) to include a CartPath flyer with new cart sales or service visits. | 20–50 users |
| Nextdoor | Post in Baldwin Park and surrounding neighborhoods. Frame as “a neighbor building something for cart owners.” | 30–60 users |
| Word of mouth | Seed with 10–15 personal contacts who are cart owners. Ask each to share with 2–3 friends. | 20–40 users |

## Monetization (Post-Pilot)

v1 is free. Monetization decisions will be informed by pilot learnings. Early candidates include:

- **Freemium model: **Free core routing with paid features (offline maps, advanced route planning, ad-free experience).

- **Local business partnerships: **Golf-cart-friendly businesses (restaurants, shops) could pay for promoted destinations or “Cart-friendly” badges on the map.

- **Affiliate/referral: **Partnerships with golf cart accessory or insurance companies.

# Risks and Mitigations

| **Risk** | **Severity** | **Likelihood** | **Mitigation** |
| --- | --- | --- | --- |
| Inaccurate speed limit data causes routing onto unsafe roads | High | Medium | Tiered data approach: OSM tags + FDOT GIS + road-type inference covers 91.2%. Display disclaimers. Implement community reporting ASAP. Add “Report an error” CTA on every route. |
| Road-type inference fails on edge cases | Medium | Low | Only 2.6% of roads fall into the “unknown” tier. These are excluded from the default cart-safe graph and shown with warnings in fallback mode. Community reports will resolve over time. |
| Low user adoption in pilot area | High | Medium | Hyper-local distribution (Facebook groups, dealers). Build for one community perfectly rather than many communities poorly. |
| Liability if a user has an accident on a recommended route | High | Low | Legal disclaimer on app launch and route display. Consult an attorney. Frame routes as “suggested” not “safe.” |
| “Paved unless proven otherwise” heuristic fails for expansion regions | Medium | Medium | Heuristic is validated for suburban Orlando only. Expansion to rural or non-FL regions will require Mapillary dataset integration or a custom classifier. Plan this before expanding. |
| Scope creep delays launch | Medium | High | Enforce the v1 / v1.5 / v2 phasing strictly. Ship the core routing engine first; everything else follows. |

# Development Timeline

Estimated timeline for a solo developer or 2-person team working full-time. Adjust if part-time. Note: removal of the AI vision pipeline from v1.0 reduces the data pipeline phase by approximately 2 weeks.

| **Phase** | **Duration** | **Deliverables** |
| --- | --- | --- |
| Phase 1: Data Pipeline | 2 weeks | OSM data extraction for pilot region via Overpass API. Speed limit graph built with tiered classification (OSM tags + FDOT GIS + road-type inference). Surface classification applied. Pre-built routing graph generated. |
| Phase 2: Routing Engine | 2–3 weeks | OSRM instance with custom Lua profile. FastAPI wrapper with /route endpoint. Fallback routing with segment warnings. |
| Phase 3: Web Client | 3–4 weeks | React PWA with map, search, route display. Saved routes. ETA display. Mobile-responsive design. |
| Phase 4: Integration & QA | 2 weeks | End-to-end testing. Drive-test 20+ routes in pilot area. Fix data quality issues. Performance optimization. |
| Phase 5: Pilot Launch | 1 week | Deploy to production VPS. Seed first 20–30 users. Set up analytics. Begin collecting feedback. |
| Phase 6: v1.5 Features | 4–6 weeks post-launch | Community reports. Share my route. Iterate based on pilot feedback. |

**Total estimated time to pilot launch: 10–12 weeks.** (Reduced from 11–14 weeks in v1.0 due to elimination of AI vision pipeline.)

# Legal and Compliance Considerations

- **Routing disclaimer: **CartPath provides suggested routes based on available data. Routes are not guaranteed to be legal, safe, or accessible for all vehicles. Users are responsible for obeying all local traffic laws. This disclaimer must appear on first use and be accessible from the route screen.

- **Golf cart vs. LSV/NEV distinction: **Florida law distinguishes between golf carts (max 20 MPH, no VIN, limited equipment) and Low-Speed Vehicles/Neighborhood Electric Vehicles (max 25 MPH, street-legal equipment, VIN required). LSVs may operate on roads with speed limits ≤35 MPH (FL Statute 316.2122); golf carts are limited to ≤30 MPH in some municipalities. CartPath v1 defaults to the 35 MPH LSV threshold. A vehicle type toggle (switching to ≤30 MPH) is planned for v2. The app should include a brief note in its legal/help screen explaining this distinction so users can self-assess which rules apply to their vehicle.

- **Multi-county jurisdictions: **The 30-mile pilot radius crosses Orange, Seminole, Osceola, and potentially Lake counties. Each county and municipality may impose additional golf cart restrictions beyond state law: designated cart corridors, time-of-day limits, or specific road prohibitions. v1 includes a general disclaimer noting this. The app’s “About” screen should link to each county’s golf cart ordinance page. If any roads are identified as explicitly prohibited by local ordinance, exclude them from the routing graph manually (expected: 10–20 roads, curated by hand). Community reports (v1.5) will crowd-source additional local restrictions over time.

- **Night and weather restrictions: **Some FL municipalities restrict golf cart operation after dark or during severe weather. v1 includes a line in the legal disclaimer: “Some areas restrict golf cart use after dark or during severe weather. Check local regulations.” A sunset-aware reminder banner is planned for v2.

- **Data privacy: **v1 stores no personal data (routes are in local storage only). Analytics use anonymous session IDs with no PII. When user accounts are added in v2, comply with Florida’s data privacy laws and consider CCPA/GDPR if expanding beyond FL.

- **OSM license compliance: **OpenStreetMap data is licensed under ODbL. CartPath must provide attribution (“© OpenStreetMap contributors”) on the map interface.

- **API terms of service: **Verify compliance with Mapbox TOS for commercial use of geocoding and map tiles. All other data sources (OSM, FDOT, Mapillary) are open data with permissive licenses.

- **Golf cart road-use laws: **Florida Statute 316.212 governs golf cart operation; FL Statute 316.2122 governs LSVs. CartPath should link to or summarize both statutes for user education.

# Open Questions

All open questions from v1.0 and the gap analysis have been resolved. This table serves as a decision log.

| **#** | **Question** | **Decision** | **Status** |
| --- | --- | --- | --- |
| 1 | OSM speed limit coverage in pilot area? | 6.4% explicit, 91.2% with inference. Data audit complete. | Resolved |
| 2 | Multi-stop routes in v1? | Skip for v1. Add multi_stop_requested analytics event to track demand. Revisit for v1.5 if data warrants. | Resolved |
| 3 | Attorney review of disclaimer? | No. Use the disclaimer as written in Section 5.7. Revisit if user base exceeds 500 or before any paid tier launches. | Resolved |
| 4 | AI vision pipeline for surface classification? | Eliminated. Open data covers ~98% of surface classification at zero cost. | Resolved |
| 5 | Fallback route warning UX? | Inline banner: persistent, expandable, non-blocking. Amber/warning color. Shows max speed and distance of each non-compliant segment. Tapping expands detail. Non-compliant segments highlighted on map. | Resolved |
| 6 | Service road handling? | Cart-legal by default, 10 MPH routing penalty. Exclude driveway/parking_aisle subtypes. | Resolved |
| 7 | FDOT data ingestion? | Bulk download, self-host, spatial join. Script spec in Section 6.4. | Resolved |
| 8 | Pilot boundary handling? | Soft boundary with partial route option. See Section 5.5. | Resolved |
| 9 | Golf cart vs. LSV? | Default 35 MPH (LSV) for v1. Toggle deferred to v2. | Resolved |
| 10 | Error states and feedback? | 5 error states specced. Mailto link for problem reports. See Section 5.6. | Resolved |
| 11 | Multi-county jurisdictions? | Disclaimer + county ordinance links + manual road exclusions. | Resolved |
| 12 | Analytics platform? | Plausible Cloud ($9/mo) recommended for ease of setup. Self-hosted is fallback. | Resolved |

# Appendix

## A. Florida Golf Cart Law Summary

Under Florida Statute 316.212, golf carts may be operated on roads with posted speed limits of 35 MPH or less. Golf carts must be equipped with headlights, brake lights, turn signals, and mirrors when operated on public roads. Operators must be at least 14 years old. Local municipalities may impose additional restrictions or designate specific golf cart routes.

## B. Competitive Landscape

| **Product** | **Golf Cart Routing?** | **Speed Limit Filtering?** | **Road Surface Info?** | **Notes** |
| --- | --- | --- | --- | --- |
| Google Maps | No | No | No | Routes for cars. Sends carts onto highways. |
| Apple Maps | No | No | No | Same as Google Maps for this use case. |
| Waze | No | No | No | Community reports are valuable but routing is car-centric. |
| GolfCartMaps.com | Partial | No | No | Static map overlays of cart-legal zones. No routing. |
| CartPath (us) | Yes | Yes | Yes (data-driven) | Purpose-built. Only solution with all three capabilities. |

## C. Data Audit Results (March 24, 2026)

Full results from the Overpass API query of the 30-mile Baldwin Park pilot radius. Query covered all highway types: primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, residential, unclassified, living_street, and service.

| **Road Type** | **Segments** | **Has Speed Tag** | **Speed %** | **≤35 MPH (of tagged)** | **Has Surface Tag** | **Surface %** |
| --- | --- | --- | --- | --- | --- | --- |
| primary | 7,670 | 6,221 | 81.1% | 761 (12.2%) | 7,502 | 97.8% |
| secondary | 7,781 | 3,542 | 45.5% | 952 (26.9%) | 6,895 | 88.6% |
| tertiary | 11,890 | 2,244 | 18.9% | 1,396 (62.2%) | 6,250 | 52.6% |
| residential | 62,963 | 2,449 | 3.9% | 2,344 (95.7%) | 12,938 | 20.5% |
| service | 143,183 | 416 | 0.3% | 414 (99.5%) | 13,715 | 9.6% |
| unclassified | 5,162 | 361 | 7.0% | 282 (78.1%) | 1,670 | 32.3% |
| living_street | 95 | 3 | 3.2% | 3 (100%) | 29 | 30.5% |
| links (all) | 2,134 | 78 | 3.7% | 35 (44.9%) | 896 | 42.0% |

**Cart-legality summary: **6,187 segments (2.6%) are definitively ≤35 MPH from tags. 213,571 segments (88.6%) are likely ≤35 MPH from road-type inference. 14,815 segments (6.1%) are likely >35 MPH. 6,305 segments (2.6%) are unknown.

**Surface summary: **Top surface values: asphalt (42,743), no tag (190,983), paved (3,722), bricks (1,132), concrete (941), unpaved (879), dirt (136), paving_stones (97), gravel (52), sand (51). Total unpaved: 1,236 of 49,895 tagged segments (2.5%).

*End of Document*