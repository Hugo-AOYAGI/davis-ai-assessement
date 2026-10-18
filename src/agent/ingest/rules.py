import re
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agent.contracts.base import Contract

GROUPS = frozenset({"number", "zone", "article", "sector", "title"})
"""Named groups a heading pattern may capture."""


class Line(Contract):
    """One visual line of a PDF page, with the typography of its first non-blank span."""

    page: int = Field(ge=1)
    """1-based PDF page index."""
    text: str
    """Spans concatenated, trailing blanks removed."""
    y0: float
    """Top of the line, in points from the top of the page."""
    size: float
    """Font size of the first non-blank span."""
    font: str
    """Font name of the first non-blank span."""
    lead: str
    """Text of the leading spans sharing the first non-blank span's font."""


class HeadingRule(Contract):
    """A regex rule recognising one heading level (titre, zone, article, term...)."""

    level: str = Field(min_length=1)
    """Level opened by a match; one of ``SplitterConfig.levels``."""
    pattern: str
    """Regex matched (``re.match``) on the stripped field; named groups among ``GROUPS``."""
    scope: Literal["body", "header"] = "body"
    """Lines the rule reads: page body, or the running-header band (once per page)."""
    field: Literal["text", "lead"] = "text"
    """Matched part of the line: the whole text or its leading same-font spans."""
    inside: str | None = None
    """``level`` or ``level/key``: the rule applies only while such a section is open."""
    font: str | None = None
    """Regex searched in the line's font name."""
    min_size: float | None = None
    max_size: float | None = None
    key: str | None = None
    """Format template over the groups giving the section key; defaults to the title."""
    title: str | None = None
    """Format template over the groups giving the title; defaults to the matched field."""
    continuation: str | None = None
    """Regex for following body lines appended to the title (wrapped headings)."""
    continuation_min_size: float | None = None
    """Minimum font size of continuation lines; defaults to ``min_size``."""

    @field_validator("pattern")
    @classmethod
    def _check_groups(cls, pattern: str) -> str:
        """Reject patterns that do not compile or capture unknown groups.

        Args:
            pattern: The configured regex.

        Returns:
            The pattern unchanged.

        Raises:
            ValueError: If a group name is not in ``GROUPS``.
        """
        unknown = set(re.compile(pattern).groupindex) - GROUPS
        if unknown:
            msg = f"unknown groups {sorted(unknown)} in {pattern!r}; allowed: {sorted(GROUPS)}"
            raise ValueError(msg)
        return pattern

    def styled(self, line: Line, min_size: float | None = None) -> bool:
        """Tell whether a line has the rule's font and size.

        Args:
            line: Candidate line.
            min_size: Lower size bound replacing ``self.min_size`` when given.

        Returns:
            True if the font regex and size bounds (when set) all accept the line.
        """
        floor = self.min_size if min_size is None else min_size
        return (
            (self.font is None or re.search(self.font, line.font) is not None)
            and (floor is None or line.size >= floor)
            and (self.max_size is None or line.size <= self.max_size)
        )

    def match(self, line: Line) -> re.Match[str] | None:
        """Match the rule's pattern on the line, ignoring typography.

        Args:
            line: Candidate line.

        Returns:
            The match, or ``None``.
        """
        return re.match(self.pattern, self.value(line))

    def value(self, line: Line) -> str:
        """Return the stripped field of a line that the rule reads.

        Args:
            line: Any line.

        Returns:
            Its text or lead, stripped.
        """
        return (line.lead if self.field == "lead" else line.text).strip()

    def continues(self, line: Line) -> bool:
        """Tell whether a line continues a wrapped heading of this rule.

        Args:
            line: The body line following the heading (or its previous continuation).

        Returns:
            True if it has the rule's style and matches ``continuation``.
        """
        return (
            self.continuation is not None
            and self.styled(line, self.continuation_min_size)
            and re.match(self.continuation, line.text.strip()) is not None
        )


class SplitterConfig(Contract):
    """Heading splitter settings for one document kind."""

    levels: tuple[str, ...] = Field(min_length=1)
    """Section levels, outermost first."""
    header_max_y: float
    """Lines starting above this y are running header."""
    footer_min_y: float
    """Lines starting below this y are running footer."""
    footer: str | None = None
    """Regex for a footer line placed higher than ``footer_min_y``; it and every line at or
    below it on that page are footer."""
    max_continuation: int = Field(ge=0)
    """Maximum number of wrapped lines appended to a heading title."""
    preamble: str = Field(min_length=1)
    """Title of the section holding text before the first heading."""
    rules: tuple[HeadingRule, ...]
    """Tried in order on each line; the first match wins."""

    def bands(self, lines: Sequence[Line]) -> tuple[list[Line], list[Line]]:
        """Separate a page's running header from its body; footer lines are dropped.

        Args:
            lines: The page's lines.

        Returns:
            The header lines and the body lines.
        """
        marks = [
            line.y0
            for line in lines
            if self.footer is not None and re.match(self.footer, line.text.strip())
        ]
        footer_y = min([self.footer_min_y, *marks])
        header = [line for line in lines if line.y0 < self.header_max_y]
        body = [line for line in lines if self.header_max_y <= line.y0 < footer_y]
        return header, body

    @model_validator(mode="after")
    def _check_levels(self) -> "SplitterConfig":
        """Reject rules naming an unknown level.

        Returns:
            The validated config.

        Raises:
            ValueError: If a rule's ``level`` or ``inside`` level is not in ``levels``.
        """
        for rule in self.rules:
            inside = rule.level if rule.inside is None else rule.inside.split("/", 1)[0]
            for level in (rule.level, inside):
                if level not in self.levels:
                    msg = f"rule {rule.pattern!r} names unknown level {level!r}"
                    raise ValueError(msg)
        return self
