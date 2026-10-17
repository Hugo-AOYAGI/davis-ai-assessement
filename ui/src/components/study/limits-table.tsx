import type { EnvelopeParameters, Limit } from "@/lib/study-types";
import { CitationList } from "./citation-chip";
import {
  formatLength,
  formatNumber,
  formatPercent,
  formatStoreys,
} from "./format";

type Unit = "m" | "storeys" | "ratio";

const ROWS: { key: keyof EnvelopeParameters; label: string; unit: Unit }[] = [
  { key: "setback_road_m", label: "Road setback", unit: "m" },
  { key: "setback_side_m", label: "Side setback", unit: "m" },
  { key: "setback_rear_m", label: "Rear setback", unit: "m" },
  { key: "max_height_m", label: "Max height", unit: "m" },
  { key: "max_storeys", label: "Max storeys", unit: "storeys" },
  { key: "max_footprint_ratio", label: "Max footprint ratio", unit: "ratio" },
  { key: "min_green_ratio", label: "Min green ratio", unit: "ratio" },
];

function formatValue(limit: Limit, unit: Unit): string {
  if (limit.value === null) return "Not regulated";
  switch (unit) {
    case "m":
      return formatLength(limit.value);
    case "storeys":
      return `${formatNumber(limit.value)} (${formatStoreys(limit.value)})`;
    case "ratio":
      return formatPercent(limit.value);
  }
}

export function LimitsTable({ params }: { params: EnvelopeParameters }) {
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">
        Envelope limits, with the rule and the cited passages
      </caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Limit</th>
          <th scope="col">Rule and sources</th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {ROWS.map(({ key, label, unit }) => {
          const limit = params[key];
          return (
            <tr
              key={key}
              className="align-top"
            >
              <th
                scope="row"
                className="w-32 py-2.5 pr-3 text-left font-normal sm:w-40"
              >
                <span className="text-muted-foreground block text-xs">
                  {label}
                </span>
                <span
                  className={
                    limit.value === null
                      ? "text-muted-foreground text-sm italic"
                      : "font-semibold tabular-nums"
                  }
                >
                  {formatValue(limit, unit)}
                </span>
              </th>
              <td className="py-2.5">
                <p className="leading-relaxed">{limit.rule}</p>
                <CitationList
                  citations={limit.citations}
                  className="mt-1.5"
                />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
