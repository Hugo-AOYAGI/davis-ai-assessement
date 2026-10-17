import { parsePartialJson } from "@langchain/core/output_parsers";
import type { AIMessage, Message, ToolMessage } from "@langchain/langgraph-sdk";
import { DO_NOT_RENDER_ID_PREFIX } from "@/lib/ensure-tool-responses";
import { getContentString } from "@/components/thread/utils";

/** A tool call as rendered by the chat (args always an object). */
export type ToolCall = {
  id?: string;
  name: string;
  args: Record<string, unknown>;
};

/** Tool results of a conversation, by tool call id. */
export type ToolResults = Map<string, ToolMessage>;

/** One rendered unit of the conversation. */
export type Block =
  | { kind: "human"; key: string; message: Message }
  /** An AI message with text and/or sub-agent calls. */
  | { kind: "ai"; key: string; message: AIMessage }
  /** Consecutive AI messages that only call tools, folded into one group. */
  | { kind: "steps"; key: string; calls: ToolCall[] }
  /** Where the verified study renders, right after it was accepted. */
  | { kind: "study"; key: string };

export const SUBAGENT_TOOL = "task";
export const STUDY_TOOL = "submit_study";

/** Text of a ToolMessage (or any message), joining its text blocks. */
export function messageText(message: Pick<Message, "content">): string {
  return getContentString(message.content);
}

/** Whether a `submit_study` result says the study was stored. */
export function isStudyAccepted(result: ToolMessage | undefined): boolean {
  return (
    !!result &&
    result.status !== "error" &&
    messageText(result).trimStart().startsWith("study accepted")
  );
}

/**
 * Tool calls of an AI message. While Anthropic streams a tool call, `tool_calls` may still
 * have empty args: the partial `tool_use` content blocks are parsed instead.
 */
export function toolCallsOf(message: AIMessage): ToolCall[] {
  const calls = (message.tool_calls ?? []).map((tc) => ({
    id: tc.id,
    name: tc.name,
    args: (tc.args ?? {}) as Record<string, unknown>,
  }));
  if (calls.some((tc) => Object.keys(tc.args).length > 0)) return calls;
  const streamed = Array.isArray(message.content)
    ? parseStreamedToolUse(message.content)
    : [];
  return streamed.length > 0 ? streamed : calls;
}

function parseStreamedToolUse(content: unknown[]): ToolCall[] {
  return content
    .filter(
      (c): c is Record<string, any> =>
        !!c &&
        typeof c === "object" &&
        (c as { type?: unknown }).type === "tool_use" &&
        !!(c as { id?: unknown }).id,
    )
    .map((block) => {
      let args: Record<string, unknown> = {};
      if (typeof block.input === "string") {
        try {
          args = parsePartialJson(block.input) ?? {};
        } catch {
          // Incomplete JSON: keep empty args until more arrives.
        }
      } else if (block.input && typeof block.input === "object") {
        args = block.input;
      }
      return { id: block.id, name: block.name ?? "", args };
    });
}

/** Index the tool results of a message list by tool call id. */
export function indexToolResults(messages: Message[]): ToolResults {
  const results: ToolResults = new Map();
  for (const message of messages) {
    if (message.type === "tool" && message.tool_call_id) {
      results.set(message.tool_call_id, message);
    }
  }
  return results;
}

/** All tool calls made in a message list (used for sub-agent inner steps). */
export function allToolCalls(messages: Message[]): ToolCall[] {
  return messages.flatMap((m) => (m.type === "ai" ? toolCallsOf(m) : []));
}

/**
 * Group a conversation into blocks: human messages, AI messages with text or sub-agent
 * calls, and runs of tool-only AI messages folded into one "steps" block. Tool messages are
 * not blocks: each is shown on the row of the call it answers.
 */
export function buildBlocks(
  messages: Message[],
  results: ToolResults,
): Block[] {
  const blocks: Block[] = [];
  let pending: { key: string; calls: ToolCall[] } | null = null;

  const flush = () => {
    if (pending && pending.calls.length > 0) {
      blocks.push({ kind: "steps", ...pending });
    }
    pending = null;
  };

  messages.forEach((message, index) => {
    if (message.id?.startsWith(DO_NOT_RENDER_ID_PREFIX)) return;
    const key = message.id ?? `${message.type}-${index}`;
    if (message.type === "human") {
      flush();
      blocks.push({ kind: "human", key, message });
      return;
    }
    if (message.type !== "ai") return;

    const calls = toolCallsOf(message);
    const hasText = messageText(message).trim().length > 0;
    const callsSubagent = calls.some((tc) => tc.name === SUBAGENT_TOOL);
    const studyAccepted = calls.some(
      (tc) =>
        tc.name === STUDY_TOOL &&
        !!tc.id &&
        isStudyAccepted(results.get(tc.id)),
    );

    if (hasText || callsSubagent) {
      flush();
      blocks.push({ kind: "ai", key, message });
    } else if (calls.length > 0) {
      pending ??= { key, calls: [] };
      pending.calls.push(...calls);
    } else {
      return;
    }

    if (studyAccepted) {
      flush();
      blocks.push({ kind: "study", key: `study-${key}` });
    }
  });
  flush();
  return blocks;
}

export type ToolStatus = "running" | "done" | "error" | "waiting" | "stopped";

/**
 * Status of a call: its result decides, else whether the run is still going or paused on a
 * question to the user.
 */
export function toolStatus(
  result: ToolMessage | undefined,
  { running, waiting }: { running: boolean; waiting: boolean },
): ToolStatus {
  if (result) return result.status === "error" ? "error" : "done";
  if (waiting) return "waiting";
  return running ? "running" : "stopped";
}

/** First non-empty line of a text, without Markdown emphasis or heading marks. */
export function firstLine(text: string): string {
  const line = text.split("\n").find((l) => l.trim()) ?? "";
  return line
    .replace(/^#+\s*/, "")
    .replace(/[*_`]/g, "")
    .trim();
}
