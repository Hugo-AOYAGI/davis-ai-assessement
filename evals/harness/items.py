"""Eval item schema (``evals/README.md``§2) and the YAML loader of a dataset directory."""

import re
from collections.abc import Collection
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import Discriminator, Field, Tag, ValidationError, model_validator

from agent.contracts.base import Contract
from evals.harness.extract import parse_key
from evals.harness.refusals import ExpectedRefusal

type Scalar = str | int | float | bool | None
type Value = Scalar | tuple[Scalar, ...]
type Source = Literal["ban", "cadastre", "gpu_2021", "geometry", "hand"]
"""Oracle an expected value comes from."""

_PLACEHOLDER = re.compile(r'"(<[^<>"]*>)"')
"""A JSON string value of the form ``<...>``: an answer still to be filled in."""
_LABEL = r"^[a-z][a-z0-9_]*$"


class Level(StrEnum):
    """The unit under test."""

    SURVEYOR = "surveyor"
    ZONING = "zoning"
    DOC = "doc"
    E2E = "e2e"


class Status(StrEnum):
    """Review state of an item; only verified items are scored."""

    DRAFT = "draft"
    VERIFIED = "verified"
    DROPPED = "dropped"


class SurveyorInput(Contract):
    """The surveyor's task: the address, and the program when the orchestrator gives it."""

    address: str = Field(min_length=1)
    program: str | None = None


class ZoningInput(Contract):
    """The zoning analyst's task: address, program and the parcel ids of the site."""

    address: str = Field(min_length=1)
    parcel_ids: tuple[str, ...] = Field(min_length=1)
    program: str = Field(min_length=1)


class DocContext(Contract):
    """What the orchestrator already knows, written into a doc_analyst task's ``context``."""

    zone: str = Field(min_length=1)
    legend_items: tuple[str, ...] = ()
    """Legend items that apply to the site, with their exact labels."""
    parcel_ids: tuple[str, ...] = ()
    program: str = Field(min_length=1)
    facts: tuple[str, ...] = ()
    """Known program facts."""


class DocInput(Contract):
    """A doc_analyst task: label, aim, documents, topics and context."""

    label: str = Field(pattern=_LABEL)
    aim: str = Field(min_length=1)
    documents: tuple[str, ...] = ()
    """Corpus document ids it may read; empty for every document."""
    topics: tuple[str, ...] = ()
    context: DocContext


class E2EInput(Contract):
    """The end-to-end request: address, program and program facts standing in for ask_user."""

    address: str = Field(min_length=1)
    program: str = Field(min_length=1)
    facts: tuple[str, ...] = ()


type ItemInput = SurveyorInput | ZoningInput | DocInput | E2EInput

_INPUTS: dict[Level, type[ItemInput]] = {
    Level.SURVEYOR: SurveyorInput,
    Level.ZONING: ZoningInput,
    Level.DOC: DocInput,
    Level.E2E: E2EInput,
}


class Evidence(Contract):
    """Where an expected answer lives in the corpus."""

    doc: str = Field(min_length=1)
    page: int = Field(ge=1)
    """1-based PDF page index."""
    quote: str | None = None


class KeyFact(Contract):
    """An expected value at a key of the output, scored in code."""

    key: str = Field(min_length=1)
    expect: Value = None
    any_of: tuple[Scalar, ...] | None = None
    expect_none_of: tuple[Scalar, ...] | None = None
    at_least: int | None = Field(default=None, ge=0)
    present: tuple[str, ...] | None = None
    absent: tuple[str, ...] | None = None
    tolerance: float | None = Field(default=None, ge=0)
    """Relative tolerance on numbers, for ``expect`` and ``any_of``."""
    critical: bool = False
    source: Source | None = None
    evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def _one_expectation(self) -> Self:
        """Require a valid key and one expectation (``present`` and ``absent`` count as one)."""
        given = self.model_fields_set
        kinds = {"expect", "any_of", "expect_none_of", "at_least"} & given
        if {"present", "absent"} & given:
            kinds.add("present/absent")
        if len(kinds) != 1:
            found = ", ".join(sorted(kinds)) or "none"
            msg = f"fact {self.key!r} needs exactly one expectation, found: {found}"
            raise ValueError(msg)
        if self.tolerance is not None and not {"expect", "any_of"} & given:
            msg = f"fact {self.key!r}: tolerance only applies to expect or any_of"
            raise ValueError(msg)
        parse_key(self.key)
        return self


