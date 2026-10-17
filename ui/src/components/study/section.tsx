"use client";

import { useId, useState, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronRight, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** A collapsible block of the study card. Content unmounts when closed. */
export function Section({
  title,
  icon: Icon,
  meta,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon: LucideIcon;
  /** Short hint shown next to the title, e.g. a count. */
  meta?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const reduceMotion = useReducedMotion();
  const contentId = useId();
  return (
    <section className="border-t">
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((o) => !o)}
          className="hover:bg-muted/50 focus-visible:ring-ring/50 flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-medium transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-inset"
        >
          <ChevronRight
            aria-hidden
            className={cn(
              "text-muted-foreground size-4 shrink-0 transition-transform duration-200",
              open && "rotate-90",
            )}
          />
          <Icon
            aria-hidden
            className="text-muted-foreground size-4 shrink-0"
          />
          <span className="flex-1">{title}</span>
          {meta && (
            <span className="text-muted-foreground text-xs font-normal">
              {meta}
            </span>
          )}
        </button>
      </h3>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={contentId}
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: reduceMotion ? 0 : 0.2,
              ease: [0.25, 1, 0.5, 1],
            }}
            className="overflow-hidden"
          >
            <div className="px-4 pt-1 pb-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
