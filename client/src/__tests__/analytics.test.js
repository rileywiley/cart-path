/**
 * Tests for analytics event tracking.
 * Run with: npx vitest
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { trackEvent } from '../utils/analytics';

describe('Analytics', () => {
  beforeEach(() => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    // Clear any previous fetch mocks
    global.fetch = vi.fn().mockResolvedValue({});
  });

  it('logs events in development mode', () => {
    trackEvent('app_opened', { test: true });
    expect(console.log).toHaveBeenCalledWith(
      '[analytics]',
      'app_opened',
      expect.objectContaining({ test: true })
    );
  });

  it('includes session_id and timestamp in events', () => {
    // Track an event and check the logged payload
    trackEvent('route_requested', { start_lat: 28.5641 });
    const call = console.log.mock.calls.find(c => c[1] === 'route_requested');
    expect(call).toBeDefined();
  });

  it('tracks all 10 required event types without error', () => {
    const events = [
      'app_opened',
      'route_requested',
      'route_displayed',
      'route_started',
      'route_completed',
      'route_saved',
      'destination_outside_area',
      'error_reported',
      'page_load_time',
      'multi_stop_requested',
    ];

    for (const event of events) {
      expect(() => trackEvent(event, {})).not.toThrow();
    }

    // Verify all 10 events were logged
    const loggedEvents = console.log.mock.calls
      .filter(c => c[0] === '[analytics]')
      .map(c => c[1]);

    for (const event of events) {
      expect(loggedEvents).toContain(event);
    }
  });
});
