import { ReactNode, useId, useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A labelled section that opens on click. When closed, an optional one-line preview of the
 * content follows the label.
 */
export function Disclosure({
  label,
  preview,
  defaultOpen = false,
  className,
  children,
}: {
  label: ReactNode;
  preview?: string;
  defaultOpen?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = useId();
  return (
    <div className={cn("min-w-0 text-sm", className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((o) => !o)}
        className="hover:text-foreground text-muted-foreground focus-visible:ring-ring/50 flex w-full min-w-0 items-center gap-1 rounded-sm text-left outline-none focus-visible:ring-[3px]"
      >
        <ChevronRight
          className={cn(
            "size-3.5 shrink-0 transition-transform",
            open && "rotate-90",
          )}
        />
        <span className="text-foreground shrink-0 font-medium">{label}</span>
        {!open && preview && (
          <span className="min-w-0 truncate">{preview}</span>
        )}
      </button>
      {open && (
        <div
          id={contentId}
          className="mt-1 pl-[1.125rem]"
        >
          {children}
        </div>
      )}
    </div>
  );
}
