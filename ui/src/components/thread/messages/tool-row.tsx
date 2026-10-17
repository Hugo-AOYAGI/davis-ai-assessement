import { useMemo, useState } from "react";
import type { ToolMessage } from "@langchain/langgraph-sdk";
import {
  ChevronRight,
  CircleCheck,
  CircleMinus,
  CircleX,
  Hourglass,
  LoaderCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolCall, ToolStatus } from "@/lib/message-blocks";
import { describeToolCall } from "@/lib/tool-labels";
import { useStreamContext } from "@/providers/Stream";

const STATUS_TEXT: Record<ToolStatus, string> = {
  running: "Running",
  done: "Done",
  error: "Failed",
  waiting: "Waiting for your answer",
  stopped: "No result",
};

export function StatusIcon({
  status,
  className,
}: {
  status: ToolStatus;
  className?: string;
}) {
  const props = {
    className: cn("size-3.5 shrink-0", className),
    "aria-label": STATUS_TEXT[status],
  };
  switch (status) {
    case "running":
      return (
        <LoaderCircle
          {...props}
          className={cn(props.className, "text-muted-foreground animate-spin")}
        />
      );
    case "done":
      return (
        <CircleCheck
          {...props}
          className={cn(props.className, "text-muted-foreground")}
        />
      );
    case "error":
      return (
        <CircleX
          {...props}
          className={cn(props.className, "text-destructive")}
        />
      );
    case "waiting":
      return (
        <Hourglass
          {...props}
          className={cn(props.className, "text-muted-foreground")}
        />
      );
    case "stopped":
      return (
        <CircleMinus
          {...props}
          className={cn(props.className, "text-muted-foreground/60")}
        />
      );
  }
}

/** One tool call on one line; click to see its arguments and result. */
export function ToolRow({
  call,
  result,
  status,
}: {
  call: ToolCall;
  result?: ToolMessage;
  status: ToolStatus;
}) {
  const [open, setOpen] = useState(false);
  const { label, icon: Icon, summary } = describeToolCall(call.name, call.args);
  return (
    <div className="min-w-0 text-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        title={STATUS_TEXT[status]}
        className="hover:bg-muted focus-visible:ring-ring/50 flex w-full min-w-0 items-center gap-2 rounded-md px-2 py-1 text-left outline-none focus-visible:ring-[3px]"
      >
        <Icon className="text-muted-foreground size-3.5 shrink-0" />
        <span
          className={cn(
            "shrink-0 font-medium",
            status === "error" && "text-destructive",
          )}
        >
          {label}
        </span>
        {summary && (
          <span className="text-muted-foreground min-w-0 truncate">
            {summary}
          </span>
        )}
        <span className="ml-auto flex shrink-0 items-center gap-1.5 pl-2">
          <StatusIcon status={status} />
          <ChevronRight
            className={cn(
              "text-muted-foreground size-3.5 transition-transform",
              open && "rotate-90",
            )}
          />
        </span>
      </button>
      {open && (
        <ToolDetails
          args={call.args}
          result={result}
        />
      )}
    </div>
  );
}

function ToolDetails({
  args,
  result,
}: {
  args: Record<string, unknown>;
  result?: ToolMessage;
}) {
  const entries = Object.entries(args);
  return (
    <div className="mt-1 mb-2 ml-[1.1rem] flex flex-col gap-3 border-l pl-3 text-xs">
      {entries.length > 0 && (
        <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-1">
          {entries.map(([key, value]) => (
            <div
              key={key}
              className="contents"
            >
              <dt className="text-muted-foreground font-mono">{key}</dt>
              <dd className="min-w-0">
                <ArgValue value={value} />
              </dd>
            </div>
          ))}
        </dl>
      )}
      {result && <ResultView result={result} />}
    </div>
  );
}

function ArgValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">—</span>;
  }
  if (typeof value === "string") {
    return <ExpandableText text={value} />;
  }
  if (typeof value === "object") {
    return (
      <ExpandableText
        text={JSON.stringify(value, null, 2)}
        mono
      />
    );
  }
  return <span>{String(value)}</span>;
}

type ContentBlock = Record<string, any>;

/** `/images/x.png` → `<apiUrl>/images/x.png`: server-relative URLs point at the agent server. */
function resolveServerUrl(url: string, apiUrl: string): string {
  if (!url.startsWith("/") || url.startsWith("//")) return url;
  return `${apiUrl.replace(/\/+$/, "")}${url}`;
}

function imageSource(block: ContentBlock): string | undefined {
  if (block.type === "image_url") {
    return typeof block.image_url === "string"
      ? block.image_url
      : block.image_url?.url;
  }
  if (block.type !== "image") return undefined;
  if (typeof block.url === "string") return block.url;
  const data = block.base64 ?? block.data;
  if (typeof data !== "string") return undefined;
  const mime = block.mime_type ?? block.mimeType ?? "image/png";
  return `data:${mime};base64,${data}`;
}

function resultParts(
  result: ToolMessage,
  apiUrl: string,
): {
  text: string;
  images: string[];
} {
  const content = result.content as unknown;
  if (typeof content === "string") return { text: content, images: [] };
  if (!Array.isArray(content)) return { text: "", images: [] };
  const blocks = content as ContentBlock[];
  return {
    text: blocks
      .filter((b) => b?.type === "text" && typeof b.text === "string")
      .map((b) => b.text as string)
      .join("\n\n"),
    images: blocks
      .map(imageSource)
      .filter((s): s is string => !!s)
      .map((s) => resolveServerUrl(s, apiUrl)),
  };
}

function prettyJson(text: string): { text: string; json: boolean } {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
    return { text, json: false };
  }
  try {
    return { text: JSON.stringify(JSON.parse(trimmed), null, 2), json: true };
  } catch {
    return { text, json: false };
  }
}

function ResultView({ result }: { result: ToolMessage }) {
  // Reading the stream context re-renders this on every stream update: keep the parsing of
  // a possibly large result to when the result itself changes.
  const { apiUrl } = useStreamContext();
  const { images, pretty } = useMemo(() => {
    const parts = resultParts(result, apiUrl);
    return { images: parts.images, pretty: prettyJson(parts.text) };
  }, [result, apiUrl]);
  const isError = result.status === "error";
  return (
    <div className="flex flex-col gap-2">
      <div className="text-muted-foreground font-medium">
        {isError ? "Error" : "Result"}
      </div>
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {images.map((src, i) => (
            <img
              key={i}
              src={src}
              alt={`Tool result image ${i + 1}`}
              loading="lazy"
              className="bg-muted max-h-64 max-w-full rounded-md border object-contain"
            />
          ))}
        </div>
      )}
      {pretty.text.trim() && (
        <ExpandableText
          text={pretty.text}
          mono={pretty.json}
          className={cn(isError && "text-destructive")}
        />
      )}
    </div>
  );
}

const PREVIEW_CHARS = 600;

/** Text cut after a few hundred characters, with a toggle to see it all. */
function ExpandableText({
  text,
  mono = false,
  className,
}: {
  text: string;
  mono?: boolean;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const long = text.length > PREVIEW_CHARS;
  const shown = long && !expanded ? `${text.slice(0, PREVIEW_CHARS)}…` : text;
  return (
    <div className="min-w-0">
      <pre
        className={cn(
          "break-words whitespace-pre-wrap",
          mono ? "bg-muted rounded-md p-2 font-mono" : "font-sans",
          className,
        )}
      >
        {shown}
      </pre>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 mt-1 rounded-sm underline-offset-2 outline-none hover:underline focus-visible:ring-[3px]"
        >
          {expanded ? "Show less" : `Show more (${text.length} characters)`}
        </button>
      )}
    </div>
  );
}
