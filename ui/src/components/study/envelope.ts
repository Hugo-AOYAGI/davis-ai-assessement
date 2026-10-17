import type { Envelope, EnvelopeParameters } from "@/lib/study-types";

/** What limits the buildable area below the setback footprint, if anything. */
export type FootprintCap = "footprint ratio" | "minimum green space" | null;

/**
 * The envelope's `footprint` polygon is the site minus setbacks; when the
 * footprint ratio or the green space minimum binds, only
 * `max_footprint_area_m2` is reduced, the polygon is not.
 */
export function footprintCap(
  envelope: Envelope,
  params: EnvelopeParameters,
): FootprintCap {
  const capped = envelope.max_footprint_area_m2;
  if (capped >= envelope.footprint_area_m2 - 0.5) return null;
  const ratio = params.max_footprint_ratio.value;
  const byRatio = ratio === null ? Infinity : ratio * envelope.site_area_m2;
  const byGreen =
    envelope.min_green_area_m2 === null
      ? Infinity
      : envelope.site_area_m2 - envelope.min_green_area_m2;
  return Math.abs(byRatio - capped) <= Math.abs(byGreen - capped)
    ? "footprint ratio"
    : "minimum green space";
}

/** Storey height used to draw floor lines: height / storeys, else 3 m. */
export function storeyHeight(
  maxHeight: number,
  maxStoreys: number | null,
): number {
  return maxStoreys && maxStoreys > 0 ? maxHeight / maxStoreys : 3;
}
