/**
 * Questions the agent puts to the user (`ask_user`), as sent in the interrupt value under
 * `clarification`, and the answers it accepts back.
 */

export type QuestionKind = "program_fact" | "interpretation";

export type Question = {
  id: string;
  text: string;
  kind: QuestionKind;
  /** What in the study depends on the answer. */
  why: string;
  options: string[];
  /** The option the agent would choose. */
  recommended: string | null;
};

export type ClarificationRequest = { questions: Question[] };

/** Resume value of `ask_user`; unanswered questions are left out. */
export type ClarificationReply = {
  answers: { question_id: string; text: string }[];
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);

function readQuestion(value: unknown): Question | null {
  if (!isRecord(value)) return null;
  const { id, text, kind, why, options, recommended } = value;
  if (typeof id !== "string" || typeof text !== "string") return null;
  const choices = Array.isArray(options)
    ? options.filter((o): o is string => typeof o === "string")
    : [];
  return {
    id,
    text,
    kind: kind === "program_fact" ? "program_fact" : "interpretation",
    why: typeof why === "string" ? why : "",
    options: choices,
    recommended:
      typeof recommended === "string" && choices.includes(recommended)
        ? recommended
        : null,
  };
}

/** The questions of an `ask_user` interrupt value, or null for any other interrupt. */
export function readClarification(value: unknown): ClarificationRequest | null {
  if (!isRecord(value) || !isRecord(value.clarification)) return null;
  const raw = value.clarification.questions;
  if (!Array.isArray(raw)) return null;
  const questions = raw.map(readQuestion).filter((q): q is Question => !!q);
  return questions.length > 0 ? { questions } : null;
}
