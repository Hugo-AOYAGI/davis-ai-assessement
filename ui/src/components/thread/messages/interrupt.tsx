import { useStreamContext } from "@/providers/Stream";
import { STREAM_OPTIONS } from "@/lib/stream-options";
import { readClarification } from "@/lib/clarification";
import { pendingInterrupts, resumeRun } from "@/lib/interrupts";
import { AskUserCard } from "./ask-user-card";
import { GenericInterruptView } from "./generic-interrupt";

/** What the run is waiting for: the agent's questions, or any other pause. */
export function InterruptView() {
  const stream = useStreamContext();
  const interrupts = pendingInterrupts(stream);
  // Once resumed, the card goes away; it comes back fresh if the run pauses again.
  if (interrupts.length === 0 || stream.isLoading) return null;

  for (const interrupt of interrupts) {
    const request = readClarification(interrupt.value);
    if (request) {
      return (
        <AskUserCard
          key={interrupt.id ?? "ask-user"}
          request={request}
          onSubmit={(reply) => resumeRun(stream, reply)}
        />
      );
    }
  }
  const [first] = interrupts;
  return (
    <GenericInterruptView
      key={first.id ?? "interrupt"}
      interrupt={first}
      onReply={(reply) => resumeRun(stream, reply)}
      onContinue={() => stream.submit(undefined, STREAM_OPTIONS)}
    />
  );
}
