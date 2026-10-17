from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract


class QuestionKind(StrEnum):
    """Who is best placed to answer a question."""

    PROGRAM_FACT = "program_fact"
    """Only the client knows (units, floor area, financing...)."""
    INTERPRETATION = "interpretation"
    """A reading of the regulation, on which the agent offers a recommendation."""


class Question(Contract):
    """A question put to the user, with suggested options and room for a free answer."""

    id: str = Field(min_length=1)
    """Short stable id, used to match the answer."""
    text: str = Field(min_length=1)
    kind: QuestionKind
    why: str = Field(min_length=1)
    """What in the study depends on the answer."""
    options: tuple[str, ...] = ()
    recommended: str | None = None
    """The option the agent would choose; one of ``options``."""

    @model_validator(mode="after")
    def _recommended_is_option(self) -> Self:
        """Reject a recommendation that is not among the options."""
        if self.recommended is not None and self.recommended not in self.options:
            msg = "recommended must be one of options"
            raise ValueError(msg)
        return self


class ClarificationRequest(Contract):
    """A batch of questions sent to the user (interrupt payload of ``ask_user``)."""

    questions: tuple[Question, ...] = Field(min_length=1)


class Answer(Contract):
    """The user's answer to one question."""

    question_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    """The chosen option, or a free answer."""


class ClarificationReply(Contract):
    """The user's answers (resume payload of ``ask_user``). Unanswered questions are omitted."""

    answers: tuple[Answer, ...]
