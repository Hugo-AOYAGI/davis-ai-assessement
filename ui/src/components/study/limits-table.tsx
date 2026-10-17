import type { ReactNode } from "react";
import type {
  BuildingLimits,
  Distance,
  EnvelopeRules,
  Limit,
  SetbackRule,
} from "@/lib/study-types";
import { CitationList } from "./citation-chip";
import { BOUNDARY_COLORS, BOUNDARY_KINDS, BOUNDARY_LABELS } from "./colors";
import { formatDistance, shortName } from "./envelope";
import {
  formatLength,
  formatNumber,
  formatPercent,
  formatStoreys,
} from "./format";

/** A rule restated with its sources. */
function Cited({
  label,
  rule,
  citations,
}: Pick<Limit, "rule" | "citations"> & { label?: string }) {
  return (
    <div className="[&+&]:mt-2">
      <p className="leading-relaxed">
        {label && <span className="text-muted-foreground">{label}: </span>}
        {rule}
      </p>
      <CitationList
        citations={citations}
        className="mt-1.5"
      />
    </div>
  );
}

function Row({
  label,
  values,
  children,
}: {
  label: ReactNode;
  /** One line per value; `null` reads "Not regulated". */
  values: string[] | null;
  children: ReactNode;
}) {
  return (
    <tr className="align-top">
      <th
        scope="row"
        className="w-32 py-2.5 pr-3 text-left font-normal sm:w-40"
      >
        <span className="text-muted-foreground block text-xs">{label}</span>
        {values === null ? (
          <span className="text-muted-foreground text-sm italic">
            Not regulated
          </span>
        ) : (
          values.map((v) => (
            <span
              key={v}
              className="block font-semibold tabular-nums"
            >
              {v}
            </span>
          ))
        )}
      </th>
      <td className="py-2.5">{children}</td>
    </tr>
  );
}

function Group({ title }: { title: string }) {
  return (
    <tr>
      <th
        scope="rowgroup"
        colSpan={2}
        className="text-muted-foreground pt-3 pb-1 text-left text-[11px] font-medium tracking-wide uppercase"
      >
        {title}
      </th>
    </tr>
  );
}

/** Both distances, merged when they say the same thing. */
function distances(
  withWindows: Distance | null,
  withoutWindows: Distance | null,
): { label?: string; distance: Distance }[] {
  if (withWindows && withoutWindows) {
    const same =
      formatDistance(withWindows) === formatDistance(withoutWindows) &&
      withWindows.rule === withoutWindows.rule;
    return same
      ? [{ distance: withWindows }]
      : [
          { label: "With windows", distance: withWindows },
          { label: "Without windows", distance: withoutWindows },
        ];
  }
  if (withWindows) return [{ label: "With windows", distance: withWindows }];
  if (withoutWindows) {
    return [{ label: "Without windows", distance: withoutWindows }];
  }
  return [];
}

/** `6 m · windows`, `3 m · no windows`, or the distance alone when merged. */
function optionValue(label: string | undefined, distance: Distance): string {
  const value = formatDistance(distance);
  if (!label) return value;
  return `${value} · ${label === "With windows" ? "windows" : "no windows"}`;
}

function SetbackRow({ setback }: { setback: SetbackRule }) {
  const options = distances(setback.with_windows, setback.without_windows);
  const values = [
    ...(setback.on_limit_allowed ? ["On the limit"] : []),
    ...options.map(({ label, distance }) => {
      const prefix = setback.on_limit_allowed ? "or " : "";
      return `${prefix}${optionValue(label, distance)}`;
    }),
  ];
  return (
    <Row
      label={
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="h-0.5 w-3 rounded-full"
            style={{ backgroundColor: BOUNDARY_COLORS[setback.kind] }}
          />
          {BOUNDARY_LABELS[setback.kind]} setback
        </span>
      }
      values={values.length > 0 ? values : null}
    >
      {setback.on_limit_allowed && (
        <p className="text-muted-foreground mb-2 text-xs">
          Building right on the limit is allowed.
        </p>
      )}
      {options.map(({ label, distance }) => (
        <Cited
          key={label ?? "both"}
          label={label}
          rule={distance.rule}
          citations={distance.citations}
        />
      ))}
      {options.length === 0 && !setback.on_limit_allowed && (
        <p className="text-muted-foreground">No setback distance given.</p>
      )}
    </Row>
  );
}

function HeightRow({ limits }: { limits: BuildingLimits }) {
  const height = limits.max_height_m.value;
  const storeys = limits.max_storeys.value;
  const values = [
    ...(height === null ? [] : [formatLength(height)]),
    ...(storeys === null
      ? []
      : [`${formatStoreys(storeys)} (${formatNumber(storeys)} storeys)`]),
  ];
  return (
    <Row
      label={
        <span title={limits.building}>
          Height · {shortName(limits.building)}
        </span>
      }
      values={values.length > 0 ? values : null}
    >
      <p className="mb-1 text-xs font-medium">{limits.building}</p>
      <Cited
        label="Height"
        {...limits.max_height_m}
      />
      {limits.max_storeys.rule !== limits.max_height_m.rule && (
        <Cited
          label="Storeys"
          {...limits.max_storeys}
        />
      )}
    </Row>
  );
}

function RatioRow({ label, limit }: { label: string; limit: Limit }) {
  return (
    <Row
      label={label}
      values={limit.value === null ? null : [formatPercent(limit.value)]}
    >
      <Cited {...limit} />
    </Row>
  );
}

export function LimitsTable({ rules }: { rules: EnvelopeRules }) {
  const setbacks = BOUNDARY_KINDS.flatMap((kind) =>
    rules.setbacks.filter((s) => s.kind === kind),
  );
  const spacing = distances(
    rules.spacing_with_windows,
    rules.spacing_without_windows,
  );
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">
        Envelope rules, with the rule and the cited passages
      </caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Limit</th>
          <th scope="col">Rule and sources</th>
        </tr>
      </thead>
      <tbody className="divide-y">
        <Group title="Setbacks" />
        {setbacks.map((s) => (
          <SetbackRow
            key={s.kind}
            setback={s}
          />
        ))}
        <Group title="Heights" />
        {rules.buildings.map((b) => (
          <HeightRow
            key={b.building}
            limits={b}
          />
        ))}
        <Group title="Between buildings" />
        <Row
          label="Spacing"
          values={
            spacing.length > 0
              ? spacing.map(({ label, distance }) =>
                  optionValue(label, distance),
                )
              : null
          }
        >
          {spacing.length > 0 ? (
            spacing.map(({ label, distance }) => (
              <Cited
                key={label ?? "both"}
                label={label}
                rule={distance.rule}
                citations={distance.citations}
              />
            ))
          ) : (
            <p className="text-muted-foreground">
              No spacing between buildings set.
            </p>
          )}
        </Row>
        <Group title="Caps" />
        <RatioRow
          label="Max footprint ratio"
          limit={rules.max_footprint_ratio}
        />
        <RatioRow
          label="Min green ratio"
          limit={rules.min_green_ratio}
        />
      </tbody>
    </table>
  );
}
