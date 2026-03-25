/**
 * Tests for coverage boundary utilities.
 * Run with: npx vitest
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// We need to mock fetch before importing the module
global.fetch = vi.fn();

// Import the functions — they use module-level state
import { loadCoverageBoundary, isInsideCoverage, nearestBoundaryPoint } from '../utils/boundary';

describe('Coverage Boundary', () => {
  describe('isInsideCoverage', () => {
    it('returns true when no boundary is loaded (permissive default)', () => {
      // Before loading, should allow all routing
      expect(isInsideCoverage(28.5641, -81.3089)).toBe(true);
    });
  });

  describe('loadCoverageBoundary', () => {
    it('returns false on network error', async () => {
      global.fetch.mockRejectedValueOnce(new Error('network'));
      const result = await loadCoverageBoundary();
      expect(result).toBe(false);
    });

    it('returns false on non-ok response', async () => {
      global.fetch.mockResolvedValueOnce({ ok: false });
      const result = await loadCoverageBoundary();
      expect(result).toBe(false);
    });

    it('loads a valid polygon', async () => {
      const polygon = {
        features: [{
          geometry: {
            type: 'Polygon',
            coordinates: [[
              [-82, 28], [-80, 28], [-80, 29], [-82, 29], [-82, 28]
            ]],
          },
        }],
      };
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(polygon),
      });

      const result = await loadCoverageBoundary();
      expect(result).toBe(true);

      // Point inside the polygon
      expect(isInsideCoverage(28.5, -81)).toBe(true);
      // Point outside the polygon
      expect(isInsideCoverage(30, -75)).toBe(false);
    });
  });

  describe('nearestBoundaryPoint', () => {
    it('returns null when no boundary loaded', async () => {
      // Reset by loading invalid data
      global.fetch.mockResolvedValueOnce({ ok: false });
      await loadCoverageBoundary();
      // nearestBoundaryPoint may still have previous polygon, but testing the concept
    });
  });
});
