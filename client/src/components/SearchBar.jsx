import React, { useState, useRef, useCallback, useEffect } from 'react';

// Stable session token per component mount (Mapbox billing groups suggest+retrieve)
function useSessionToken() {
  const ref = useRef(crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2));
  return ref.current;
}

export default function SearchBar({ userLocation, onRouteRequest, onClear, loading }) {
  const [startText, setStartText] = useState('Current Location');
  const [endText, setEndText] = useState('');
  const [startCoords, setStartCoords] = useState(null);
  const [endCoords, setEndCoords] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [activeField, setActiveField] = useState(null);
  const [validationError, setValidationError] = useState(null);
  const [geocoding, setGeocoding] = useState(false);
  const debounceRef = useRef(null);
  const formRef = useRef(null);
  const sessionToken = useSessionToken();

  // Close suggestions on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (formRef.current && !formRef.current.contains(e.target)) {
        setSuggestions([]);
        setActiveField(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchSuggestions = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setSuggestions([]);
      return;
    }

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        let url = `/api/geocode/suggest?q=${encodeURIComponent(query)}&session_token=${sessionToken}`;
        if (userLocation) {
          url += `&proximity_lat=${userLocation.lat}&proximity_lon=${userLocation.lon}`;
        }
        const resp = await fetch(url);
        if (resp.ok) {
          const data = await resp.json();
          setSuggestions(data.results || []);
        }
      } catch {
        setSuggestions([]);
      }
    }, 300);
  }, [userLocation, sessionToken]);

  // Geocode a text query and return the first result's coords, or null
  const geocodeText = useCallback(async (query) => {
    if (!query || query.length < 2) return null;
    try {
      let url = `/api/geocode?q=${encodeURIComponent(query)}`;
      if (userLocation) {
        url += `&proximity_lat=${userLocation.lat}&proximity_lon=${userLocation.lon}`;
      }
      const resp = await fetch(url);
      if (!resp.ok) return null;
      const data = await resp.json();
      const results = data.results || [];
      if (results.length > 0) {
        return { lat: results[0].lat, lon: results[0].lon, place_name: results[0].place_name };
      }
    } catch {
      // fall through
    }
    return null;
  }, [userLocation]);

  const handleUseCurrentLocation = () => {
    setStartText('Current Location');
    setStartCoords(null);
    setSuggestions([]);
    setActiveField(null);
    setValidationError(null);
  };

  const handleStartChange = (e) => {
    const val = e.target.value;
    setStartText(val);
    setStartCoords(null);
    setActiveField('start');
    setValidationError(null);
    if (val !== 'Current Location') {
      fetchSuggestions(val);
    } else {
      setSuggestions([]);
    }
  };

  const handleEndChange = (e) => {
    setEndText(e.target.value);
    setEndCoords(null);
    setActiveField('end');
    setValidationError(null);
    fetchSuggestions(e.target.value);
  };

  const handleSelectSuggestion = async (suggestion) => {
    const field = activeField; // capture before clearing
    const displayName = suggestion.place_name || suggestion.name;
    // Immediately show the selected name and close dropdown
    if (field === 'start') {
      setStartText(displayName);
    } else {
      setEndText(displayName);
    }
    setSuggestions([]);
    setActiveField(null);
    setValidationError(null);

    // Retrieve full coordinates from Mapbox Search Box API
    if (suggestion.mapbox_id) {
      try {
        const resp = await fetch(
          `/api/geocode/retrieve?id=${encodeURIComponent(suggestion.mapbox_id)}&session_token=${sessionToken}`
        );
        if (resp.ok) {
          const data = await resp.json();
          const coords = { lat: data.lat, lon: data.lon };
          if (field === 'start') {
            setStartCoords(coords);
            setStartText(data.place_name || displayName);
          } else {
            setEndCoords(coords);
            setEndText(data.place_name || displayName);
          }
          return;
        }
      } catch {
        // Fall through to legacy coords if available
      }
    }

    // Fallback: use coords directly if present (legacy /geocode response)
    if (suggestion.lat && suggestion.lon) {
      const coords = { lat: suggestion.lat, lon: suggestion.lon };
      if (field === 'start') {
        setStartCoords(coords);
      } else {
        setEndCoords(coords);
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError(null);
    setSuggestions([]);

    // Resolve start coordinates
    let start = null;
    if (startText === 'Current Location' && userLocation) {
      start = userLocation;
    } else if (startCoords) {
      start = startCoords;
    } else if (startText && startText !== 'Current Location') {
      // Auto-geocode the typed start text
      setGeocoding(true);
      const result = await geocodeText(startText);
      setGeocoding(false);
      if (result) {
        start = { lat: result.lat, lon: result.lon };
        setStartCoords(start);
        setStartText(result.place_name);
      }
    }

    // Resolve end coordinates
    let end = endCoords;
    if (!end && endText) {
      // Auto-geocode the typed destination text
      setGeocoding(true);
      const result = await geocodeText(endText);
      setGeocoding(false);
      if (result) {
        end = { lat: result.lat, lon: result.lon };
        setEndCoords(end);
        setEndText(result.place_name);
      }
    }

    // Validate
    if (!start && !end) {
      setValidationError('Enter a starting point and destination.');
      return;
    }
    if (!start) {
      setValidationError(
        startText === 'Current Location'
          ? 'Location unavailable. Enter a starting address.'
          : 'Could not find that starting location. Select from suggestions.'
      );
      return;
    }
    if (!end) {
      setValidationError(
        endText
          ? 'Could not find that destination. Try a different search.'
          : 'Enter a destination.'
      );
      return;
    }

    onRouteRequest(start, end);
    setActiveField(null);
  };

  const handleClear = () => {
    setEndText('');
    setEndCoords(null);
    setStartText('Current Location');
    setStartCoords(null);
    setSuggestions([]);
    setValidationError(null);
    onClear();
  };

  const isSubmitting = loading || geocoding;

  return (
    <form className="search-bar" onSubmit={handleSubmit} role="search" aria-label="Route search" ref={formRef}>
      <div className="search-fields">
        <div className="search-field">
          <label htmlFor="start-input" className="sr-only">Starting point</label>
          <input
            id="start-input"
            type="text"
            value={startText}
            onChange={handleStartChange}
            onFocus={() => { setActiveField('start'); setValidationError(null); }}
            placeholder="Start location"
            aria-label="Starting point"
            autoComplete="off"
          />
        </div>
        <div className="search-field">
          <label htmlFor="end-input" className="sr-only">Destination</label>
          <input
            id="end-input"
            type="text"
            value={endText}
            onChange={handleEndChange}
            onFocus={() => { setActiveField('end'); setValidationError(null); }}
            placeholder="Where to?"
            aria-label="Destination"
            autoComplete="off"
          />
        </div>
      </div>

      {validationError && (
        <p className="search-validation-error" role="alert">{validationError}</p>
      )}

      <div className="search-actions">
        <button type="submit" disabled={isSubmitting} className="btn-primary btn-go" aria-label="Get route">
          {isSubmitting ? 'Finding...' : 'Go'}
        </button>
        {(endText || startText !== 'Current Location') && (
          <button type="button" onClick={handleClear} className="btn-secondary" aria-label="Clear route">
            Clear
          </button>
        )}
      </div>

      {activeField && (suggestions.length > 0 || (activeField === 'start' && startText !== 'Current Location' && userLocation)) && (
        <ul className="suggestions" role="listbox" aria-label="Address suggestions">
          {activeField === 'start' && startText !== 'Current Location' && userLocation && (
            <li role="option" className="suggestion-current-location" onClick={handleUseCurrentLocation}>
              <span className="suggestion-name">Current Location</span>
              <span className="suggestion-detail">Use your GPS location</span>
            </li>
          )}
          {suggestions.map((s, i) => (
            <li key={s.place_name || i} role="option" onClick={() => handleSelectSuggestion(s)}>
              <span className="suggestion-name">{s.name}</span>
              <span className="suggestion-detail">{s.place_name}</span>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
