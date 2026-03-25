import React, { useState, useEffect, useCallback } from 'react';
import Map from './components/Map';
import SearchBar from './components/SearchBar';
import RoutePanel from './components/RoutePanel';
import FallbackBanner from './components/FallbackBanner';
import SavedRoutes from './components/SavedRoutes';
import Onboarding from './components/Onboarding';
import ErrorStates from './components/ErrorStates';
import AuthModal from './components/AuthModal';
import AccountMenu from './components/AccountMenu';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { trackEvent } from './utils/analytics';
import { apiFetch } from './utils/api';
import { loadCoverageBoundary, isInsideCoverage, nearestBoundaryPoint } from './utils/boundary';

const CENTER = { lat: 28.5641, lon: -81.3089 };

function AppContent() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const [onboardingComplete, setOnboardingComplete] = useState(
    () => localStorage.getItem('cartpath_onboarding') === 'done'
  );
  const [userLocation, setUserLocation] = useState(null);
  const [route, setRoute] = useState(null);
  const [alternatives, setAlternatives] = useState([]);
  const [selectedAltIndex, setSelectedAltIndex] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showSaved, setShowSaved] = useState(false);
  const [lastStartCoords, setLastStartCoords] = useState(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showAccountMenu, setShowAccountMenu] = useState(false);

  useEffect(() => {
    trackEvent('app_opened');
    loadCoverageBoundary();

    // Request geolocation on mount (covers return visits after onboarding)
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        },
        () => { /* permission denied or unavailable — leave userLocation null */ },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    }
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
    setAlternatives([]);
    setSelectedAltIndex(0);
    setLastStartCoords(start);

    // Check if destination is inside coverage area
    if (!isInsideCoverage(end.lat, end.lon)) {
      trackEvent('destination_outside_area', { lat: end.lat, lon: end.lon });
      const nearest = nearestBoundaryPoint(end.lat, end.lon);
      setError({
        type: 'outside_coverage',
        message: "This destination is outside CartPath's verified coverage area.",
        nearestPoint: nearest,
      });
      setLoading(false);
      return;
    }

    trackEvent('route_requested', {
      start_lat: start.lat,
      start_lon: start.lon,
      end_lat: end.lat,
      end_lon: end.lon,
    });

    // Include vehicle type in request if user is authenticated
    const vehicleType = user?.vehicle_type || 'golf_cart';

    const retries = 2;
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const resp = await apiFetch('/api/route', {
          method: 'POST',
          body: JSON.stringify({ start, end, vehicle_type: vehicleType }),
          signal: AbortSignal.timeout(10000),
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
        if (data.alternatives && data.alternatives.length > 0) {
          setAlternatives(data.alternatives);
          setSelectedAltIndex(0);
        }
        setLoading(false);
        trackEvent('route_displayed', {
          compliance: data.compliance,
          segment_count: data.segments?.length,
          alternatives_count: data.alternatives?.length || 1,
        });
        return;
      } catch (err) {
        if (attempt === retries) {
          setError({ type: 'api_down' });
          setLoading(false);
        }
      }
    }
  }, [user]);

  const handleClearRoute = useCallback(() => {
    setRoute(null);
    setAlternatives([]);
    setSelectedAltIndex(0);
    setError(null);
  }, []);

  const handleSelectAlternative = useCallback((index) => {
    if (alternatives[index]) {
      setSelectedAltIndex(index);
      setRoute(alternatives[index]);
      trackEvent('route_alternative_selected', {
        label: alternatives[index].label,
        index,
      });
    }
  }, [alternatives]);

  if (!onboardingComplete) {
    return <Onboarding onComplete={handleOnboardingComplete} />;
  }

  return (
    <div className="app">
      <Map
        center={userLocation || CENTER}
        route={route}
        alternatives={alternatives}
        selectedAltIndex={selectedAltIndex}
        userLocation={userLocation}
      />

      <div className="app-overlay">
        <div className="app-top-bar">
          <SearchBar
            userLocation={userLocation}
            onRouteRequest={handleRouteRequest}
            onClear={handleClearRoute}
            loading={loading}
          />
          {!authLoading && (
            <button
              className="btn-auth-toggle"
              onClick={() => isAuthenticated ? setShowAccountMenu(!showAccountMenu) : setShowAuthModal(true)}
              aria-label={isAuthenticated ? 'Account settings' : 'Sign in'}
            >
              {isAuthenticated ? (user.display_name || user.email.split('@')[0]) : 'Sign in'}
            </button>
          )}
        </div>

        {error && (
          <ErrorStates
            error={error}
            onDismiss={() => setError(null)}
            onRouteToBoundary={(point) => {
              setError(null);
              handleRouteRequest(lastStartCoords || userLocation || CENTER, point);
            }}
          />
        )}

        {route && (
          <>
            {route.compliance !== 'full' && (
              <FallbackBanner warnings={route.warnings} />
            )}
            <RoutePanel
              route={route}
              alternatives={alternatives}
              selectedAltIndex={selectedAltIndex}
              onSelectAlternative={handleSelectAlternative}
              onSave={() => setShowSaved(true)}
              userLocation={userLocation}
              startCoords={lastStartCoords}
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

        {showAuthModal && (
          <AuthModal onClose={() => setShowAuthModal(false)} />
        )}

        {showAccountMenu && (
          <AccountMenu onClose={() => setShowAccountMenu(false)} />
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
