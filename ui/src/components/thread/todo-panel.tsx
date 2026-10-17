import { useState } from "react";
import {
  ChevronRight,
  Circle,
  CircleCheck,
  ListTodo,
  LoaderCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { TodoItem } from "@/providers/Stream";

const STATUS_ICON = {
  pending: Circle,
  in_progress: LoaderCircle,
  completed: CircleCheck,
} as const;

/** The agent's plan, above the composer; shown only when the agent keeps one. */
export function TodoPanel({ todos }: { todos: TodoItem[] | undefined }) {
  const [open, setOpen] = useState(true);
  if (!todos?.length) return null;

  const done = todos.filter((t) => t.status === "completed").length;
  const current = todos.find((t) => t.status === "in_progress");

  return (
    <div className="bg-background mx-auto w-full max-w-3xl rounded-lg border text-sm shadow-xs">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="hover:bg-muted focus-visible:ring-ring/50 flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left outline-none focus-visible:ring-[3px]"
      >
        <ListTodo className="text-muted-foreground size-4 shrink-0" />
        <span className="font-medium">Plan</span>
        <span className="text-muted-foreground">
          {done}/{todos.length} done
        </span>
        {!open && current && (
          <span className="text-muted-foreground min-w-0 truncate">
            · {current.content}
          </span>
        )}
        <ChevronRight
          className={cn(
            "text-muted-foreground ml-auto size-3.5 shrink-0 transition-transform",
            open && "rotate-90",
          )}
        />
      </button>
      {open && (
        <ul className="flex max-h-40 flex-col gap-1 overflow-y-auto border-t px-3 py-2">
          {todos.map((todo, index) => {
            const Icon = STATUS_ICON[todo.status] ?? Circle;
            return (
              <li
                key={`${index}-${todo.content}`}
                className="flex items-start gap-2"
              >
                <Icon
                  aria-label={todo.status.replace("_", " ")}
                  className={cn(
                    "text-muted-foreground mt-0.5 size-3.5 shrink-0",
                    todo.status === "in_progress" &&
                      "text-foreground animate-spin",
                  )}
                />
                <span
                  className={cn(
                    todo.status === "completed" &&
                      "text-muted-foreground line-through",
                    todo.status === "in_progress" && "font-medium",
                  )}
                >
                  {todo.content}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
