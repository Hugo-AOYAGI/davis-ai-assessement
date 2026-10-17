import { Bot, UserRound } from "lucide-react";
import type { Ambiguity } from "@/lib/study-types";
import { CitationList } from "./citation-chip";
import { Pill } from "./pill";

function ResolvedBy({ by }: { by: Ambiguity["resolved_by"] }) {
  return by === "user" ? (
    <Pill
      tone="info"
      title="Answered by the user when asked"
    >
      <UserRound aria-hidden />
      Resolved by user
    </Pill>
  ) : (
    <Pill
      tone="outline"
      title="Chosen and justified by the agent"
    >
      <Bot aria-hidden />
      Resolved by agent
    </Pill>
  );
}

export function AmbiguityList({ items }: { items: Ambiguity[] }) {
  if (items.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        The documents left no open question.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {items.map((a, i) => (
        <li
          key={i}
          className="rounded-lg border p-3"
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium">{a.question}</p>
            <ResolvedBy by={a.resolved_by} />
          </div>
          {a.options.length > 0 && (
            <ul className="text-muted-foreground mt-2 list-disc space-y-0.5 pl-5 text-xs">
              {a.options.map((o) => (
                <li key={o}>{o}</li>
              ))}
            </ul>
          )}
          <dl className="mt-2 space-y-1.5 text-sm">
            <div className="bg-muted/50 rounded-md px-2.5 py-1.5">
              <dt className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                Chosen
              </dt>
              <dd>{a.chosen}</dd>
            </div>
            <div className="px-2.5">
              <dt className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                Why
              </dt>
              <dd className="text-muted-foreground leading-relaxed">
                {a.rationale}
              </dd>
            </div>
          </dl>
          <CitationList
            citations={a.citations}
            className="mt-2"
          />
        </li>
      ))}
    </ul>
  );
}
