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
 * Find the nearest point on the coverage boundary to a given point.
 * Used when offering "route to nearest boundary point".
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
    const dist = Math.sqrt((lat - blat) ** 2 + (lon - blon) ** 2);
    if (dist < minDist) {
      minDist = dist;
      nearest = { lat: blat, lon: blon };
    }
  }

  return nearest;
}
