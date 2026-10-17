/**
 * TypeScript mirror of the agent's `VerifiedStudy` contract
 * (`src/agent/contracts/study.py` and the modules it imports).
 *
 * Polygons and points are EPSG:2154 (Lambert-93) metres; only
 * `Site.longitude` / `Site.latitude` are WGS84. Python tuples are arrays.
 */

/** `(x, y)` in a projected CRS, metres. */
export type Point = [number, number];

/** `[x0, y0, x1, y1]`, end-exclusive pixel box. */
export type PixelBounds = [number, number, number, number];

// --- evidence.py -----------------------------------------------------------

export type SourceKind = "regulatory" | "geometric";

export interface Citation {
  /** Corpus document id, or data source name for geometric sources. */
  doc: string;
  /** 1-based PDF page index; required for regulatory sources. */
  page: number | null;
  /** Article or section reference, e.g. `UMG 10`. */
  article: string | null;
  /** Verbatim excerpt. */
  quote: string;
  source_kind: SourceKind;
}

export interface CitationCheck {
  citation: Citation;
  verified: boolean;
  /** Best similarity in [0, 1]. */
  score: number;
  /** Page holding the best match, when it differs from the cited page. */
  matched_page: number | null;
  /** False for raster documents (no text layer): not checked. */
  text_verifiable: boolean;
}

export interface Rule {
  topic: string;
  text: string;
  citations: Citation[];
}

/** A numeric limit; the unit is given by the field holding it. */
export interface Limit {
  /** `null` when the documents set no such limit. */
  value: number | null;
  rule: string;
  citations: Citation[];
}

export type Resolution = "user" | "agent";

export interface Ambiguity {
  question: string;
  options: string[];
  chosen: string;
  rationale: string;
  resolved_by: Resolution;
  citations: Citation[];
}

export interface ImageRegion {
  doc: string;
  page: number;
  /** Overview-image pixel box. */
  region: PixelBounds;
}

export interface StoredCrop {
  region: ImageRegion;
  /** Full-resolution page-image pixel box. */
  pixels: PixelBounds;
  /** PNG, POSIX path relative to the project root (e.g. `data/crops/x.png`). */
  path: string;
}

// --- geometry.py -----------------------------------------------------------

export interface Polygon {
  /** e.g. `EPSG:2154`. */
  crs: string;
  /** Closed ring: first and last points are equal. */
  exterior: Point[];
  holes: Point[][];
}

export type BoundaryKind = "road" | "side" | "rear";

export interface Boundary {
  kind: BoundaryKind;
  start: Point;
  end: Point;
}

/** Distances in metres, ratios in [0, 1]. */
export interface EnvelopeParameters {
  setback_road_m: Limit;
  setback_side_m: Limit;
  setback_rear_m: Limit;
  max_height_m: Limit;
  /** Storeys above ground, ground floor included (R+5 = 6). */
  max_storeys: Limit;
  max_footprint_ratio: Limit;
  min_green_ratio: Limit;
}

export interface Envelope {
  site_area_m2: number;
  /** Site polygon minus setbacks; `null` when nothing remains. */
  footprint: Polygon | null;
  footprint_area_m2: number;
  /**
   * Smallest of the footprint area, the footprint ratio applied to the site
   * area and the site area minus the green area. `footprint` is not shrunk
   * to it: only the area is capped.
   */
  max_footprint_area_m2: number;
  min_green_area_m2: number | null;
  max_height_m: number | null;
  /** `max_footprint_area_m2 * max_height_m`; `null` without a height limit. */
  max_volume_m3: number | null;
  assumptions: string[];
}

// --- findings/site.py ------------------------------------------------------

export interface ParcelChoice {
  address: string;
  parcel_ids: string[];
  rationale: string;
  assumptions: string[];
}

export type EdgeSide = "parcel" | "public_land";

export interface Edge {
  start: Point;
  end: Point;
  length_m: number;
  other_side: EdgeSide;
  neighbours: string[];
}

export interface Parcel {
  id: string;
  area_m2: number;
  polygon: Polygon;
}

export interface Site {
  address: string;
  /** WGS84. */
  longitude: number;
  /** WGS84. */
  latitude: number;
  choice: ParcelChoice;
  parcels: Parcel[];
  /** Union of the parcels. */
  polygon: Polygon;
  area_m2: number;
  edges: Edge[];
  citations: Citation[];
}

// --- findings/zone.py ------------------------------------------------------

export interface LegendItem {
  item: string;
  applies: boolean;
  note: string;
}

export interface ZoneFindings {
  zone: string;
  overlays: LegendItem[];
  rationale: string;
  region: ImageRegion;
  ambiguities: Ambiguity[];
}

// --- study.py --------------------------------------------------------------

export type Verdict = "permitted" | "conditional" | "restricted" | "prohibited";

export interface Admissibility {
  building: string;
  stated_use: string;
  destination: string;
  verdict: Verdict;
  conditions: string[];
  citations: Citation[];
}

export type ParkingBasis = "floor_area_m2" | "unit" | "other";

/** `spaces` per `per` of `basis`. */
export interface ParkingRule {
  use: string;
  spaces: number;
  per: number;
  basis: ParkingBasis;
  rule: string;
  citations: Citation[];
}

export interface Regime {
  zone: string;
  overlays: LegendItem[];
  oap_applicable: boolean;
  oap_prescriptions: Rule[];
  citations: Citation[];
}

export interface Study {
  address: string;
  program: string;
  regime: Regime;
  admissibility: Admissibility[];
  envelope: EnvelopeParameters;
  parking: ParkingRule[];
  conditions: Rule[];
  ambiguities: Ambiguity[];
  /** Markdown. */
  summary: string;
}

export interface VerifiedStudy {
  study: Study;
  site: Site;
  boundaries: Boundary[];
  zone: ZoneFindings;
  envelope: Envelope;
  /** One per distinct regulatory citation in `study`. */
  citation_checks: CitationCheck[];
  evidence: StoredCrop[];
}
