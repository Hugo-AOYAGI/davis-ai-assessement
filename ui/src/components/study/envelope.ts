import type {
  BuildingLimits,
  BuildingMassing,
  Distance,
  EnvelopeStudy,
  Level,
  Scenario,
  VerifiedStudy,
} from "@/lib/study-types";
import { buildingColor } from "./colors";
import { capitalize, formatLength, formatNumber } from "./format";
import { polygonArea } from "./geometry";

/**
 * The study's envelope, or `null` when it is missing or in the older prism
 * shape (studies stored before bounds and proposal existed).
 */
export function readEnvelope(study: VerifiedStudy): EnvelopeStudy | null {
  const e = study.envelope as Partial<EnvelopeStudy> | null | undefined;
  if (!e?.rules || !e.layout || !Array.isArray(e.bounds) || !e.proposal) {
    return null;
  }
  return e as EnvelopeStudy;
}

const SCENARIOS: Record<string, { label: string; hint: string }> = {
  proposal: {
    label: "Proposal",
    hint: "The architect's layout of the program's buildings",
  },
  largest: {
    label: "Largest",
    hint: "Legal maximum: smallest setbacks, on the limit wherever allowed",
  },
  windows: {
    label: "With windows",
    hint: "Setbacks for facades with windows: the realistic case for housing",
  },
};

export const scenarioLabel = (name: string) =>
  SCENARIOS[name]?.label ?? capitalize(name);

export const scenarioHint = (name: string) => SCENARIOS[name]?.hint ?? "";

export const findBound = (envelope: EnvelopeStudy, name: string) =>
  envelope.bounds.find((s) => s.name === name);

/**
 * Ground area the scenario's buildings take. Proposal parts are disjoint and
 * add up; a bound's massings (one per height band, "how much", not "where")
 * share the same ground, so the largest one counts.
 */
export function groundArea(scenario: Scenario): number {
  const areas = scenario.buildings.map((b) => b.footprint_area_m2);
  if (areas.length === 0) return 0;
  return scenario.name === "proposal"
    ? areas.reduce((s, a) => s + a, 0)
    : Math.max(...areas);
}

/**
 * A cap (footprint ratio, green space) scaled some building's area below its
 * ground polygon: the computation shrinks the areas, not the polygons.
 */
export const isCapped = (scenario: Scenario) =>
  scenario.buildings.some(
    (b) =>
      b.footprint !== null &&
      b.footprint_area_m2 < polygonArea(b.footprint) * 0.995,
  );

/** `0.5` → `H/2`, `1` → `H`, `0.4` → `0,4 × H`. */
function formatRatio(ratio: number): string {
  if (Math.abs(ratio - 1) < 1e-9) return "H";
  const inverse = 1 / ratio;
  if (Math.abs(inverse - Math.round(inverse)) < 1e-6) {
    return `H/${Math.round(inverse)}`;
  }
  return `${formatNumber(ratio, 2)} × H`;
}

/** `6 m`, `H/2`, `H/2, min 4 m`. */
export function formatDistance(d: Distance): string {
  const parts: string[] = [];
  if (d.height_ratio !== null) parts.push(formatRatio(d.height_ratio));
  if (d.min_m !== null) {
    parts.push(
      d.height_ratio === null
        ? formatLength(d.min_m)
        : `min ${formatLength(d.min_m)}`,
    );
  }
  return parts.join(", ") || "—";
}

/**
 * Short tag for a building label: its trailing abbreviation (`… (RSE)`),
 * the label itself when short, else the initials of its words.
 */
export function shortName(label: string): string {
  const abbreviation = /\(([^()]{1,12})\)\s*$/.exec(label);
  if (abbreviation) return abbreviation[1];
  if (label.length <= 16) return label;
  const words = label
    .split(/[\s_-]+/)
    .filter((w) => w.length > 3 || /^\p{Lu}/u.test(w));
  return words.map((w) => w.charAt(0).toUpperCase()).join("");
}

/**
 * The building labels a massing stands for: its own, or several when a bound
 * groups buildings of one height band under a joined label.
 */
export function massingBuildings(
  massing: BuildingMassing,
  known: string[],
): string[] {
  if (known.includes(massing.building)) return [massing.building];
  const parts = massing.building.split(/,\s*/);
  return parts.length > 1 && parts.every((p) => known.includes(p))
    ? parts
    : [massing.building];
}

/** Short tag for a massing: `RSE`, or `RSE + RJA` for a grouped bound massing. */
export const massingTag = (massing: BuildingMassing, known: string[]) =>
  massingBuildings(massing, known).map(shortName).join(" + ");

export const limitsFor = (envelope: EnvelopeStudy, building: string) =>
  envelope.rules.buildings.find((b) => b.building === building);

/** Levels to draw: the stored ones, else one prism slice to the massing's height. */
export function levelsOf(massing: BuildingMassing): Level[] {
  const levels = massing.levels.filter((l) => l.to_m > l.from_m);
  if (levels.length > 0) return levels;
  return massing.max_height_m > 0
    ? [
        {
          from_m: 0,
          to_m: massing.max_height_m,
          area_m2: massing.footprint_area_m2,
        },
      ]
    : [];
}

/** A massing has a ground polygon and some height. */
export const isDrawable = (massing: BuildingMassing) =>
  massing.footprint !== null && levelsOf(massing).length > 0;

/** Floor-to-floor height for floor lines: max height / max storeys, else 3 m. */
export function storeyHeight(limits: BuildingLimits | undefined): number {
  const height = limits?.max_height_m.value;
  const storeys = limits?.max_storeys.value;
  return height && storeys && storeys > 0 ? height / storeys : 3;
}

/**
 * One colour per proposal building, shared by the plan, the 3D view and the
 * proposal table: layout order first, then any building it does not list.
 */
export function buildingColors(envelope: EnvelopeStudy): Map<string, string> {
  const names = [
    ...envelope.layout.order,
    ...envelope.proposal.buildings.map((b) => b.building),
    ...envelope.rules.buildings.map((b) => b.building),
  ];
  const colors = new Map<string, string>();
  for (const name of names) {
    if (!colors.has(name)) colors.set(name, buildingColor(colors.size));
  }
  return colors;
}
