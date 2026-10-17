import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
import { useStream } from "@langchain/langgraph-sdk/react";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { Fragment } from "react/jsx-runtime";
import { useQueryState, parseAsBoolean } from "nuqs";
import { cn } from "@/lib/utils";
import {
  messageText,
  SUBAGENT_TOOL,
  toolCallsOf,
  type ToolResults,
} from "@/lib/message-blocks";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { useArtifact } from "../artifact";
import { ToolSteps } from "./tool-steps";
import { SubagentCard } from "./subagent-card";

function CustomComponent({
  message,
  thread,
}: {
  message: Message;
  thread: ReturnType<typeof useStreamContext>;
}) {
  const artifact = useArtifact();
  const { values } = useStreamContext();
  const customComponents = values.ui?.filter(
    (ui) => ui.metadata?.message_id === message.id,
  );

  if (!customComponents?.length) return null;
  return (
    <Fragment key={message.id}>
      {customComponents.map((customComponent) => (
        <LoadExternalComponent
          key={customComponent.id}
          stream={thread as unknown as ReturnType<typeof useStream>}
          message={customComponent}
          meta={{ ui: customComponent, artifact }}
        />
      ))}
    </Fragment>
  );
}

/**
 * An AI message: its text, its tool calls as compact rows, and its delegations to
 * sub-agents as cards.
 */
export function AssistantMessage({
  message,
  results,
  isLoading,
  active,
  waiting,
  handleRegenerate,
}: {
  message: AIMessage;
  results: ToolResults;
  isLoading: boolean;
  /** Whether the run is currently working on this message's calls. */
  active: boolean;
  /** Whether the run is paused on a question to the user. */
  waiting: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
}) {
  const contentString = messageText(message);
  const [hideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const thread = useStreamContext();
  const meta = thread.getMessagesMetadata(message);
  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;

  const calls = toolCallsOf(message);
  const subagentCalls = calls.filter((tc) => tc.name === SUBAGENT_TOOL);
  const otherCalls = calls.filter((tc) => tc.name !== SUBAGENT_TOOL);

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full min-w-0 flex-col gap-2">
        {contentString.length > 0 && (
          <div className="py-1">
            <MarkdownText>{contentString}</MarkdownText>
          </div>
        )}

        {!hideToolCalls && (
          <ToolSteps
            calls={otherCalls}
            results={results}
            running={isLoading}
            waiting={waiting}
            active={active}
          />
        )}

        {subagentCalls.length > 0 && (
          <div className="flex flex-col gap-2">
            {subagentCalls.map((call, index) => (
              <SubagentCard
                key={call.id || index}
                call={call}
                result={call.id ? results.get(call.id) : undefined}
                running={isLoading}
              />
            ))}
          </div>
        )}

        <CustomComponent
          message={message}
          thread={thread}
        />

        {contentString.length > 0 && (
          <div
            className={cn(
              "mr-auto flex items-center gap-2 transition-opacity",
              "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
            )}
          >
            <BranchSwitcher
              branch={meta?.branch}
              branchOptions={meta?.branchOptions}
              onSelect={(branch) => thread.setBranch(branch)}
              isLoading={isLoading}
            />
            <CommandBar
              content={contentString}
              isLoading={isLoading}
              isAiMessage={true}
              handleRegenerate={() => handleRegenerate(parentCheckpoint)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export function AssistantMessageLoading() {
  return (
    <div className="mr-auto flex items-start gap-2">
      <div className="bg-muted flex h-8 items-center gap-1 rounded-2xl px-4 py-2">
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_0.5s_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_1s_infinite] rounded-full"></div>
      </div>
    </div>
  );
}
