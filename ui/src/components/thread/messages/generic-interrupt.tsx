import { useState } from "react";
import type { Interrupt } from "@langchain/langgraph-sdk";
import { CirclePause } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

function describeValue(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/**
 * Fallback for a pause that is not the agent's questions: shows what the run sent and lets
 * the user reply in free text, or simply continue when the run sent nothing.
 */
export function GenericInterruptView({
  interrupt,
  onReply,
  onContinue,
}: {
  interrupt: Interrupt;
  onReply: (reply: string) => void;
  onContinue: () => void;
}) {
  const [reply, setReply] = useState("");
  const [sent, setSent] = useState(false);
  const hasValue = interrupt.value !== undefined && interrupt.value !== null;

  return (
    <div className="bg-card flex flex-col gap-3 rounded-lg border p-4 shadow-xs">
      <div className="flex items-center gap-2">
        <CirclePause className="text-muted-foreground size-4" />
        <h3 className="text-sm font-semibold">
          {hasValue
            ? "The agent is waiting for your reply"
            : "The run is paused"}
        </h3>
      </div>
      {hasValue ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!reply.trim()) return;
            setSent(true);
            onReply(reply.trim());
          }}
        >
          <pre className="bg-muted max-h-48 overflow-auto rounded-md p-2 font-mono text-xs break-words whitespace-pre-wrap">
            {describeValue(interrupt.value)}
          </pre>
          <Textarea
            aria-label="Your reply"
            placeholder="Your reply"
            value={reply}
            disabled={sent}
            onChange={(e) => setReply(e.target.value)}
          />
          <div className="flex justify-end">
            <Button
              type="submit"
              size="sm"
              disabled={sent || !reply.trim()}
            >
              Reply
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex justify-end">
          <Button
            size="sm"
            disabled={sent}
            onClick={() => {
              setSent(true);
              onContinue();
            }}
          >
            Continue
          </Button>
        </div>
      )}
    </div>
  );
}
