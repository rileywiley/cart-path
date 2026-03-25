import React from 'react';
import { trackEvent } from '../utils/analytics';

const ERROR_MESSAGES = {
  no_route: {
    title: 'No route found',
    message: "We couldn't find any route between these locations. Please check the addresses and try again.",
    icon: '\uD83D\uDDFA\uFE0F',
  },
  gps_unavailable: {
    title: 'GPS unavailable',
    message: 'Enter your starting address to get a route.',
    icon: '\uD83D\uDCCD',
  },
  permission_denied: {
    title: 'Location access needed',
    message: 'Allow location access for one-tap routing, or enter your starting address manually.',
    icon: '\uD83D\uDD13',
    action: 'Enable location',
  },
  api_down: {
    title: 'Temporarily unavailable',
    message: 'CartPath is temporarily unavailable. Please try again in a few minutes.',
    icon: '\u26A0\uFE0F',
  },
  outside_coverage: {
    title: 'Outside coverage area',
    message: "This destination is outside CartPath's verified coverage area.",
    icon: '\uD83C\uDF0D',
  },
};

export default function ErrorStates({ error, onDismiss }) {
  if (!error) return null;

  const config = ERROR_MESSAGES[error.type] || ERROR_MESSAGES.api_down;
  const message = error.message || config.message;

  const handleAction = () => {
    if (error.type === 'permission_denied') {
      // Re-prompt location permission
      navigator.geolocation.getCurrentPosition(
        () => { onDismiss(); },
        () => {},
        { enableHighAccuracy: true }
      );
    }
  };

  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      <div className="error-content">
        <span className="error-icon" aria-hidden="true">{config.icon}</span>
        <div>
          <strong className="error-title">{config.title}</strong>
          <p className="error-message">{message}</p>
        </div>
      </div>
      <div className="error-actions">
        {config.action && (
          <button className="btn-secondary" onClick={handleAction}>
            {config.action}
          </button>
        )}
        <button className="btn-dismiss" onClick={onDismiss} aria-label="Dismiss">
          Dismiss
        </button>
      </div>
    </div>
  );
}