class StatementFact(Contract):
    """An expected statement, matched to doc_analyst notes by the judge."""

    statement: str = Field(min_length=1)
    critical: bool = False
    evidence: tuple[Evidence, ...] = ()


def _fact_kind(value: object) -> str:
    """Tell a statement fact from a key fact, for the discriminated union."""
    if isinstance(value, StatementFact) or (isinstance(value, dict) and "statement" in value):
        return "statement"
    return "key"


type Fact = Annotated[
    Annotated[KeyFact, Tag("key")] | Annotated[StatementFact, Tag("statement")],
    Discriminator(_fact_kind),
]


class Item(Contract):
    """One eval item: an input for the unit under test and the expected answers."""

    id: str = Field(min_length=1)
    level: Level
    tests: str = Field(min_length=1)
    """One line: what the item catches."""
    status: Status
    built_by: str = Field(min_length=1)
    input: ItemInput
    facts: tuple[Fact, ...] = ()
    must_flag: tuple[str, ...] = ()
    must_not: tuple[str, ...] = ()
    from_items: tuple[str, ...] = ()
    """Component items an end-to-end item's facts are composed from."""
    expected_refusal: ExpectedRefusal | None = None

    @model_validator(mode="before")
    @classmethod
    def _input_for_level(cls, data: object) -> object:
        """Validate ``input`` against the input model of the item's level."""
        if isinstance(data, dict) and data.get("level") in _INPUTS and "input" in data:
            model = _INPUTS[Level(data["level"])]
            return {**data, "input": model.model_validate(data["input"])}
        return data

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Check level-specific fields and, on verified items, unfilled placeholders."""
        if self.from_items and self.level is not Level.E2E:
            msg = "from_items is only for e2e items"
            raise ValueError(msg)
        if self.expected_refusal is not None and (
            self.level is not Level.SURVEYOR or self.facts or self.must_flag or self.must_not
        ):
            raise ValueError(
                "expected_refusal requires a surveyor item without facts or judge assertions"
            )
        if self.level is not Level.DOC and any(isinstance(f, StatementFact) for f in self.facts):
            msg = "statement facts are only for doc items"
            raise ValueError(msg)
        if self.status is Status.VERIFIED:
            placeholders = sorted(set(_PLACEHOLDER.findall(self.model_dump_json())))
            if placeholders:
                msg = f"a verified item has unfilled placeholders: {', '.join(placeholders)}"
                raise ValueError(msg)
        return self


class ItemError(ValueError):
    """An item file that does not parse or validate."""


def load_item(path: Path) -> Item:
    """Read a YAML item, raising ``ItemError`` with its path on invalid content."""
    try:
        return Item.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (yaml.YAMLError, ValidationError) as error:
        msg = f"invalid eval item {path}: {error}"
        raise ItemError(msg) from error


def load_items(directory: Path, *, statuses: Collection[Status] = (Status.VERIFIED,)) -> list[Item]:
    """Load the items of a dataset directory, one YAML file per item, sorted by file name.

    Every file is validated, whatever its status, so a broken draft is reported too.

    Args:
        directory: Directory of ``*.yaml`` item files (sub-directories are not read).
        statuses: Statuses of the items returned.

    Returns:
        The items whose status is in ``statuses``.

    Raises:
        ItemError: Naming the file, for the first invalid item, or when two files hold the
            same item id.
    """
    items = [load_item(path) for path in sorted(directory.glob("*.yaml"))]
    ids = [item.id for item in items]
    duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
    if duplicates:
        msg = f"duplicate item ids in {directory}: {', '.join(duplicates)}"
        raise ItemError(msg)
    return [item for item in items if item.status in statuses]
