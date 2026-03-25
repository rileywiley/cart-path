import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { apiFetch } from '../utils/api';
import { trackEvent } from '../utils/analytics';

export default function SavedRoutes({ onSelect, onClose }) {
  const { isAuthenticated } = useAuth();
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [importBanner, setImportBanner] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      // Fetch from server
      setLoading(true);
      apiFetch('/api/saved-routes')
        .then((resp) => (resp.ok ? resp.json() : { routes: [] }))
        .then((data) => {
          setRoutes(data.routes || []);
          // Check if there are localStorage routes to import
          const local = JSON.parse(localStorage.getItem('cartpath_saved_routes') || '[]');
          if (local.length > 0) setImportBanner(true);
        })
        .catch(() => setRoutes([]))
        .finally(() => setLoading(false));
    } else {
      // Guest: read from localStorage
      setRoutes(JSON.parse(localStorage.getItem('cartpath_saved_routes') || '[]'));
    }
  }, [isAuthenticated]);

  const handleDelete = async (route, index) => {
    if (isAuthenticated && route.id) {
      await apiFetch(`/api/saved-routes/${route.id}`, { method: 'DELETE' });
      setRoutes((prev) => prev.filter((_, i) => i !== index));
    } else {
      const updated = routes.filter((_, i) => i !== index);
      localStorage.setItem('cartpath_saved_routes', JSON.stringify(updated));
      setRoutes(updated);
    }
  };

  const handleImport = async () => {
    const local = JSON.parse(localStorage.getItem('cartpath_saved_routes') || '[]');
    if (local.length === 0) return;

    try {
      const resp = await apiFetch('/api/saved-routes/import', {
        method: 'POST',
        body: JSON.stringify({ routes: local }),
      });
      if (resp.ok) {
        const data = await resp.json();
        trackEvent('routes_imported', { imported: data.imported, skipped: data.skipped });
        localStorage.removeItem('cartpath_saved_routes');
        setImportBanner(false);
        // Refresh the list
        const listResp = await apiFetch('/api/saved-routes');
        if (listResp.ok) {
          const listData = await listResp.json();
          setRoutes(listData.routes || []);
        }
      }
    } catch {
      // silently fail
    }
  };

  const handleSelect = (route) => {
    // Normalize coordinates for both server and localStorage formats
    const start = route.start || { lat: route.start_lat, lon: route.start_lon };
    const end = route.end || { lat: route.end_lat, lon: route.end_lon };
    onSelect({ ...route, start, end });
  };

  return (
    <div className="saved-routes-panel" role="dialog" aria-label="Saved routes">
      <div className="saved-routes-header">
        <h2>Saved Routes</h2>
        <button className="btn-dismiss" onClick={onClose} aria-label="Close saved routes">
          Close
        </button>
      </div>

      {importBanner && (
        <div className="import-banner">
          <p>You have saved routes on this device. Import them to your account?</p>
          <div className="import-banner-actions">
            <button className="btn-primary btn-small" onClick={handleImport}>
              Import
            </button>
            <button className="btn-dismiss btn-small" onClick={() => setImportBanner(false)}>
              Dismiss
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="saved-routes-empty">Loading...</p>
      ) : routes.length === 0 ? (
        <p className="saved-routes-empty">
          No saved routes yet. Search for a destination and tap "Save" to add one.
        </p>
      ) : (
        <ul className="saved-routes-list" role="list">
          {routes.map((route, i) => (
            <li key={route.id || i} className="saved-route-item">
              <button
                className="saved-route-button"
                onClick={() => handleSelect(route)}
                aria-label={`Navigate: ${route.label}`}
              >
                <span className="saved-route-label">{route.label}</span>
                <span className="saved-route-summary">
                  {route.distance_miles} mi · ~{Math.round(route.duration_minutes)} min
                </span>
              </button>
              <button
                className="btn-dismiss btn-small"
                onClick={() => handleDelete(route, i)}
                aria-label={`Delete ${route.label}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {!isAuthenticated && routes.length > 0 && (
        <p className="saved-routes-sync-hint">
          Sign in to sync your routes across devices.
        </p>
      )}
    </div>
  );
}
