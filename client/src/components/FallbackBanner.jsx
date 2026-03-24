import React, { useState } from 'react';

export default function FallbackBanner({ warnings }) {
  const [expanded, setExpanded] = useState(false);

  if (!warnings || warnings.length === 0) return null;

  const totalMiles = warnings.reduce((sum, w) => sum + w.distance_miles, 0);
  const maxSpeed = Math.max(...warnings.map((w) => w.speed_limit));
  const maxRoad = warnings.find((w) => w.speed_limit === maxSpeed)?.road_name || '';

  return (
    <div className="fallback-banner" role="alert" aria-live="polite">
      <button
        className="fallback-banner-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-label="Route warning details"
      >
        <span className="fallback-icon" aria-hidden="true">&#9888;</span>
        <span className="fallback-text">
          This route includes {totalMiles.toFixed(1)} mi on roads above 35 MPH
          (max: {maxSpeed} MPH on {maxRoad}).
        </span>
        <span className="fallback-chevron" aria-hidden="true">{expanded ? '\u25B2' : '\u25BC'}</span>
      </button>

      {expanded && (
        <ul className="fallback-details" aria-label="Non-compliant road segments">
          {warnings.map((w, i) => (
            <li key={i}>
              <strong>{w.road_name}</strong>: {w.speed_limit} MPH, {w.distance_miles} mi
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
