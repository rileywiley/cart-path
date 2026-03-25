import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { apiFetch } from '../utils/api';
import { trackEvent } from '../utils/analytics';

export default function RoutePanel({
  route,
  alternatives = [],
  selectedAltIndex = 0,
  onSelectAlternative,
  onSave,
  userLocation,
  startCoords,
  onStartRoute,
}) {
  const { isAuthenticated } = useAuth();
  const [showSegments, setShowSegments] = useState(false);
  const [saveLabel, setSaveLabel] = useState('');
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [saveError, setSaveError] = useState('');

  if (!route) return null;

  const handleStartRoute = () => {
    trackEvent('route_started', { route_id: route.route_id });
    onStartRoute?.();
  };

  const handleSave = async () => {
    if (!saveLabel.trim()) return;
    setSaveError('');

    const start = startCoords || userLocation || { lat: 0, lon: 0 };
    const end = route.route_geometry?.coordinates?.at(-1)
      ? { lon: route.route_geometry.coordinates.at(-1)[0], lat: route.route_geometry.coordinates.at(-1)[1] }
      : { lat: 0, lon: 0 };

    if (isAuthenticated) {
      // Save to server
      try {
        const resp = await apiFetch('/api/saved-routes', {
          method: 'POST',
          body: JSON.stringify({
            label: saveLabel.trim(),
            route_id: route.route_id,
            summary: route.summary,
            distance_miles: route.distance_miles,
            duration_minutes: route.duration_minutes,
            start,
            end,
          }),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          setSaveError(data.detail || 'Failed to save route.');
          return;
        }
      } catch {
        setSaveError('Failed to save route. Please try again.');
        return;
      }
    } else {
      // Save to localStorage (guest mode)
      const saved = JSON.parse(localStorage.getItem('cartpath_saved_routes') || '[]');
      saved.unshift({
        label: saveLabel.trim(),
        route_id: route.route_id,
        summary: route.summary,
        distance_miles: route.distance_miles,
        duration_minutes: route.duration_minutes,
        start,
        end,
        saved_at: new Date().toISOString(),
      });
      localStorage.setItem('cartpath_saved_routes', JSON.stringify(saved.slice(0, 10)));
    }

    trackEvent('route_saved');
    setShowSaveForm(false);
    setSaveLabel('');
    setSaveError('');
  };

  const reportUrl = `mailto:feedback@cartpath.app?subject=Route%20Problem%20Report&body=Route%20ID:%20${route.route_id}%0ADescription:%20`;

  return (
    <div className="route-panel" role="region" aria-label="Route details">
      {/* Route alternative tabs */}
      {alternatives.length > 1 && (
        <div className="route-alternatives" role="tablist" aria-label="Route options">
          {alternatives.map((alt, i) => (
            <button
              key={alt.route_id}
              role="tab"
              aria-selected={i === selectedAltIndex}
              className={`route-alt-tab ${i === selectedAltIndex ? 'route-alt-tab--active' : ''}`}
              onClick={() => onSelectAlternative?.(i)}
            >
              <span className="route-alt-label">{alt.label}</span>
              <span className="route-alt-info">
                ~{Math.round(alt.duration_minutes)} min · {alt.distance_miles} mi
              </span>
              {alt.residential_pct >= 75 && (
                <span className="route-alt-badge" aria-label="Mostly residential roads">
                  Residential
                </span>
              )}
              {alt.compliance !== 'full' && (
                <span className="route-alt-warning" aria-label="Includes high-speed roads">
                  ⚠
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      <div className="route-summary">
        <span className="route-summary-text" aria-live="polite" aria-label={
          route.compliance === 'full'
            ? `${Math.round(route.duration_minutes)}-minute route, ${route.distance_miles} miles, all roads ${route.max_speed_mph || 35} MPH or less`
            : `${Math.round(route.duration_minutes)}-minute route, ${route.distance_miles} miles, includes roads above speed limit`
        }>
          {route.summary}
        </span>
        {route.residential_pct != null && (
          <span className="route-residential-pct">
            {Math.round(route.residential_pct)}% residential roads
          </span>
        )}
      </div>

      <div className="route-actions">
        <button className="btn-primary btn-go" onClick={handleStartRoute} aria-label="Start navigation">
          Go
        </button>
        <button
          className="btn-secondary"
          onClick={() => setShowSaveForm(!showSaveForm)}
          aria-label="Save this route"
        >
          Save
        </button>
        <button
          className="btn-secondary"
          onClick={() => setShowSegments(!showSegments)}
          aria-expanded={showSegments}
          aria-label="Show route segments"
        >
          {showSegments ? 'Hide details' : 'Details'}
        </button>
      </div>

      {showSaveForm && (
        <div className="save-form">
          <label htmlFor="save-label" className="sr-only">Route label</label>
          <input
            id="save-label"
            type="text"
            placeholder="Label (e.g., Home to Publix)"
            value={saveLabel}
            onChange={(e) => setSaveLabel(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            autoFocus
          />
          <button className="btn-primary" onClick={handleSave}>Save</button>
        </div>
      )}
      {saveError && <p className="save-error">{saveError}</p>}
      {showSaveForm && !isAuthenticated && (
        <p className="save-sync-hint">Sign in to sync across devices.</p>
      )}

      {showSegments && route.segments && (
        <ul className="segment-list" aria-label="Route segments">
          {route.segments.map((seg, i) => (
            <li key={i} className={`${seg.compliant ? '' : 'segment-noncompliant'} ${seg.is_residential ? 'segment-residential' : ''}`}>
              <span className="segment-name">{seg.road_name || 'Unnamed road'}</span>
              <span className="segment-info">
                {seg.distance_miles} mi · ~{seg.duration_minutes} min
                {seg.speed_limit && ` · ${seg.speed_limit} MPH`}
                {seg.is_residential && ' · Residential'}
              </span>
            </li>
          ))}
        </ul>
      )}

      <a href={reportUrl} className="report-link" aria-label="Report a problem with this route">
        Report a problem
      </a>
    </div>
  );
}
