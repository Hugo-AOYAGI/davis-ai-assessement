import type { Rule } from "@/lib/study-types";
import { CitationList } from "./citation-chip";
import { capitalize } from "./format";

/** Free-text rules (feasibility conditions, OAP prescriptions). */
export function RuleList({ rules, empty }: { rules: Rule[]; empty: string }) {
  if (rules.length === 0) {
    return <p className="text-muted-foreground text-sm">{empty}</p>;
  }
  return (
    <ul className="divide-y">
      {rules.map((r, i) => (
        <li
          key={`${r.topic}-${i}`}
          className="py-2.5 first:pt-0 last:pb-0"
        >
          <p className="text-sm font-medium">{capitalize(r.topic)}</p>
          <p className="text-muted-foreground mt-0.5 text-sm leading-relaxed">
            {r.text}
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
