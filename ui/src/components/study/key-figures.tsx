import type { VerifiedStudy } from "@/lib/study-types";
import { footprintCap } from "./envelope";
import {
  formatArea,
  formatLength,
  formatPercent,
  formatStoreys,
  formatVolume,
} from "./format";

interface Figure {
  label: string;
  value: string;
  hint: string;
}

function figures({ envelope, study }: VerifiedStudy): Figure[] {
  const params = study.envelope;
  const site = envelope.site_area_m2;
  const cap = footprintCap(envelope, params);
  const storeys = params.max_storeys.value;
  const green = params.min_green_ratio.value;
  return [
    {
      label: "Site area",
      value: formatArea(site),
      hint: "Parcel union",
    },
    {
      label: "Buildable footprint",
      value: formatArea(envelope.footprint_area_m2),
      hint: "After setbacks",
    },
    {
      label: "Max footprint area",
      value: formatArea(envelope.max_footprint_area_m2),
      hint: cap ? `Capped by ${cap}` : "No ratio cap applies",
    },
    {
      label: "Max height",
      value:
        envelope.max_height_m === null
          ? "Not set"
          : formatLength(envelope.max_height_m),
      hint:
        storeys === null
          ? "No storey limit"
          : `${formatStoreys(storeys)} · ${storeys} storeys`,
    },
    {
      label: "Max volume",
      value:
        envelope.max_volume_m3 === null
          ? "—"
          : formatVolume(envelope.max_volume_m3),
      hint:
        envelope.max_volume_m3 === null
          ? "No height limit"
          : "Max footprint × height",
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

export function KeyFigures({ study }: { study: VerifiedStudy }) {
  return (
    <dl className="grid grid-cols-2 gap-2 px-4 pb-4 sm:grid-cols-3">
      {figures(study).map((f) => (
        <div
          key={f.label}
          className="bg-muted/40 rounded-lg border px-3 py-2"
        >
          <dt className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
            {f.label}
          </dt>
          <dd className="mt-0.5 text-lg leading-tight font-semibold tabular-nums">
            {f.value}
          </dd>
          <dd className="text-muted-foreground mt-0.5 truncate text-xs">
            {f.hint}
          </dd>
        </div>
      ))}
    </dl>
  );
}
