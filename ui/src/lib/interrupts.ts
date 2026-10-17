import type { Interrupt } from "@langchain/langgraph-sdk";
import type { useStreamContext } from "@/providers/Stream";
import { STREAM_OPTIONS } from "@/lib/stream-options";

type Stream = ReturnType<typeof useStreamContext>;

/** Continue a paused run with the user's reply (`Command(resume=value)`). */
export function resumeRun(stream: Stream, value: unknown) {
  return stream.submit(undefined, {
    ...STREAM_OPTIONS,
    command: { resume: value },
  });
}

/** The pending interrupts of the thread (the hook gives one, several, or none). */
export function pendingInterrupts(stream: Stream): Interrupt[] {
  const value = stream.interrupt as Interrupt | Interrupt[] | undefined;
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}
