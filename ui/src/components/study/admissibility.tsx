import { Ban, CircleCheck, CircleDot, TriangleAlert } from "lucide-react";
import type { Admissibility, Verdict } from "@/lib/study-types";
import { CitationList } from "./citation-chip";
import { Pill, type PillTone } from "./pill";

const VERDICTS: Record<
  Verdict,
  { label: string; tone: PillTone; icon: typeof Ban }
> = {
  permitted: { label: "Permitted", tone: "positive", icon: CircleCheck },
  conditional: { label: "Conditional", tone: "caution", icon: CircleDot },
  restricted: { label: "Restricted", tone: "warning", icon: TriangleAlert },
  prohibited: { label: "Prohibited", tone: "negative", icon: Ban },
};

export function VerdictPill({ verdict }: { verdict: Verdict }) {
  const { label, tone, icon: Icon } = VERDICTS[verdict];
  return (
    <Pill tone={tone}>
      <Icon aria-hidden />
      {label}
    </Pill>
  );
}

export function AdmissibilityList({ items }: { items: Admissibility[] }) {
  return (
    <ul className="space-y-3">
      {items.map((a) => (
        <li
          key={a.building}
          className="rounded-lg border p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="text-sm font-semibold">{a.building}</p>
            <VerdictPill verdict={a.verdict} />
          </div>
          <p className="text-muted-foreground mt-1 text-xs">
            {a.stated_use} → {a.destination}
          </p>
          {a.conditions.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm">
              {a.conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
          <CitationList
            citations={a.citations}
            className="mt-2"
          />
        </li>
      ))}
    </ul>
  );
}
