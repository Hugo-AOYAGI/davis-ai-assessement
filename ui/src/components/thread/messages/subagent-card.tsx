import { useEffect, useState } from "react";
import type { ToolMessage } from "@langchain/langgraph-sdk";
import { LoaderCircle } from "lucide-react";
import { useStreamContext } from "@/providers/Stream";
import { cn } from "@/lib/utils";
import {
  allToolCalls,
  firstLine,
  indexToolResults,
  messageText,
  type ToolCall,
  type ToolStatus,
} from "@/lib/message-blocks";
import { describeSubagent } from "@/lib/tool-labels";
import { MarkdownText } from "../markdown-text";
import { Disclosure } from "./disclosure";
import { ToolSteps } from "./tool-steps";
import { StatusIcon } from "./tool-row";

const STATUS_LABEL: Record<ToolStatus, string> = {
  running: "Working",
  done: "Done",
  error: "Failed",
  waiting: "Waiting",
  stopped: "Stopped",
};

/** Seconds of silence before the waiting row shows its counter (avoids flicker on fast steps). */
const SHOW_SECONDS_FROM = 5;

const text = (value: unknown) => (typeof value === "string" ? value : "");

/**
 * A spinner row with the seconds elapsed since it mounted, ticking every second. Re-keyed on
 * each activity so its clock counts from the last one.
 */
function WaitingRow({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  const [since] = useState(() => Date.now());
  const [now, setNow] = useState(since);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.floor((now - since) / 1000);

  return (
    <div
      className={cn(
        "text-muted-foreground flex items-center gap-2 text-xs",
        className,
      )}
    >
      <LoaderCircle className="size-3.5 animate-spin" />
      {seconds >= SHOW_SECONDS_FROM ? `${label} ${seconds} s` : label}
    </div>
  );
}

/**
 * A delegation to a sub-agent (`task` call): who, the task, its own steps while it works,
 * and its answer.
 *
 * The inner steps come from the sub-agent's stream, tracked live by the client; after a
 * reload they are recovered from the sub-agent's checkpoints when the server still has them.
 * Otherwise the card shows the task and the answer only.
 */
export function SubagentCard({
  call,
  result,
  running,
}: {
  call: ToolCall;
  result?: ToolMessage;
  /** Whether the parent run is still going. */
  running: boolean;
}) {
  const stream = useStreamContext();
  const subagent = call.id ? stream.getSubagent(call.id) : undefined;

  const type =
    text(call.args.subagent_type) ||
    text(subagent?.toolCall.args.subagent_type);
  const description =
    text(call.args.description) || text(subagent?.toolCall.args.description);
  const { name, icon: Icon } = describeSubagent(type || undefined);

  const status: ToolStatus = result
    ? result.status === "error"
      ? "error"
      : "done"
    : subagent?.status === "error"
      ? "error"
      : running
        ? "running"
        : "stopped";

  const innerMessages = subagent?.messages ?? [];
  const innerCalls = allToolCalls(innerMessages);
  const innerResults = indexToolResults(innerMessages);
  /** Changes with the sub-agent's visible activity; keys the waiting row to restart its clock. */
  const activityKey = `${innerCalls.length}:${innerResults.size}`;
  const waiting =
    status === "running" &&
    innerCalls.every((c) => c.id && innerResults.has(c.id));
  const waitingLabel = innerCalls.length > 0 ? "Thinking…" : "Starting…";
  const answer = result
    ? messageText(result)
    : (subagent?.result ?? text(subagent?.error));

  return (
    <div className="bg-card min-w-0 rounded-lg border shadow-xs">
      <div className="flex items-start gap-3 px-3 py-2.5">
        <span className="bg-muted text-foreground flex size-8 shrink-0 items-center justify-center rounded-md">
          <Icon className="size-4" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{name}</span>
            <span
              className={cn(
                "text-muted-foreground ml-auto flex items-center gap-1 text-xs",
                status === "error" && "text-destructive",
              )}
            >
              <StatusIcon status={status} />
              {STATUS_LABEL[status]}
            </span>
          </div>
          {description && (
            <Disclosure
              label="Task"
              preview={firstLine(description)}
            >
              <MarkdownText>{description}</MarkdownText>
            </Disclosure>
          )}
        </div>
      </div>

      {innerCalls.length > 0 ? (
        <div className="border-t px-2 py-1.5">
          <ToolSteps
            calls={innerCalls}
            results={innerResults}
            running={status === "running"}
            active={status === "running"}
          />
          {waiting && (
            <WaitingRow
              key={activityKey}
              label={waitingLabel}
              className="px-2 py-1"
            />
          )}
        </div>
      ) : (
        waiting && (
          <WaitingRow
            key={activityKey}
            label={waitingLabel}
            className="border-t px-3 py-2"
          />
        )
      )}

      {answer.trim() && (
        <div className="border-t px-3 py-2">
          <Disclosure
            label={status === "error" ? "Error" : "Answer"}
            preview={firstLine(answer)}
          >
            <div className={cn(status === "error" && "text-destructive")}>
              <MarkdownText>{answer}</MarkdownText>
            </div>
          </Disclosure>
        </div>
      )}
    </div>
  );
}
