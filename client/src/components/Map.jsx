import React, { useRef, useEffect, useState } from 'react';
import mapboxgl from 'mapbox-gl';

// Token set via environment variable at build time
const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';
mapboxgl.accessToken = MAPBOX_TOKEN;

const SPEED_COLORS = {
  legal_low: '#22c55e',    // green — ≤25 MPH
  legal_high: '#eab308',   // yellow — 26-35 MPH
  illegal: '#ef4444',      // red — >35 MPH
};

// Line patterns for accessibility (non-color indicators per PRD)
const SPEED_DASH_PATTERNS = {
  legal_low: null,          // solid line — ≤25 MPH (safest)
  legal_high: [6, 3],       // dashed — 26-35 MPH (caution)
  illegal: [2, 2],          // dotted — >35 MPH (not cart-legal)
};

const ROUTE_COLORS = {
  compliant: '#16a34a',
  noncompliant: '#f97316',
};

const ALT_ROUTE_COLORS = ['#6b7280', '#9ca3af'];  // Gray shades for non-selected alternatives

export default function Map({ center, route, alternatives = [], selectedAltIndex = 0, userLocation }) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const userMarker = useRef(null);
  const altLayerIds = useRef([]);  // Track created alternative layer/source IDs for cleanup
  const [mapLoaded, setMapLoaded] = useState(false);

  // Initialize map
  useEffect(() => {
    if (map.current || !MAPBOX_TOKEN) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/streets-v12',
      center: [center.lon, center.lat],
      zoom: 13,
      attributionControl: true,
      customAttribution: '© OpenStreetMap contributors',
    });

    // Navigation controls with 56px touch targets
    const nav = new mapboxgl.NavigationControl({ showCompass: false });
    map.current.addControl(nav, 'bottom-right');

    // Geolocate control
    const geolocate = new mapboxgl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
    });
    map.current.addControl(geolocate, 'bottom-right');

    map.current.on('load', () => {
      setMapLoaded(true);
      loadCoverageBoundary(map.current);
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  // Update user marker
  useEffect(() => {
    if (!map.current || !userLocation) return;

    if (!userMarker.current) {
      const el = document.createElement('div');
      el.className = 'user-marker';
      userMarker.current = new mapboxgl.Marker(el)
        .setLngLat([userLocation.lon, userLocation.lat])
        .addTo(map.current);
    } else {
      userMarker.current.setLngLat([userLocation.lon, userLocation.lat]);
    }
  }, [userLocation]);

  // Display route alternatives and selected route
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    // Remove previously created alternative layers/sources
    for (const sourceId of altLayerIds.current) {
      const layerIds = [`${sourceId}-line`, `${sourceId}-casing`];
      layerIds.forEach((id) => {
        if (map.current.getLayer(id)) map.current.removeLayer(id);
      });
      if (map.current.getSource(sourceId)) map.current.removeSource(sourceId);
    }
    altLayerIds.current = [];

    // Remove primary route layers
    const primaryIds = ['route-line', 'route-line-casing'];
    primaryIds.forEach((id) => {
      if (map.current.getLayer(id)) map.current.removeLayer(id);
    });
    if (map.current.getSource('route')) map.current.removeSource('route');

    if (!route || !route.route_geometry) return;

    // Draw non-selected alternatives first (behind the selected route)
    if (alternatives.length > 1) {
      alternatives.forEach((alt, i) => {
        if (i === selectedAltIndex || !alt.route_geometry) return;

        const sourceId = `route-alt-${i}`;
        altLayerIds.current.push(sourceId);
        map.current.addSource(sourceId, {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: { compliance: alt.compliance, index: i },
            geometry: alt.route_geometry,
          },
        });

        map.current.addLayer({
          id: `route-alt-${i}-casing`,
          type: 'line',
          source: sourceId,
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: { 'line-color': '#ffffff', 'line-width': 6, 'line-opacity': 0.5 },
        });

        map.current.addLayer({
          id: `route-alt-${i}-line`,
          type: 'line',
          source: sourceId,
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': ALT_ROUTE_COLORS[i % ALT_ROUTE_COLORS.length],
            'line-width': 4,
            'line-opacity': 0.6,
            'line-dasharray': [4, 2],
          },
        });
      });
    }

    // Draw selected route on top
    map.current.addSource('route', {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: { compliance: route.compliance },
        geometry: route.route_geometry,
      },
    });

    map.current.addLayer({
      id: 'route-line-casing',
      type: 'line',
      source: 'route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 8 },
    });

    const color = route.compliance === 'full'
      ? ROUTE_COLORS.compliant
      : ROUTE_COLORS.noncompliant;

    const routePaint = { 'line-color': color, 'line-width': 5 };
    // Accessibility: use dash pattern to distinguish compliant from non-compliant
    if (route.compliance !== 'full') {
      routePaint['line-dasharray'] = SPEED_DASH_PATTERNS.legal_high;
    }

    map.current.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: routePaint,
    });

    // Fit map to all route bounds (include alternatives for context)
    const allCoords = [];
    if (alternatives.length > 1) {
      alternatives.forEach((alt) => {
        if (alt.route_geometry?.coordinates) {
          allCoords.push(...alt.route_geometry.coordinates);
        }
      });
    } else if (route.route_geometry?.coordinates) {
      allCoords.push(...route.route_geometry.coordinates);
    }

    if (allCoords.length > 0) {
      const bounds = allCoords.reduce(
        (b, c) => b.extend(c),
        new mapboxgl.LngLatBounds(allCoords[0], allCoords[0])
      );
      map.current.fitBounds(bounds, { padding: 60 });
    }
  }, [route, alternatives, selectedAltIndex, mapLoaded]);

  return (
    <div ref={mapContainer} className="map-container" role="application" aria-label="Map">
      {!MAPBOX_TOKEN && (
        <div className="map-token-warning" role="alert">
          <h2>Map unavailable</h2>
          <p>Set <code>VITE_MAPBOX_TOKEN</code> in <code>client/.env</code> to enable the map.</p>
          <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
            Get a free token at mapbox.com
          </p>
        </div>
      )}
    </div>
  );
}

async function loadCoverageBoundary(mapInstance) {
  try {
    const resp = await fetch('/data/coverage_boundary.geojson');
    if (!resp.ok) return;
    const data = await resp.json();

    mapInstance.addSource('coverage-boundary', { type: 'geojson', data });
    mapInstance.addLayer({
      id: 'coverage-boundary-line',
      type: 'line',
      source: 'coverage-boundary',
      paint: {
        'line-color': '#6b7280',
        'line-width': 2,
        'line-dasharray': [4, 4],
      },
    });
  } catch {
    // Coverage boundary not available — non-critical
  }
}
