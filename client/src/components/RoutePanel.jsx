import React, { useState } from 'react';
import { trackEvent } from '../utils/analytics';

export default function RoutePanel({ route, onSave, userLocation, startCoords }) {
  const [showSegments, setShowSegments] = useState(false);
  const [saveLabel, setSaveLabel] = useState('');
  const [showSaveForm, setShowSaveForm] = useState(false);

  if (!route) return null;

  const handleStartRoute = () => {
    trackEvent('route_started', { route_id: route.route_id });
  };

  const handleSave = () => {
    if (!saveLabel.trim()) return;
    const saved = JSON.parse(localStorage.getItem('cartpath_saved_routes') || '[]');
    saved.unshift({
      label: saveLabel.trim(),
      route_id: route.route_id,
      summary: route.summary,
      distance_miles: route.distance_miles,
      duration_minutes: route.duration_minutes,
      start: startCoords || userLocation || { lat: 0, lon: 0 },
      end: route.route_geometry?.coordinates?.at(-1)
        ? { lon: route.route_geometry.coordinates.at(-1)[0], lat: route.route_geometry.coordinates.at(-1)[1] }
        : { lat: 0, lon: 0 },
      saved_at: new Date().toISOString(),
    });
    // Keep max 10
    localStorage.setItem('cartpath_saved_routes', JSON.stringify(saved.slice(0, 10)));
    trackEvent('route_saved');
    setShowSaveForm(false);
    setSaveLabel('');
  };

  const reportUrl = `mailto:feedback@cartpath.app?subject=Route%20Problem%20Report&body=Route%20ID:%20${route.route_id}%0ADescription:%20`;

  return (
    <div className="route-panel" role="region" aria-label="Route details">
      <div className="route-summary">
        <span className="route-summary-text" aria-live="polite">
          {route.summary}
        </span>
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

      {showSegments && route.segments && (
        <ul className="segment-list" aria-label="Route segments">
          {route.segments.map((seg, i) => (
            <li key={i} className={seg.compliant ? '' : 'segment-noncompliant'}>
              <span className="segment-name">{seg.road_name || 'Unnamed road'}</span>
              <span className="segment-info">
                {seg.distance_miles} mi · ~{seg.duration_minutes} min
                {seg.speed_limit && ` · ${seg.speed_limit} MPH`}
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
