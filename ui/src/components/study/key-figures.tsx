import type { EnvelopeStudy, VerifiedStudy } from "@/lib/study-types";
import { cn } from "@/lib/utils";
import { findBound, groundArea, isCapped } from "./envelope";
import {
  formatArea,
  formatLength,
  formatNumber,
  formatPercent,
  formatStoreys,
  formatVolume,
} from "./format";

interface Figure {
  label: string;
  value: string;
  hint: string;
  warn?: boolean;
}

function heightFigure(envelope: EnvelopeStudy): Figure {
  const limits = envelope.rules.buildings;
  const heights = limits.flatMap((b) =>
    b.max_height_m.value === null ? [] : [b.max_height_m.value],
  );
  const storeys = limits.flatMap((b) =>
    b.max_storeys.value === null ? [] : [b.max_storeys.value],
  );
  if (heights.length === 0) {
    return { label: "Max height", value: "Not set", hint: "No height limit" };
  }
  const low = Math.min(...heights);
  const high = Math.max(...heights);
  const value =
    low === high
      ? formatLength(high)
      : `${formatNumber(low, 1)}–${formatLength(high)}`;
  let hint = low === high ? "All buildings" : "By building destination";
  if (storeys.length > 0) {
    const top = Math.max(...storeys);
    hint = `${hint} · up to ${formatStoreys(top)}`;
  }
  return { label: "Max height", value, hint };
}

function figures(study: VerifiedStudy, envelope: EnvelopeStudy): Figure[] {
  const largest = findBound(envelope, "largest");
  const windows = findBound(envelope, "windows");
  const { proposal } = envelope;
  const green = envelope.rules.min_green_ratio.value;
  const count = proposal.buildings.length;
  return [
    {
      label: "Site area",
      value: formatArea(envelope.site_area_m2 || study.site.area_m2),
      hint: "Parcel union",
    },
    {
      label: "Max ground area",
      value: largest ? formatArea(groundArea(largest)) : "—",
      hint: !largest
        ? "No largest bound"
        : isCapped(largest)
          ? `Capped; setbacks leave ${formatArea(largest.footprint_area_m2)}`
          : "Legal maximum, after setbacks",
    },
    heightFigure(envelope),
    {
      label: "Max volume",
      value: largest ? formatVolume(largest.total_volume_m3) : "—",
      hint: windows
        ? `With windows: ${formatVolume(windows.total_volume_m3)}`
        : "Legal maximum",
    },
    {
      label: "Proposal",
      value: count > 0 ? formatVolume(proposal.total_volume_m3) : "—",
      hint: !proposal.fits
        ? "Does not fit: see the proposal"
        : count === 0
          ? "No building placed"
          : `${count} building${count > 1 ? "s" : ""} · ${formatArea(groundArea(proposal))} ground`,
      warn: !proposal.fits,
    },
    {
      label: "Min green area",
      value:
        envelope.min_green_area_m2 === null
          ? "Not set"
          : formatArea(envelope.min_green_area_m2),
      hint:
        green === null ? "No green minimum" : `${formatPercent(green)} of site`,
    },
  ];
}

export function KeyFigures({
  study,
  envelope,
}: {
  study: VerifiedStudy;
  envelope: EnvelopeStudy | null;
}) {
  const shown: Figure[] = envelope
    ? figures(study, envelope)
    : [
        {
          label: "Site area",
          value: formatArea(study.site.area_m2),
          hint: "Parcel union",
        },
      ];
  return (
    <dl className="grid grid-cols-2 gap-2 px-4 pb-4 sm:grid-cols-3">
      {shown.map((f) => (
        <div
          key={f.label}
          className={cn(
            "bg-muted/40 rounded-lg border px-3 py-2",
            f.warn && "border-destructive/40 bg-destructive/5",
          )}
        >
          <dt className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
            {f.label}
          </dt>
          <dd className="mt-0.5 text-lg leading-tight font-semibold tabular-nums">
            {f.value}
          </dd>
          <dd
            className={cn(
              "text-muted-foreground mt-0.5 truncate text-xs",
              f.warn && "text-destructive",
            )}
            title={f.hint}
          >
            {f.hint}
          </dd>
        </div>
      ))}
    </dl>
  );
}
