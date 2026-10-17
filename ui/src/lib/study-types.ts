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

// --- envelope.py: what the architect submits -------------------------------

/** `max(min_m, height_ratio × H)`, metres; at least one of the two is set. */
export interface Distance {
  min_m: number | null;
  /** `H/2` → 0.5. */
  height_ratio: number | null;
  rule: string;
  citations: Citation[];
}

/** One per edge kind. */
export interface SetbackRule {
  kind: BoundaryKind;
  /** May build right on the edge. */
  on_limit_allowed: boolean;
  with_windows: Distance | null;
  without_windows: Distance | null;
}

/** One per building of the program. */
export interface BuildingLimits {
  /** Same label as in `Study.admissibility`. */
  building: string;
  max_height_m: Limit;
  /** Storeys above ground, ground floor included (R+5 = 6); reported only. */
  max_storeys: Limit;
}

/** Ratios in [0, 1]. */
export interface EnvelopeRules {
  setbacks: SetbackRule[];
  buildings: BuildingLimits[];
  /** Between buildings on one plot. */
  spacing_with_windows: Distance | null;
  spacing_without_windows: Distance | null;
  max_footprint_ratio: Limit;
  min_green_ratio: Limit;
}

export interface OapChoice {
  /** Cited from `notes.oap`. */
  prescription: Rule;
  how: string;
}

export type LayoutCut = "across_long_axis" | "along_long_axis";

/** The architect's design choices (none dictated by the PLU). */
export interface Layout {
  cut: LayoutCut;
  /** (0, 1): share of the usable area given to the first part. */
  first_share: number;
  /** Building labels, first part (nearer the road) first. */
  order: string[];
  /** A facing facade has windows: `spacing_with_windows` applies. */
  facing_windows: boolean;
  /** Per building in `order`; empty = each building's maximum. */
  heights_m: number[];
  oap: OapChoice[];
  reasons: string;
}

// --- envelope.py: what code computes ----------------------------------------

/** One horizontal slice of a massing. */
export interface Level {
  from_m: number;
  to_m: number;
  area_m2: number;
}

export interface BuildingMassing {
  /** A building label, or several joined when a bound groups a height band. */
  building: string;
  /** Its ground part. */
  footprint: Polygon | null;
  /**
   * May be below the polygon's area when a footprint or green-space cap
   * scales the buildings down: the polygon is not shrunk, only the areas.
   */
  footprint_area_m2: number;
  max_height_m: number;
  /** One slice for a prism, several when setbacks grow with height. */
  levels: Level[];
  volume_m3: number;
}

export type ScenarioName = "largest" | "windows" | "proposal";

export interface Scenario {
  name: ScenarioName | (string & {});
  /** Plot minus setbacks at ground level; `null` when nothing remains. */
  footprint: Polygon | null;
  footprint_area_m2: number;
  buildings: BuildingMassing[];
  /** Every building fits with the required spacing. */
  fits: boolean;
  total_volume_m3: number;
  assumptions: string[];
}

/** The `envelope` artifact. */
export interface EnvelopeStudy {
  rules: EnvelopeRules;
  layout: Layout;
  site_area_m2: number;
  min_green_area_m2: number | null;
  /** `largest` and `windows`: from the rules alone. */
  bounds: Scenario[];
  /** From the rules and the layout. */
  proposal: Scenario;
  open_points: OpenPoint[];
}

// --- findings/notes.py -----------------------------------------------------

export interface OpenPoint {
  question: string;
  options: string[];
  why: string;
  citations: Citation[];
}

// --- findings/site.py ------------------------------------------------------

/** A neighbouring parcel the surveyor declared to be public land. */
export interface PublicParcel {
  id: string;
  /** The evidence: shape, size, position, what the aerial photo shows. */
  reason: string;
}

export interface ParcelChoice {
  address: string;
  parcel_ids: string[];
  rationale: string;
  assumptions: string[];
  public_parcels?: PublicParcel[];
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
  /** Studies stored before this shape hold a prism here: read it with `readEnvelope`. */
  envelope: EnvelopeStudy;
  /** One per distinct regulatory citation in `study`. */
  citation_checks: CitationCheck[];
  evidence: StoredCrop[];
}
