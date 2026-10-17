import { type ReactNode, useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type {
  ClarificationReply,
  ClarificationRequest,
  Question,
} from "@/lib/clarification";
import { ASK_USER_ICON } from "@/lib/tool-labels";

/** Sentinel choice: the user writes their own answer. */
const OTHER = "\u0000other";

type Choice = { selected: string; other: string };

const KIND_LABEL: Record<Question["kind"], string> = {
  program_fact: "Project fact",
  interpretation: "Interpretation",
};

function initialChoice(question: Question): Choice {
  return {
    selected:
      question.recommended ?? (question.options.length > 0 ? "" : OTHER),
    other: "",
  };
}

function answerOf(choice: Choice): string {
  return (choice.selected === OTHER ? choice.other : choice.selected).trim();
}

/**
 * The agent's questions (`ask_user`): one block per question with its options, the
 * recommended one preselected, and room for a free answer. Unanswered questions are left
 * to the agent, which then decides and records why.
 */
export function AskUserCard({
  request,
  onSubmit,
}: {
  request: ClarificationRequest;
  onSubmit: (reply: ClarificationReply) => void;
}) {
  const [choices, setChoices] = useState<Record<string, Choice>>(() =>
    Object.fromEntries(request.questions.map((q) => [q.id, initialChoice(q)])),
  );
  const [sent, setSent] = useState(false);
  const Icon = ASK_USER_ICON;

  const update = (id: string, patch: Partial<Choice>) =>
    setChoices((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));

  const send = (reply: ClarificationReply) => {
    setSent(true);
    onSubmit(reply);
  };

  const answers = request.questions
    .map((q) => ({ question_id: q.id, text: answerOf(choices[q.id]) }))
    .filter((a) => a.text);
  const recommendations = request.questions
    .filter((q) => q.recommended)
    .map((q) => ({ question_id: q.id, text: q.recommended as string }));
  const unanswered = request.questions.length - answers.length;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send({ answers });
      }}
      className="bg-card flex flex-col gap-4 rounded-lg border p-4 shadow-xs"
    >
      <div className="flex items-center gap-2">
        <Icon className="text-muted-foreground size-4" />
        <h3 className="text-sm font-semibold">
          {request.questions.length === 1
            ? "The agent has a question"
            : `The agent has ${request.questions.length} questions`}
        </h3>
      </div>

      <fieldset
        disabled={sent}
        className="flex flex-col gap-5"
      >
        {request.questions.map((question, index) => (
          <QuestionBlock
            key={question.id}
            index={index + 1}
            question={question}
            choice={choices[question.id]}
            onChange={(patch) => update(question.id, patch)}
          />
        ))}
      </fieldset>

      <div className="flex flex-wrap items-center gap-2 border-t pt-3">
        <p className="text-muted-foreground mr-auto text-xs">
          {unanswered > 0
            ? `${unanswered} unanswered: the agent will decide and say why.`
            : "All questions answered."}
        </p>
        {recommendations.length > 0 && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={sent}
            onClick={() => send({ answers: recommendations })}
          >
            Accept recommendations
          </Button>
        )}
        <Button
          type="submit"
          size="sm"
          disabled={sent}
        >
          {sent ? "Sent" : "Send answers"}
        </Button>
      </div>
    </form>
  );
}

function QuestionBlock({
  index,
  question,
  choice,
  onChange,
}: {
  index: number;
  question: Question;
  choice: Choice;
  onChange: (patch: Partial<Choice>) => void;
}) {
  const name = useId();
  const otherId = useId();
  const hasOptions = question.options.length > 0;

  return (
    <div
      role="group"
      aria-labelledby={`${name}-text`}
      className="flex flex-col gap-2"
    >
      <div className="flex flex-col gap-0.5">
        <p
          id={`${name}-text`}
          className="text-sm font-medium"
        >
          <span className="text-muted-foreground mr-1.5">{index}.</span>
          {question.text}
          <span className="text-muted-foreground ml-2 rounded-sm border px-1 py-px align-middle text-[0.65rem] font-normal tracking-wide uppercase">
            {KIND_LABEL[question.kind]}
          </span>
        </p>
        {question.why && (
          <p className="text-muted-foreground text-xs">{question.why}</p>
        )}
      </div>

      {hasOptions ? (
        <div className="flex flex-col gap-1.5">
          {question.options.map((option) => (
            <OptionChip
              key={option}
              name={name}
              value={option}
              checked={choice.selected === option}
              recommended={option === question.recommended}
              onSelect={() => onChange({ selected: option })}
            >
              {option}
            </OptionChip>
          ))}
          <OptionChip
            name={name}
            value={OTHER}
            checked={choice.selected === OTHER}
            onSelect={() => onChange({ selected: OTHER })}
          >
            Other…
          </OptionChip>
          {choice.selected === OTHER && (
            <Input
              id={otherId}
              autoFocus
              aria-label={`Your answer to: ${question.text}`}
              placeholder="Your answer"
              value={choice.other}
              onChange={(e) => onChange({ other: e.target.value })}
            />
          )}
        </div>
      ) : (
        <Input
          aria-label={`Your answer to: ${question.text}`}
          placeholder="Your answer (leave empty to let the agent decide)"
          value={choice.other}
          onChange={(e) => onChange({ selected: OTHER, other: e.target.value })}
        />
      )}
    </div>
  );
}

function OptionChip({
  name,
  value,
  checked,
  recommended = false,
  onSelect,
  children,
}: {
  name: string;
  value: string;
  checked: boolean;
  recommended?: boolean;
  onSelect: () => void;
  children: ReactNode;
}) {
  return (
    <label
      className={cn(
        "hover:bg-muted flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-sm transition-colors",
        "has-[:focus-visible]:ring-ring/50 has-[:focus-visible]:ring-[3px]",
        "has-[:disabled]:cursor-default has-[:disabled]:opacity-70",
        checked && "border-primary bg-muted",
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onSelect}
        className="accent-primary size-3.5 shrink-0"
      />
      <span className="min-w-0 flex-1">{children}</span>
      {recommended && (
        <span className="bg-primary text-primary-foreground shrink-0 rounded-sm px-1.5 py-px text-[0.65rem] font-medium">
          Recommended
        </span>
      )}
    </label>
  );
}
