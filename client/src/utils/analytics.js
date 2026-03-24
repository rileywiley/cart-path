/**
 * CartPath — Analytics Module
 *
 * Instruments 10 events per the PRD Analytics Event Taxonomy.
 * Uses anonymous session IDs (no PII). Sends to Plausible or custom endpoint.
 *
 * Events: app_opened, route_requested, route_displayed, route_started,
 *         route_completed, route_saved, destination_outside_area,
 *         error_reported, page_load_time, multi_stop_requested
 */

const ANALYTICS_ENDPOINT = import.meta.env.VITE_ANALYTICS_ENDPOINT || '';
const PLAUSIBLE_DOMAIN = import.meta.env.VITE_PLAUSIBLE_DOMAIN || '';

function getSessionId() {
  let id = localStorage.getItem('cartpath_session_id');
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    localStorage.setItem('cartpath_session_id', id);
  }
  return id;
}

/**
 * Track an analytics event.
 * @param {string} eventName - One of the 10 defined event types
 * @param {object} payload - Optional event-specific data
 */
export function trackEvent(eventName, payload = {}) {
  const event = {
    event: eventName,
    session_id: getSessionId(),
    timestamp: new Date().toISOString(),
    ...payload,
  };

  // Send to Plausible (if configured)
  if (PLAUSIBLE_DOMAIN && window.plausible) {
    window.plausible(eventName, { props: payload });
  }

  // Send to custom analytics endpoint (if configured)
  if (ANALYTICS_ENDPOINT) {
    fetch(ANALYTICS_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
      keepalive: true,
    }).catch(() => {});
  }

  // Always log in development
  if (import.meta.env.DEV) {
    console.log('[analytics]', eventName, payload);
  }
}

/**
 * Track page load performance via Web Vitals.
 * Called automatically after the page loads.
 */
export function trackPageLoad() {
  if (typeof window === 'undefined') return;

  window.addEventListener('load', () => {
    setTimeout(() => {
      const navigation = performance.getEntriesByType('navigation')[0];
      if (navigation) {
        trackEvent('page_load_time', {
          lcp: Math.round(navigation.loadEventEnd - navigation.startTime),
          dom_interactive: Math.round(navigation.domInteractive - navigation.startTime),
        });
      }
    }, 0);
  });
}

// Auto-track page load
trackPageLoad();
