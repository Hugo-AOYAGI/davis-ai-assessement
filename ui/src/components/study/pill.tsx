import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

const TONES = {
  neutral: "bg-muted text-foreground border-border",
  outline: "bg-transparent text-muted-foreground border-border",
  positive:
    "bg-emerald-500/10 text-emerald-700 border-emerald-500/30 dark:text-emerald-300",
  caution:
    "bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-300",
  warning:
    "bg-orange-500/10 text-orange-700 border-orange-500/30 dark:text-orange-300",
  negative: "bg-destructive/10 text-destructive border-destructive/30",
  info: "bg-sky-500/10 text-sky-700 border-sky-500/30 dark:text-sky-300",
} as const;

export type PillTone = keyof typeof TONES;

/** Small inline badge. */
export function Pill({
  tone = "neutral",
  className,
  ...props
}: ComponentProps<"span"> & { tone?: PillTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] leading-4 font-medium whitespace-nowrap [&_svg]:size-3 [&_svg]:shrink-0",
        TONES[tone],
        className,
      )}
      {...props}
    />
  );
}
