import React from 'react';

export default function SavedRoutes({ onSelect, onClose }) {
  const saved = JSON.parse(localStorage.getItem('cartpath_saved_routes') || '[]');

  const handleDelete = (index) => {
    const updated = saved.filter((_, i) => i !== index);
    localStorage.setItem('cartpath_saved_routes', JSON.stringify(updated));
    // Force re-render by triggering parent
    onClose();
  };

  return (
    <div className="saved-routes-panel" role="dialog" aria-label="Saved routes">
      <div className="saved-routes-header">
        <h2>Saved Routes</h2>
        <button className="btn-dismiss" onClick={onClose} aria-label="Close saved routes">
          Close
        </button>
      </div>

      {saved.length === 0 ? (
        <p className="saved-routes-empty">
          No saved routes yet. Search for a destination and tap "Save" to add one.
        </p>
      ) : (
        <ul className="saved-routes-list" role="list">
          {saved.map((route, i) => (
            <li key={i} className="saved-route-item">
              <button
                className="saved-route-button"
                onClick={() => onSelect(route)}
                aria-label={`Navigate: ${route.label}`}
              >
                <span className="saved-route-label">{route.label}</span>
                <span className="saved-route-summary">
                  {route.distance_miles} mi · ~{route.duration_minutes} min
                </span>
              </button>
              <button
                className="btn-dismiss btn-small"
                onClick={() => handleDelete(i)}
                aria-label={`Delete ${route.label}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
