import { useState } from "react";
import { ChevronRight, LoaderCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  toolStatus,
  type ToolCall,
  type ToolResults,
  type ToolStatus,
} from "@/lib/message-blocks";
import { ToolRow } from "./tool-row";

/**
 * A run of tool calls. One call shows as its row; several fold into an "N steps" group,
 * closed by default. While the group is still active its latest row stays visible.
 */
export function ToolSteps({
  calls,
  results,
  running,
  waiting = false,
  active = false,
  className,
}: {
  calls: ToolCall[];
  results: ToolResults;
  /** Whether calls without a result are still being executed. */
  running: boolean;
  /** Whether the run is paused on a question to the user. */
  waiting?: boolean;
  /** Whether this group is where the run is currently working. */
  active?: boolean;
  className?: string;
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  if (calls.length === 0) return null;

  const rows = calls.map((call, index) => {
    const result = call.id ? results.get(call.id) : undefined;
    return {
      key: call.id || `${call.name}-${index}`,
      call,
      result,
      status: toolStatus(result, { running, waiting }),
    };
  });
  const renderRow = (row: (typeof rows)[number]) => (
    <ToolRow
      key={row.key}
      call={row.call}
      result={row.result}
      status={row.status}
    />
  );

  if (rows.length === 1) {
    return <div className={className}>{renderRow(rows[0])}</div>;
  }

  const open = userOpen ?? false;
  const failed = rows.filter((r) => r.status === "error").length;
  const inProgress = rows.some((r) =>
    (["running", "waiting"] as ToolStatus[]).includes(r.status),
  );
  const last = rows[rows.length - 1];

  return (
    <div className={cn("min-w-0 text-sm", className)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setUserOpen(!open)}
        className="text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-ring/50 flex w-full items-center gap-2 rounded-md px-2 py-1 text-left outline-none focus-visible:ring-[3px]"
      >
        <ChevronRight
          className={cn(
            "size-3.5 shrink-0 transition-transform",
            open && "rotate-90",
          )}
        />
        <span className="font-medium">{rows.length} steps</span>
        {failed > 0 && (
          <span className="text-destructive">· {failed} failed</span>
        )}
        {inProgress && active && (
          <LoaderCircle
            className="ml-auto size-3.5 animate-spin"
            aria-label="Running"
          />
        )}
      </button>
      {open ? (
        <div className="ml-[0.9rem] border-l pl-1">{rows.map(renderRow)}</div>
      ) : (
        active && (
          <div className="ml-[0.9rem] border-l pl-1">{renderRow(last)}</div>
        )
      )}
    </div>
  );
}
