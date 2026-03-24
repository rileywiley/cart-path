/**
 * CartPath — Coverage Boundary Check
 *
 * Loads the coverage boundary GeoJSON and checks whether destinations
 * fall within CartPath's verified coverage area.
 */

let coveragePolygon = null;

/**
 * Load the coverage boundary GeoJSON from the server.
 * Called once on app startup.
 */
export async function loadCoverageBoundary() {
  try {
    const resp = await fetch('/data/coverage_boundary.geojson');
    if (!resp.ok) return false;
    const data = await resp.json();
    const feature = data.features?.[0];
    if (feature?.geometry?.type === 'Polygon') {
      coveragePolygon = feature.geometry.coordinates[0];
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Check if a point is inside the coverage polygon.
 * Uses ray-casting algorithm.
 *
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {boolean} true if inside coverage area
 */
export function isInsideCoverage(lat, lon) {
  if (!coveragePolygon) return true; // No boundary loaded — allow routing

  const x = lon;
  const y = lat;
  let inside = false;

  for (let i = 0, j = coveragePolygon.length - 1; i < coveragePolygon.length; j = i++) {
    const xi = coveragePolygon[i][0], yi = coveragePolygon[i][1];
    const xj = coveragePolygon[j][0], yj = coveragePolygon[j][1];

    const intersect = ((yi > y) !== (yj > y)) &&
      (x < (xj - xi) * (y - yi) / (yj - yi) + xi);

    if (intersect) inside = !inside;
  }

  return inside;
}

/**
 * Haversine distance between two points in meters.
 */
function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371000; // Earth radius in meters
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Find the nearest point on the coverage boundary to a given point.
 * Uses Haversine formula for geographic accuracy.
 *
 * @param {number} lat
 * @param {number} lon
 * @returns {{ lat: number, lon: number } | null}
 */
export function nearestBoundaryPoint(lat, lon) {
  if (!coveragePolygon) return null;

  let minDist = Infinity;
  let nearest = null;

  for (const [blon, blat] of coveragePolygon) {
    const dist = haversineDistance(lat, lon, blat, blon);
    if (dist < minDist) {
      minDist = dist;
      nearest = { lat: blat, lon: blon };
    }
  }

  return nearest;
}
