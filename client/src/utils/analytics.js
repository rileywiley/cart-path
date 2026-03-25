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

let _userId = null;

/** Link analytics to an authenticated user (call with null to unlink). */
export function setAnalyticsUserId(userId) {
  _userId = userId;
}

function getSessionId() {
  if (_userId) return _userId;
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
 * Measures LCP, FID, and CLS per PRD Analytics Event Taxonomy.
 */
export function trackPageLoad() {
  if (typeof window === 'undefined' || typeof PerformanceObserver === 'undefined') return;

  const vitals = {};

  function reportVitals() {
    if (vitals.lcp !== undefined) {
      trackEvent('page_load_time', vitals);
    }
  }

  try {
    // LCP (Largest Contentful Paint)
    new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const lcpEntry = entries[entries.length - 1];
      if (lcpEntry) {
        vitals.lcp = Math.round(lcpEntry.startTime);
        reportVitals();
      }
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch { /* not supported */ }

  try {
    // FID (First Input Delay)
    new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      if (entries.length > 0) {
        vitals.fid = Math.round(entries[0].processingStart - entries[0].startTime);
        reportVitals();
      }
    }).observe({ type: 'first-input', buffered: true });
  } catch { /* not supported */ }

  try {
    // CLS (Cumulative Layout Shift)
    let clsValue = 0;
    new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value;
        }
      }
      vitals.cls = Math.round(clsValue * 1000) / 1000;
      reportVitals();
    }).observe({ type: 'layout-shift', buffered: true });
  } catch { /* not supported */ }
}

// Auto-track page load
trackPageLoad();
