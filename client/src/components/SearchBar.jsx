import React, { useState, useRef, useCallback } from 'react';

export default function SearchBar({ userLocation, onRouteRequest, onClear, loading }) {
  const [startText, setStartText] = useState('Current Location');
  const [endText, setEndText] = useState('');
  const [startCoords, setStartCoords] = useState(null);
  const [endCoords, setEndCoords] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [activeField, setActiveField] = useState(null);
  const debounceRef = useRef(null);

  const fetchSuggestions = useCallback(async (query) => {
    if (!query || query.length < 3) {
      setSuggestions([]);
      return;
    }

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
        if (resp.ok) {
          const data = await resp.json();
          setSuggestions(data.results || []);
        }
      } catch {
        setSuggestions([]);
      }
    }, 300);
  }, []);

  const handleStartChange = (e) => {
    const val = e.target.value;
    setStartText(val);
    setStartCoords(null);
    setActiveField('start');
    if (val !== 'Current Location') {
      fetchSuggestions(val);
    }
  };

  const handleEndChange = (e) => {
    setEndText(e.target.value);
    setEndCoords(null);
    setActiveField('end');
    fetchSuggestions(e.target.value);
  };

  const handleSelectSuggestion = (suggestion) => {
    const coords = { lat: suggestion.lat, lon: suggestion.lon };
    if (activeField === 'start') {
      setStartText(suggestion.place_name);
      setStartCoords(coords);
    } else {
      setEndText(suggestion.place_name);
      setEndCoords(coords);
    }
    setSuggestions([]);
    setActiveField(null);
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const start = startText === 'Current Location' && userLocation
      ? userLocation
      : startCoords;

    const end = endCoords;

    if (!start || !end) return;

    onRouteRequest(start, end);
    setSuggestions([]);
    setActiveField(null);
  };

  const handleClear = () => {
    setEndText('');
    setEndCoords(null);
    setSuggestions([]);
    onClear();
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit} role="search" aria-label="Route search">
      <div className="search-fields">
        <div className="search-field">
          <label htmlFor="start-input" className="sr-only">Starting point</label>
          <input
            id="start-input"
            type="text"
            value={startText}
            onChange={handleStartChange}
            onFocus={() => setActiveField('start')}
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
            onFocus={() => setActiveField('end')}
            placeholder="Where to?"
            aria-label="Destination"
            autoComplete="off"
          />
        </div>
      </div>

      <div className="search-actions">
        <button type="submit" disabled={loading} className="btn-primary" aria-label="Get route">
          {loading ? 'Finding route...' : 'Go'}
        </button>
        {endText && (
          <button type="button" onClick={handleClear} className="btn-secondary" aria-label="Clear route">
            Clear
          </button>
        )}
      </div>

      {suggestions.length > 0 && (
        <ul className="suggestions" role="listbox" aria-label="Address suggestions">
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
