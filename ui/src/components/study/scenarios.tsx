import { TriangleAlert } from "lucide-react";
import type { EnvelopeStudy, Scenario } from "@/lib/study-types";
import { CitationList } from "./citation-chip";
import {
  buildingColors,
  findBound,
  groundArea,
  isCapped,
  limitsFor,
  massingBuildings,
  massingTag,
  scenarioHint,
  scenarioLabel,
  shortName,
} from "./envelope";
import {
  capitalize,
  formatArea,
  formatLength,
  formatPercent,
  formatVolume,
} from "./format";
import { Pill } from "./pill";

function Notes({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
        {title}
      </p>
      <ul className="text-muted-foreground mt-1 list-disc space-y-0.5 pl-5 text-xs leading-relaxed">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function NoFit() {
  return (
    <Pill tone="negative">
      <TriangleAlert aria-hidden />
      Does not fit
    </Pill>
  );
}

function BoundCard({
  scenario,
  known,
}: {
  scenario: Scenario;
  known: string[];
}) {
  const capped = isCapped(scenario);
  return (
    <li className="rounded-lg border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">
            {scenarioLabel(scenario.name)}
          </p>
          <p className="text-muted-foreground text-xs">
            {scenarioHint(scenario.name)}
          </p>
        </div>
        {!scenario.fits && <NoFit />}
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="text-muted-foreground text-xs">Ground area</dt>
          <dd className="font-semibold tabular-nums">
            {formatArea(
              scenario.buildings.length > 0
                ? groundArea(scenario)
                : scenario.footprint_area_m2,
            )}
          </dd>
          {capped && (
            <dd className="text-muted-foreground text-xs">
              capped; setbacks leave {formatArea(scenario.footprint_area_m2)}
            </dd>
          )}
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Total volume</dt>
          <dd className="font-semibold tabular-nums">
            {formatVolume(scenario.total_volume_m3)}
          </dd>
        </div>
      </dl>
      {scenario.buildings.length > 0 && (
        <ul className="mt-2 divide-y border-t text-xs">
          {scenario.buildings.map((b, i) => (
            <li
              key={`${b.building}-${i}`}
              className="flex items-baseline justify-between gap-2 py-1.5"
            >
              <span
                className="min-w-0 truncate"
                title={massingBuildings(b, known).join(", ")}
              >
                {massingTag(b, known)}
              </span>
              <span className="text-muted-foreground shrink-0 tabular-nums">
                {formatLength(b.max_height_m, 0)} · {formatVolume(b.volume_m3)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Notes
        title="Assumptions"
        items={scenario.assumptions}
      />
    </li>
  );
}

/** The bounds: what the rules alone allow, without placing the buildings. */
export function BoundsList({
  envelope,
  known,
}: {
  envelope: EnvelopeStudy;
  known: string[];
}) {
  if (envelope.bounds.length === 0) {
    return <p className="text-muted-foreground text-sm">No bound computed.</p>;
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {envelope.bounds.map((s) => (
        <BoundCard
          key={s.name}
          scenario={s}
          known={known}
        />
      ))}
    </ul>
  );
}

const CUTS: Record<string, string> = {
  across_long_axis: "Across the long axis",
  along_long_axis: "Along the long axis",
};

function LayoutFacts({ envelope }: { envelope: EnvelopeStudy }) {
  const { layout, rules } = envelope;
  const spacing = layout.facing_windows
    ? rules.spacing_with_windows
    : rules.spacing_without_windows;
  const spacingText = spacing?.min_m
    ? `spacing ${formatLength(spacing.min_m, 0)}`
    : "spacing not set";
  const facts = [
    { label: "Cut", value: CUTS[layout.cut] ?? layout.cut },
    {
      label: "First part",
      value: `${formatPercent(layout.first_share)} of the usable area`,
    },
    {
      label: "Order",
      value:
        layout.order.length > 0
          ? `${layout.order.map(shortName).join(" → ")} (first nearest the road)`
          : "—",
    },
    {
      label: "Facing windows",
      value: `${layout.facing_windows ? "Yes" : "No"}: ${spacingText}`,
    },
  ];
  return (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
      {facts.map((f) => (
        <div
          key={f.label}
          className="flex gap-2"
        >
          <dt className="text-muted-foreground w-24 shrink-0">{f.label}</dt>
          <dd>{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The architect's proposal: one way to place the program's buildings. */
export function ProposalView({
  envelope,
  known,
}: {
  envelope: EnvelopeStudy;
  known: string[];
}) {
  const { proposal, layout } = envelope;
  const colors = buildingColors(envelope);
  const rank = (name: string) => {
    const i = layout.order.indexOf(name);
    return i === -1 ? layout.order.length : i;
  };
  const buildings = [...proposal.buildings].sort(
    (a, b) => rank(a.building) - rank(b.building),
  );
  const windows = findBound(envelope, "windows");

  return (
    <div className="space-y-3">
      {!proposal.fits && (
        <div className="border-destructive/40 bg-destructive/5 text-destructive flex items-start gap-2 rounded-lg border p-3 text-sm">
          <TriangleAlert
            aria-hidden
            className="mt-0.5 size-4 shrink-0"
          />
          <p>
            <span className="font-semibold">
              The buildings do not fit on the plot
            </span>{" "}
            with the required spacing: a part is empty or the gap does not fit.
            The figures below are not a buildable layout; the assumptions give
            the reason.
          </p>
        </div>
      )}
      {buildings.length === 0 ? (
        <p className="text-muted-foreground text-sm">No building placed.</p>
      ) : (
        <table className="w-full text-sm">
          <caption className="sr-only">
            Proposal: ground area, height and volume per building
          </caption>
          <thead>
            <tr className="text-muted-foreground text-left text-xs">
              <th
                scope="col"
                className="pb-1 font-normal"
              >
                Building
              </th>
              <th
                scope="col"
                className="pb-1 text-right font-normal"
              >
                Ground
              </th>
              <th
                scope="col"
                className="pb-1 text-right font-normal"
              >
                Height
              </th>
              <th
                scope="col"
                className="pb-1 text-right font-normal"
              >
                Volume
              </th>
            </tr>
          </thead>
          <tbody className="divide-y border-y">
            {buildings.map((b, i) => {
              const max = limitsFor(envelope, b.building)?.max_height_m.value;
              const empty = b.footprint === null || b.footprint_area_m2 <= 0;
              return (
                <tr
                  key={`${b.building}-${i}`}
                  className="align-top"
                >
                  <th
                    scope="row"
                    className="py-1.5 pr-2 text-left font-normal"
                  >
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-2.5 shrink-0 rounded-sm"
                        style={{ backgroundColor: colors.get(b.building) }}
                      />
                      <span className="font-medium">
                        {massingTag(b, known)}
                      </span>
                      {empty && <Pill tone="negative">No room</Pill>}
                    </span>
                    <span className="text-muted-foreground block text-xs">
                      {b.building}
                    </span>
                  </th>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatArea(b.footprint_area_m2)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatLength(b.max_height_m, 0)}
                    {max != null && (
                      <span className="text-muted-foreground block text-xs">
                        max {formatLength(max, 0)}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatVolume(b.volume_m3)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="font-semibold">
              <th
                scope="row"
                className="pt-1.5 text-left"
              >
                Total
              </th>
              <td className="pt-1.5 text-right tabular-nums">
                {formatArea(groundArea(proposal))}
              </td>
              <td />
              <td className="pt-1.5 text-right tabular-nums">
                {formatVolume(proposal.total_volume_m3)}
              </td>
            </tr>
          </tfoot>
        </table>
      )}
      {windows && buildings.length > 0 && (
        <p className="text-muted-foreground text-xs">
          Cut from the footprint with windows (
          {formatArea(windows.footprint_area_m2)}); bound volume with windows{" "}
          {formatVolume(windows.total_volume_m3)}.
        </p>
      )}
      <LayoutFacts envelope={envelope} />
      {layout.reasons && (
        <p className="text-sm leading-relaxed">{layout.reasons}</p>
      )}
      {layout.oap.length > 0 && (
        <div>
          <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
            OAP prescriptions followed
          </p>
          <ul className="mt-1 divide-y">
            {layout.oap.map((c, i) => (
              <li
                key={`${c.prescription.topic}-${i}`}
                className="py-2 first:pt-1 last:pb-0"
              >
                <p className="text-sm font-medium">
                  {capitalize(c.prescription.topic)}
                </p>
                <p className="mt-0.5 text-sm leading-relaxed">{c.how}</p>
                <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
                  {c.prescription.text}
                </p>
                <CitationList
                  citations={c.prescription.citations}
                  className="mt-1.5"
                />
              </li>
            ))}
          </ul>
        </div>
      )}
      <Notes
        title="Assumptions"
        items={proposal.assumptions}
      />
    </div>
  );
}
