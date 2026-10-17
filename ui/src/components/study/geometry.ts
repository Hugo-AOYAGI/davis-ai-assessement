import type { Point, Polygon } from "@/lib/study-types";

/**
 * Planar helpers for EPSG:2154 (Lambert-93) geometry. Views work in "local"
 * metres: the site centroid subtracted, x east, y north.
 */

/** Signed shoelace area of a closed ring; positive when counter-clockwise. */
export function signedArea(ring: Point[]): number {
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[i + 1];
    sum += x0 * y1 - x1 * y0;
  }
  return sum / 2;
}

/** Unsigned area of a polygon, holes removed. */
export function polygonArea(polygon: Polygon): number {
  const holes = polygon.holes.reduce((s, h) => s + Math.abs(signedArea(h)), 0);
  return Math.abs(signedArea(polygon.exterior)) - holes;
}

/** Area centroid of a closed ring (vertex mean if degenerate). */
export function centroid(ring: Point[]): Point {
  const area = signedArea(ring);
  if (Math.abs(area) < 1e-9) {
    const n = Math.max(ring.length - 1, 1);
    const sx = ring.slice(0, n).reduce((s, p) => s + p[0], 0);
    const sy = ring.slice(0, n).reduce((s, p) => s + p[1], 0);
    return [sx / n, sy / n];
  }
  // Shift to the first vertex to keep precision with large Lambert values.
  const [ox, oy] = ring[0];
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const x0 = ring[i][0] - ox;
    const y0 = ring[i][1] - oy;
    const x1 = ring[i + 1][0] - ox;
    const y1 = ring[i + 1][1] - oy;
    const cross = x0 * y1 - x1 * y0;
    cx += (x0 + x1) * cross;
    cy += (y0 + y1) * cross;
  }
  return [ox + cx / (6 * area), oy + cy / (6 * area)];
}

export const toLocal = (p: Point, origin: Point): Point => [
  p[0] - origin[0],
  p[1] - origin[1],
];

export function ringToLocal(ring: Point[], origin: Point): Point[] {
  return ring.map((p) => toLocal(p, origin));
}

export function polygonToLocal(polygon: Polygon, origin: Point): Polygon {
  return {
    ...polygon,
    exterior: ringToLocal(polygon.exterior, origin),
    holes: polygon.holes.map((h) => ringToLocal(h, origin)),
  };
}

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export function bounds(points: Point[]): Bounds {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of points) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return { minX, minY, maxX, maxY };
}

export const distance = (a: Point, b: Point) =>
  Math.hypot(b[0] - a[0], b[1] - a[1]);

/** Even-odd point-in-ring test. */
export function pointInRing([x, y]: Point, ring: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** Unit normal of edge `a → b` pointing away from the ring's interior. */
export function outwardNormal(a: Point, b: Point, ring: Point[]): Point {
  const length = distance(a, b) || 1;
  const n: Point = [(b[1] - a[1]) / length, -(b[0] - a[0]) / length];
  const mid: Point = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const probe: Point = [mid[0] + n[0] * 0.01, mid[1] + n[1] * 0.01];
  return pointInRing(probe, ring) ? [-n[0], -n[1]] : n;
}

/** Largest "nice" length (1, 2 or 5 × 10ⁿ) not above `max`. */
export function niceLength(max: number): number {
  const exponent = Math.floor(Math.log10(max));
  const base = 10 ** exponent;
  for (const step of [5, 2, 1]) {
    if (step * base <= max) return step * base;
  }
  return base;
}
