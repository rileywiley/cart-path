import React, { useState, useEffect, useCallback, useRef } from 'react';
import Map from './components/Map';
import SearchBar from './components/SearchBar';
import RoutePanel from './components/RoutePanel';
import FallbackBanner from './components/FallbackBanner';
import SavedRoutes from './components/SavedRoutes';
import Onboarding from './components/Onboarding';
import ErrorStates from './components/ErrorStates';
import AuthModal from './components/AuthModal';
import AccountMenu from './components/AccountMenu';
import About from './components/About';
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
  const [showAbout, setShowAbout] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const routeStartedRef = useRef(false);
  const routeEndCoordsRef = useRef(null);

  useEffect(() => {
    trackEvent('app_opened');
    loadCoverageBoundary();

    // Use watchPosition for continuous location tracking
    let watchId = null;
    if (navigator.geolocation) {
      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          setUserLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        },
        () => { /* permission denied or unavailable — leave userLocation null */ },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
      );
    }
    return () => {
      if (watchId != null) navigator.geolocation.clearWatch(watchId);
    };
  }, []);

  // Track route_completed when user is within 100m of destination
  useEffect(() => {
    if (!routeStartedRef.current || !userLocation || !routeEndCoordsRef.current) return;
    const end = routeEndCoordsRef.current;
    const R = 6371000;
    const toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(end.lat - userLocation.lat);
    const dLon = toRad(end.lon - userLocation.lon);
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(userLocation.lat)) * Math.cos(toRad(end.lat)) * Math.sin(dLon / 2) ** 2;
    const dist = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    if (dist < 100) {
      trackEvent('route_completed', { route_id: route?.route_id });
      routeStartedRef.current = false;
      routeEndCoordsRef.current = null;
      setNavigating(false);
    }
  }, [userLocation, route]);

  const handleOnboardingComplete = useCallback((location) => {
    localStorage.setItem('cartpath_onboarding', 'done');
    setOnboardingComplete(true);
    if (location) {
      setUserLocation(location);
    }
  }, []);

  const handleRouteRequest = useCallback(async (start, end) => {
    // Track multi_stop_requested if user searches while a route is active
    if (route) {
      trackEvent('multi_stop_requested', {
        current_route_id: route.route_id,
        new_end_lat: end.lat,
        new_end_lon: end.lon,
      });
    }

    setLoading(true);
    setError(null);
    setRoute(null);
    setAlternatives([]);
    setSelectedAltIndex(0);
    setLastStartCoords(start);
    routeEndCoordsRef.current = end;

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
    const vehicleType = user?.vehicle_type || 'lsv';

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
    // If route was started and user dismisses, check for partial completion
    if (routeStartedRef.current && route) {
      trackEvent('route_completed', { route_id: route.route_id, reason: 'dismissed' });
      routeStartedRef.current = false;
      routeEndCoordsRef.current = null;
    }
    setRoute(null);
    setAlternatives([]);
    setSelectedAltIndex(0);
    setError(null);
    setNavigating(false);
  }, [route]);

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
        navigating={navigating}
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
              navigating={navigating}
              onStartRoute={() => { routeStartedRef.current = true; setNavigating(true); }}
              onStopNavigation={() => {
                if (route) trackEvent('route_completed', { route_id: route.route_id, reason: 'stopped' });
                routeStartedRef.current = false;
                routeEndCoordsRef.current = null;
                setNavigating(false);
              }}
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

        {showAbout && (
          <About onClose={() => setShowAbout(false)} />
        )}

        <button
          className="btn-about-toggle"
          onClick={() => setShowAbout(!showAbout)}
          aria-label="About CartPath"
        >
          &#9432;
        </button>
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
