"""The yes/no judge (``docs/EVALS.md`` §4): one question per call, a verdict and a short reason.

No 1-10 scores: every question is answered ``yes`` or ``no``. The model is the ``judge`` node of
``models.nodes``, built by ``agent.llm``; answers are cached on disk under a hash of the model,
the prompts and the inputs.
"""

import json
from collections.abc import Mapping
from enum import StrEnum
from string import Template
from typing import Literal, NamedTuple, Protocol, Self

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from omegaconf import DictConfig, OmegaConf
from pydantic import Field

from agent.agents.config import project_path, read_prompt
from agent.contracts.base import Contract
from agent.llm.costs import CostLedger
from agent.llm.factory import build_model
from evals.harness.judging.cache import AnswerCache, answer_key
from evals.harness.judging.views import ViewSettings


class Question(StrEnum):
    """A kind of question, each with its own prompt template."""

    MUST_FLAG = "must_flag"
    """Is this expected point raised by a recorded ambiguity or open point?"""
    MUST_NOT = "must_not"
    """Does the output make this forbidden claim?"""
    COVERS = "covers"
    """Which numbered notes state this expected fact?"""
    HEDGING = "hedging"
    DEFERRAL = "deferral"
    INVENTED_RULE = "invented_rule"
    RESTATING = "restating"
    INCONSISTENCY = "inconsistency"
    UNFLAGGED_GAP = "unflagged_gap"


ANTI_PATTERNS = (
    Question.HEDGING,
    Question.DEFERRAL,
    Question.INVENTED_RULE,
    Question.RESTATING,
    Question.INCONSISTENCY,
    Question.UNFLAGGED_GAP,
)
"""The six anti-patterns checked on every end-to-end study; ``yes`` means the study shows it."""


class JudgeAnswer(Contract):
    """Your answer to the question."""

    verdict: Literal["yes", "no"]
    """`yes` or `no`, answering the question exactly as asked."""
    reason: str = Field(min_length=1)
    """One or two sentences naming the passage of the output that decides the verdict."""
    notes: tuple[int, ...] = ()
    """Only when the question asks which notes state a fact: their numbers. Otherwise empty."""

    @property
    def yes(self) -> bool:
        """Whether the verdict is ``yes``."""
        return self.verdict == "yes"


class StructuredModel(Protocol):
    """A chat model bound to the ``JudgeAnswer`` schema (``with_structured_output``)."""

    def invoke(self, messages: list[BaseMessage], /) -> object:
        """Answer a conversation with a ``JudgeAnswer`` (as the model or as a dict)."""
        ...


class JudgePrompts(NamedTuple):
    """The judge's prompt texts."""

    system: str
    questions: Mapping[Question, str]
    """One template per question kind, using ``$output`` and ``$subject``."""


class Judge:
    """Asks the judge model one question at a time about a rendered output."""

    def __init__(
        self,
        model: StructuredModel,
        *,
        model_id: str,
        prompts: JudgePrompts,
        views: ViewSettings,
        cache: AnswerCache | None = None,
    ) -> None:
        """Set up a judge.

        Args:
            model: The judge model, bound to ``JudgeAnswer``.
            model_id: Model identity including generation settings, part of the cache key.
            prompts: System prompt and question templates.
            views: How outputs are rendered for the judge.
            cache: Where answers are kept; every question calls the model when ``None``.

        Raises:
            ValueError: If a question kind has no template.
        """
        missing = sorted(set(Question) - set(prompts.questions))
        if missing:
            msg = f"judge templates missing for: {', '.join(missing)}"
            raise ValueError(msg)
        self._model = model
        self._model_id = model_id
        self._system = prompts.system
        self._templates = dict(prompts.questions)
        self._cache = cache
        self.views = views
        """How outputs are rendered for this judge."""

    @classmethod
    def from_config(cls, cfg: DictConfig, ledger: CostLedger | None = None) -> Self:
        """Build the judge from ``eval.judge`` and its ``models.nodes`` entry.

        Args:
            cfg: The composed config, with the ``eval`` group.
            ledger: Keeps the judge node's cost logger, to read the judging cost.

        Returns:
            The judge, caching its answers under ``eval.judge.cache_dir``.
        """
        settings = cfg.eval.judge
        node = cfg.models.nodes[settings.model]
        model = build_model(cfg.models, settings.model, ledger)
        views = OmegaConf.to_container(settings.views, resolve=True)
        return cls(
            model.with_structured_output(JudgeAnswer, method=settings.structured_output),
            model_id=answer_key(
                (
                    json.dumps(OmegaConf.to_container(node, resolve=True), sort_keys=True),
                    str(settings.structured_output),
                )
            ),
            prompts=JudgePrompts(
                system=read_prompt(settings.system),
                questions={
                    Question(kind): read_prompt(path) for kind, path in settings.questions.items()
                },
            ),
            views=ViewSettings.model_validate(views),
            cache=AnswerCache(project_path(settings.cache_dir)),
        )

    def ask(self, question: Question, output: str, subject: str = "") -> JudgeAnswer:
        """Ask one question about an output.

        Args:
            question: The kind of question.
            output: The output, rendered for the judge.
            subject: What the question is about (expected point, claim or fact); empty for an
                anti-pattern.

        Returns:
            The answer, from the cache when the same question was asked before.
        """
        prompt = Template(self._templates[question]).substitute(output=output, subject=subject)
        schema = json.dumps(JudgeAnswer.model_json_schema(), sort_keys=True)
        key = answer_key((self._model_id, schema, self._system, prompt))
        cached = self._cache.get(key) if self._cache is not None else None
        if cached is not None:
            return JudgeAnswer.model_validate_json(cached)
        reply = self._model.invoke([SystemMessage(self._system), HumanMessage(prompt)])
        answer = JudgeAnswer.model_validate(reply)
        if self._cache is not None:
            self._cache.put(key, answer.model_dump_json())
        return answer
