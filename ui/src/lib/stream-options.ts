import type { StreamMode } from "@langchain/langgraph-sdk";

/**
 * Options shared by every run started from the chat (new message, edit, regenerate,
 * interrupt resume).
 *
 * `updates` and `messages-tuple` from subgraphs let the client follow each sub-agent's own
 * steps live; `values` keeps the thread state (messages, todos, artifacts) in sync.
 */
export const STREAM_OPTIONS: {
  streamMode: StreamMode[];
  streamSubgraphs: boolean;
  streamResumable: boolean;
} = {
  streamMode: ["values", "messages-tuple", "updates"],
  streamSubgraphs: true,
  streamResumable: true,
};
