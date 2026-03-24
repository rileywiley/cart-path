import React, { useState, useEffect, useCallback } from 'react';
import Map from './components/Map';
import SearchBar from './components/SearchBar';
import RoutePanel from './components/RoutePanel';
import FallbackBanner from './components/FallbackBanner';
import SavedRoutes from './components/SavedRoutes';
import Onboarding from './components/Onboarding';
import ErrorStates from './components/ErrorStates';
import { trackEvent } from './utils/analytics';

const CENTER = { lat: 28.5641, lon: -81.3089 };

export default function App() {
  const [onboardingComplete, setOnboardingComplete] = useState(
    () => localStorage.getItem('cartpath_onboarding') === 'done'
  );
  const [userLocation, setUserLocation] = useState(null);
  const [route, setRoute] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showSaved, setShowSaved] = useState(false);

  useEffect(() => {
    trackEvent('app_opened');
  }, []);

  const handleOnboardingComplete = useCallback((location) => {
    localStorage.setItem('cartpath_onboarding', 'done');
    setOnboardingComplete(true);
    if (location) {
      setUserLocation(location);
    }
  }, []);

  const handleRouteRequest = useCallback(async (start, end) => {
    setLoading(true);
    setError(null);
    setRoute(null);

    trackEvent('route_requested', {
      start_lat: start.lat,
      start_lon: start.lon,
      end_lat: end.lat,
      end_lon: end.lon,
    });

    const retries = 2;
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const resp = await fetch('/api/route', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ start, end }),
          signal: AbortSignal.timeout(3000),
        });

        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          if (resp.status === 404) {
            setError({ type: 'no_route', message: data.detail });
            setLoading(false);
            return;
          }
          throw new Error(data.detail || `Server error ${resp.status}`);
        }

        const data = await resp.json();
        setRoute(data);
        setLoading(false);
        trackEvent('route_displayed', {
          compliance: data.compliance,
          segment_count: data.segments?.length,
        });
        return;
      } catch (err) {
        if (attempt === retries) {
          setError({ type: 'api_down' });
          setLoading(false);
        }
      }
    }
  }, []);

  const handleClearRoute = useCallback(() => {
    setRoute(null);
    setError(null);
  }, []);

  if (!onboardingComplete) {
    return <Onboarding onComplete={handleOnboardingComplete} />;
  }

  return (
    <div className="app">
      <Map
        center={userLocation || CENTER}
        route={route}
        userLocation={userLocation}
      />

      <div className="app-overlay">
        <SearchBar
          userLocation={userLocation}
          onRouteRequest={handleRouteRequest}
          onClear={handleClearRoute}
          loading={loading}
        />

        {error && <ErrorStates error={error} onDismiss={() => setError(null)} />}

        {route && (
          <>
            {route.compliance !== 'full' && (
              <FallbackBanner warnings={route.warnings} />
            )}
            <RoutePanel
              route={route}
              onSave={() => setShowSaved(true)}
              userLocation={userLocation}
            />
          </>
        )}

        {!route && !error && (
          <button
            className="saved-routes-toggle"
            onClick={() => setShowSaved(!showSaved)}
            aria-label="Saved routes"
          >
            Saved Routes
          </button>
        )}

        {showSaved && (
          <SavedRoutes
            onSelect={(saved) => {
              setShowSaved(false);
              handleRouteRequest(saved.start, saved.end);
            }}
            onClose={() => setShowSaved(false)}
          />
        )}
      </div>
    </div>
  );
}
