"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Box, TriangleAlert } from "lucide-react";
import type { EnvelopeStudy, Scenario, VerifiedStudy } from "@/lib/study-types";
import { cn } from "@/lib/utils";
import { buildingColor, FOOTPRINT_COLOR } from "./colors";
import {
  buildingColors,
  groundArea,
  isCapped,
  isDrawable,
  levelsOf,
  limitsFor,
  massingBuildings,
  massingTag,
  scenarioHint,
  scenarioLabel,
  storeyHeight,
} from "./envelope";
import { formatArea, formatLength, formatVolume } from "./format";
import { polygonArea } from "./geometry";
import type { Massing3D } from "./volume-3d";

const Volume3D = dynamic(() => import("./volume-3d"), {
  ssr: false,
  loading: () => (
    <div
      role="status"
      className="bg-muted/40 text-muted-foreground flex h-80 w-full animate-pulse items-center justify-center rounded-lg border text-sm"
    >
      Loading 3D view…
    </div>
  ),
});

function Unavailable({ children }: { children: string }) {
  return (
    <div className="bg-muted/30 text-muted-foreground flex h-40 items-start gap-2 rounded-lg border border-dashed p-4 text-sm">
      <Box
        aria-hidden
        className="mt-0.5 size-4 shrink-0"
      />
      <p>{children}</p>
    </div>
  );
}

/** Building labels the envelope knows, to split grouped bound massings. */
function knownBuildings(study: VerifiedStudy, envelope: EnvelopeStudy) {
  return [
    ...envelope.rules.buildings.map((b) => b.building),
    ...study.study.admissibility.map((a) => a.building),
  ];
}

function toMassings(
  scenario: Scenario,
  envelope: EnvelopeStudy,
  known: string[],
): Massing3D[] {
  const colors = buildingColors(envelope);
  return scenario.buildings.filter(isDrawable).map((b, i) => ({
    id: `${scenario.name}-${i}-${b.building}`,
    tag: massingTag(b, known),
    footprint: b.footprint!,
    levels: levelsOf(b),
    color:
      scenario.name === "proposal"
        ? (colors.get(b.building) ?? buildingColor(i))
        : FOOTPRINT_COLOR,
    storeyHeight: storeyHeight(
      limitsFor(envelope, massingBuildings(b, known)[0]),
    ),
  }));
}

/** Some level is drawn smaller than the ground polygon (height setbacks or a cap). */
function hasScaledLevels(massings: Massing3D[]): boolean {
  return massings.some((m) => {
    const ground = polygonArea(m.footprint);
    return m.levels.some((l) => l.area_m2 < ground * 0.995);
  });
}

function hasSteppedLevels(massings: Massing3D[]): boolean {
  return massings.some((m) => new Set(m.levels.map((l) => l.area_m2)).size > 1);
}

function Caption({
  scenario,
  massings,
}: {
  scenario: Scenario;
  massings: Massing3D[];
}) {
  const stepped = hasSteppedLevels(massings);
  const capped = isCapped(scenario);
  return (
    <figcaption className="text-muted-foreground mt-2 space-y-1 text-xs leading-relaxed">
      <p>
        <span className="text-foreground font-medium">
          {scenarioLabel(scenario.name)}
        </span>
        {scenarioHint(scenario.name) && ` · ${scenarioHint(scenario.name)}`}.
        Ground{" "}
        {formatArea(
          scenario.buildings.length > 0
            ? groundArea(scenario)
            : scenario.footprint_area_m2,
        )}
        , volume{" "}
        <span className="text-foreground font-medium">
          {formatVolume(scenario.total_volume_m3)}
        </span>
        {massings.length > 0 &&
          `: ${massings
            .map(
              (m) =>
                `${m.tag} ${formatLength(m.levels[m.levels.length - 1].to_m, 0)}`,
            )
            .join(", ")}`}
        . The dashed outline is the footprint after setbacks; floor lines follow
        each building&apos;s height per storey (3 m when unset).
      </p>
      {!scenario.fits && (
        <p className="text-destructive">
          The buildings do not fit with the required spacing in this scenario.
        </p>
      )}
      {stepped && (
        <p>
          Setbacks grow with height here. The computation gives each
          level&apos;s area, not its outline: upper levels are drawn as the
          ground shape scaled about its centre to that area.
        </p>
      )}
      {capped && (
        <p>
          A footprint or green-space cap scales the buildings below the setback
          footprint ({formatArea(scenario.footprint_area_m2)}): the massing is
          drawn shrunk about its centre to the capped area, not at a chosen
          position.
        </p>
      )}
      {!stepped && !capped && hasScaledLevels(massings) && (
        <p>Levels smaller than the ground are drawn scaled to their area.</p>
      )}
    </figcaption>
  );
}

export function VolumePanel({
  study,
  envelope,
}: {
  study: VerifiedStudy;
  envelope: EnvelopeStudy;
}) {
  const scenarios = useMemo(
    () => [envelope.proposal, ...envelope.bounds],
    [envelope],
  );
  const [selected, setSelected] = useState(
    () =>
      scenarios.find((s) => s.buildings.some(isDrawable))?.name ?? "proposal",
  );
  const scenario = scenarios.find((s) => s.name === selected) ?? scenarios[0];
  const massings = useMemo(
    () => toMassings(scenario, envelope, knownBuildings(study, envelope)),
    [scenario, envelope, study],
  );

  return (
    <figure>
      <div
        role="group"
        aria-label="Scenario shown"
        className="bg-muted/40 mb-2 inline-flex rounded-lg border p-0.5"
      >
        {scenarios.map((s) => (
          <button
            key={s.name}
            type="button"
            aria-pressed={s.name === scenario.name}
            title={scenarioHint(s.name)}
            onClick={() => setSelected(s.name)}
            className={cn(
              "focus-visible:ring-ring/50 inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium outline-none focus-visible:ring-[3px]",
              s.name === scenario.name
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {!s.fits && (
              <TriangleAlert
                aria-label="does not fit"
                className="text-destructive size-3"
              />
            )}
            {scenarioLabel(s.name)}
          </button>
        ))}
      </div>
      {massings.length > 0 ? (
        <Volume3D
          site={study.site.polygon}
          boundaries={study.boundaries}
          massings={massings}
          outline={scenario.footprint}
          label={`3D view of the ${scenarioLabel(scenario.name).toLowerCase()} scenario: ${massings.length} massing(s) on the site`}
        />
      ) : (
        <Unavailable>
          {scenario.footprint === null
            ? "Nothing remains of the site once this scenario's setbacks are applied, so there is no volume to draw."
            : "No building massing in this scenario, so there is no volume to draw."}
        </Unavailable>
      )}
      <Caption
        scenario={scenario}
        massings={massings}
      />
    </figure>
  );
}
