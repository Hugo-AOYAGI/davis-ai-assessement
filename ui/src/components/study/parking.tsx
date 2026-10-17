import type { ParkingRule } from "@/lib/study-types";
import { CitationList } from "./citation-chip";
import { formatNumber } from "./format";

function ratio(rule: ParkingRule): string {
  const spaces = `${formatNumber(rule.spaces, 2)} space${rule.spaces === 1 ? "" : "s"}`;
  switch (rule.basis) {
    case "floor_area_m2":
      return `${spaces} / ${formatNumber(rule.per, 1)} m² floor area`;
    case "unit":
      return rule.per === 1
        ? `${spaces} / unit`
        : `${spaces} / ${formatNumber(rule.per, 1)} units`;
    case "other":
      return `${spaces} / ${formatNumber(rule.per, 1)}`;
  }
}

export function ParkingList({ rules }: { rules: ParkingRule[] }) {
  if (rules.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No car parking requirement.
      </p>
    );
  }
  return (
    <ul className="divide-y">
      {rules.map((r) => (
        <li
          key={r.use}
          className="py-2.5 first:pt-0 last:pb-0"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            <p className="text-sm font-medium">{r.use}</p>
            <p className="text-sm font-semibold tabular-nums">{ratio(r)}</p>
          </div>
          <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
            {r.rule}
          </p>
          <CitationList
            citations={r.citations}
            className="mt-1.5"
          />
        </li>
      ))}
    </ul>
  );
}
