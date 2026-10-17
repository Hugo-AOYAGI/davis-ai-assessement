from collections.abc import Mapping

from langchain.agents.middleware.human_in_the_loop import HITLRequest
from pydantic import JsonValue, ValidationError

from agent.contracts.inputs.clarification import (
    Answer,
    ClarificationReply,
    ClarificationRequest,
    Question,
)

ACTION_NAME = "ask_user"
"""Action name of the human-in-the-loop request, and name of the tool raising it."""

type Reply = ClarificationReply | str
"""What the user sent back: answers by question id, or one free text for all questions."""

INTRO = (
    "**Questions from the agent.** Answer in each field (prefilled with the recommended "
    "option, if any), approve to accept the recommendations, or reject with a message to "
    "answer in free text."
)

FROM_USER = (
    "These answers come from the user: an ambiguity they settle is recorded with resolved_by: user."
)
CHOOSE = (
    "choose the answer yourself, justify it, and record it as an ambiguity with resolved_by: agent."
)


class ClarificationInterrupt(HITLRequest):
    """Interrupt value of ``ask_user``: a human-in-the-loop request plus the questions."""

    clarification: dict[str, JsonValue]
    """The ``ClarificationRequest`` as JSON, for programmatic clients."""


def interrupt_payload(request: ClarificationRequest) -> ClarificationInterrupt:
    """Build the ``interrupt`` value of ``ask_user``.

    It is a langchain human-in-the-loop request (``HITLRequest``), which chat UIs render as one
    editable field per question id, prefilled with the recommended option, plus the
    ``clarification`` key holding the ``ClarificationRequest`` for programmatic clients.

    Args:
        request: The questions.

    Returns:
        The JSON-serialisable payload.
    """
    return {
        "action_requests": [
            {
                "name": ACTION_NAME,
                "args": {question.id: question.recommended or "" for question in request.questions},
                "description": describe_questions(request),
            }
        ],
        "review_configs": [
            {"action_name": ACTION_NAME, "allowed_decisions": ["approve", "edit", "reject"]}
        ],
        "clarification": request.model_dump(mode="json"),
    }


def describe_questions(request: ClarificationRequest) -> str:
    """Render the questions as Markdown for the user.

    Args:
        request: The questions.

    Returns:
        One paragraph per question: text, reason, options and recommendation.
    """
    return "\n\n".join([INTRO, *(_describe_question(question) for question in request.questions)])


def read_reply(request: ClarificationRequest, resume: object) -> Reply | None:
    """Read the value the run was resumed with.

    Accepted: a ``ClarificationReply`` as JSON; a human-in-the-loop response
    (``{"decisions": [decision]}``) where ``approve`` takes the recommended options, ``edit``
    takes the non-empty fields of ``edited_action.args`` and ``reject`` (or ``respond``) takes
    its ``message`` as free text; or a plain string, taken as free text.

    Args:
        request: The questions that were asked.
        resume: The resume value.

    Returns:
        The reply, or ``None`` when the value has none of the accepted shapes.
    """
    if isinstance(resume, str):
        return _free_text(resume)
    if not isinstance(resume, Mapping):
        return None
    if "answers" in resume:
        try:
            return ClarificationReply.model_validate(resume)
        except ValidationError:
            return None
    decisions = resume.get("decisions")
    if isinstance(decisions, list) and len(decisions) == 1 and isinstance(decisions[0], Mapping):
        return _from_decision(request, decisions[0])
    return None


def describe_reply(request: ClarificationRequest, reply: Reply | None) -> str:
    """Write the tool result the model reads: each answer, and what was left unanswered.

    Args:
        request: The questions that were asked.
        reply: The reply read by ``read_reply``.

    Returns:
        The text of the tool message.
    """
    if reply is None:
        return f"The user's reply could not be read. For every question, {CHOOSE}"
    if isinstance(reply, str):
        return (
            f"The user replied in free text to all the questions. {FROM_USER}\n\n{reply}\n\n"
            f"For any question this reply does not settle, {CHOOSE}"
        )
    answers = {answer.question_id: answer.text for answer in reply.answers}
    asked = [question.id for question in request.questions]
    lines = [f"- {qid}: {answers[qid]}" for qid in asked if qid in answers]
    missing = [qid for qid in asked if qid not in answers]
    parts: list[str] = []
    if lines:
        parts.append("The user answered:\n" + "\n".join(lines) + f"\n\n{FROM_USER}")
    if missing:
        parts.append(f"Left unanswered by the user: {', '.join(missing)}. For each, {CHOOSE}")
    return "\n\n".join(parts)


def _describe_question(question: Question) -> str:
    """Render one question as a Markdown paragraph."""
    lines = [
        f"**{question.id}** ({question.kind.value.replace('_', ' ')}): {question.text}",
        f"Why: {question.why}",
    ]
    if question.options:
        lines.append(f"Options: {' / '.join(question.options)}")
    if question.recommended is not None:
        lines.append(f"Recommended: {question.recommended}")
    return "  \n".join(lines)


def _free_text(text: str) -> Reply:
    """Take a free-text reply; an empty one leaves every question unanswered."""
    return text.strip() or ClarificationReply(answers=())


def _from_decision(
    request: ClarificationRequest, decision: Mapping[object, object]
) -> Reply | None:
    """Read one human-in-the-loop decision."""
    match decision.get("type"):
        case "approve":
            return ClarificationReply(
                answers=tuple(
                    Answer(question_id=question.id, text=question.recommended)
                    for question in request.questions
                    if question.recommended is not None
                )
            )
        case "edit":
            action = decision.get("edited_action")
            args = action.get("args") if isinstance(action, Mapping) else None
            return _from_fields(request, args) if isinstance(args, Mapping) else None
        case "reject" | "respond":
            message = decision.get("message")
            return _free_text(message if isinstance(message, str) else "")
        case _:
            return None


def _from_fields(request: ClarificationRequest, fields: Mapping[object, object]) -> Reply:
    """Take the non-empty answer fields edited by the user."""
    texts = {
        question.id: str(value).strip()
        for question in request.questions
        if isinstance(value := fields.get(question.id), str | int | float)
    }
    return ClarificationReply(
        answers=tuple(Answer(question_id=qid, text=text) for qid, text in texts.items() if text)
    )
