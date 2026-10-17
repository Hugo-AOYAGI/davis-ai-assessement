"use client";

import { useId, useState } from "react";
import {
  CircleAlert,
  CircleCheck,
  Database,
  ImageIcon,
  type LucideIcon,
} from "lucide-react";
import type { Citation, CitationCheck } from "@/lib/study-types";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useCitationCheck } from "./citation-checks";
import { docLabel, formatNumber } from "./format";

type Status = "verified" | "unverified" | "raster" | "geometric";

function statusOf(citation: Citation, check?: CitationCheck): Status {
  if (citation.source_kind === "geometric") return "geometric";
  if (!check) return "unverified";
  if (!check.text_verifiable) return "raster";
  return check.verified ? "verified" : "unverified";
}

const STATUS: Record<
  Status,
  { icon: LucideIcon; tone: string; label: string }
> = {
  verified: {
    icon: CircleCheck,
    tone: "text-emerald-600 dark:text-emerald-400",
    label: "Quote verified in the document",
  },
  unverified: {
    icon: CircleAlert,
    tone: "text-amber-600 dark:text-amber-400",
    label: "Quote not found in the document",
  },
  raster: {
    icon: ImageIcon,
    tone: "text-muted-foreground",
    label: "Image-only document: quote not text-checked",
  },
  geometric: {
    icon: Database,
    tone: "text-muted-foreground",
    label: "Public data source",
  },
};

function chipLabel(c: Citation) {
  return c.page ? `${docLabel(c.doc)} · p. ${c.page}` : docLabel(c.doc);
}

function CheckDetail({ check }: { check?: CitationCheck }) {
  if (!check || !check.text_verifiable) return null;
  const score = `${formatNumber(check.score * 100)} % match`;
  const moved = check.matched_page ? `, best on p. ${check.matched_page}` : "";
  return (
    <span>
      {score}
      {moved}
    </span>
  );
}

function CitationChip({
  citation,
  expanded,
  onToggle,
  panelId,
}: {
  citation: Citation;
  expanded: boolean;
  onToggle: () => void;
  panelId: string;
}) {
  const check = useCitationCheck(citation);
  const status = STATUS[statusOf(citation, check)];
  const Icon = status.icon;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={panelId}
          aria-label={`${chipLabel(citation)}${citation.article ? `, ${citation.article}` : ""}. ${status.label}`}
          className={cn(
            "bg-background hover:bg-accent focus-visible:ring-ring/50 inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] leading-4 font-medium transition-colors outline-none focus-visible:ring-[3px]",
            expanded && "bg-accent",
          )}
        >
          <Icon
            aria-hidden
            className={cn("size-3", status.tone)}
          />
          {chipLabel(citation)}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="max-w-xs text-left"
      >
        {citation.article && (
          <p className="font-semibold">{citation.article}</p>
        )}
        <p className="line-clamp-4">“{citation.quote}”</p>
        <p className="mt-1 opacity-70">{status.label}</p>
      </TooltipContent>
    </Tooltip>
  );
}

function QuotePanel({ citation, id }: { citation: Citation; id: string }) {
  const check = useCitationCheck(citation);
  const status = STATUS[statusOf(citation, check)];
  const Icon = status.icon;
  return (
    <figure
      id={id}
      className="bg-muted/50 mt-1.5 rounded-md border px-3 py-2 text-xs"
    >
      <blockquote className="border-border border-l-2 pl-2 italic">
        {citation.quote}
      </blockquote>
      <figcaption className="text-muted-foreground mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
        <span className="text-foreground font-medium">
          {chipLabel(citation)}
          {citation.article && ` · ${citation.article}`}
        </span>
        <span className={cn("inline-flex items-center gap-1", status.tone)}>
          <Icon
            aria-hidden
            className="size-3"
          />
          {status.label}
        </span>
        <CheckDetail check={check} />
      </figcaption>
    </figure>
  );
}

/** Citation chips; hover shows the quote, click pins it below the chips. */
export function CitationList({
  citations,
  className,
}: {
  citations: Citation[];
  className?: string;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const baseId = useId();
  if (citations.length === 0) return null;
  const panelId = `${baseId}-quote`;
  return (
    <div className={className}>
      <div className="flex flex-wrap gap-1">
        {citations.map((citation, i) => (
          <CitationChip
            key={i}
            citation={citation}
            expanded={open === i}
            onToggle={() => setOpen(open === i ? null : i)}
            panelId={panelId}
          />
        ))}
      </div>
      {open !== null && citations[open] && (
        <QuotePanel
          citation={citations[open]}
          id={panelId}
        />
      )}
    </div>
  );
}
