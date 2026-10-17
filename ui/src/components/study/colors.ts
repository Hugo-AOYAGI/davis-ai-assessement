import type { BoundaryKind } from "@/lib/study-types";

/**
 * Data colours shared by the 2D plan and the 3D view. Mid lightness so they
 * read on both the light and the dark theme; neutrals come from theme tokens.
 */
export const BOUNDARY_COLORS: Record<BoundaryKind, string> = {
  road: "oklch(0.72 0.17 55)",
  side: "oklch(0.66 0.15 240)",
  rear: "oklch(0.62 0.2 305)",
};

export const BOUNDARY_LABELS: Record<BoundaryKind, string> = {
  road: "Road",
  side: "Side",
  rear: "Rear",
};

export const BOUNDARY_KINDS: BoundaryKind[] = ["road", "side", "rear"];

/** Buildable footprint / volume. */
export const FOOTPRINT_COLOR = "oklch(0.68 0.14 165)";
