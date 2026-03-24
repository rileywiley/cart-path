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

const ROUTE_COLORS = {
  compliant: '#16a34a',
  noncompliant: '#f97316',
};

export default function Map({ center, route, userLocation }) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const userMarker = useRef(null);
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

  // Display route
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    // Remove existing route layers
    const layerIds = ['route-line', 'route-line-casing'];
    layerIds.forEach((id) => {
      if (map.current.getLayer(id)) map.current.removeLayer(id);
    });
    if (map.current.getSource('route')) map.current.removeSource('route');

    if (!route || !route.route_geometry) return;

    map.current.addSource('route', {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: { compliance: route.compliance },
        geometry: route.route_geometry,
      },
    });

    // Route casing (outline)
    map.current.addLayer({
      id: 'route-line-casing',
      type: 'line',
      source: 'route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#ffffff',
        'line-width': 8,
      },
    });

    // Route fill
    const color = route.compliance === 'full'
      ? ROUTE_COLORS.compliant
      : ROUTE_COLORS.noncompliant;

    map.current.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': color,
        'line-width': 5,
      },
    });

    // Fit map to route bounds
    const coords = route.route_geometry.coordinates;
    if (coords && coords.length > 0) {
      const bounds = coords.reduce(
        (b, c) => b.extend(c),
        new mapboxgl.LngLatBounds(coords[0], coords[0])
      );
      map.current.fitBounds(bounds, { padding: 60 });
    }
  }, [route, mapLoaded]);

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
