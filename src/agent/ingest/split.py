from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import groupby

from agent.adapters.corpus.text import slug
from agent.contracts.inputs.corpus import Section
from agent.ingest.rules import HeadingRule, Line, SplitterConfig


@dataclass
class _Open:
    """A section being filled while the splitter walks the document."""

    level: str
    key: str
    id: str
    path: tuple[str, ...]
    zone: str | None
    article: str | None
    page_start: int
    page_end: int
    lines: list[str] = field(default_factory=list)

    def add(self, line: Line) -> None:
        """Append a line to the section's own text.

        Args:
            line: A body line.
        """
        text = line.text.strip()
        if text:
            self.lines.append(text)
            self.page_end = max(self.page_end, line.page)

    def section(self, doc: str) -> Section:
        """Freeze into a ``Section``.

        Args:
            doc: Document id.

        Returns:
            The section.
        """
        return Section(
            id=self.id,
            doc=doc,
            heading_path=self.path,
            zone=self.zone,
            article=self.article,
            page_start=self.page_start,
            page_end=self.page_end,
            text="\n".join(self.lines),
        )


class _Splitter:
    """Stateful walk over a document's lines, keeping one open section per level."""

    def __init__(self, doc: str, config: SplitterConfig) -> None:
        """Start an empty walk.

        Args:
            doc: Document id, the root of section ids.
            config: Splitter settings.
        """
        self._doc = doc
        self._config = config
        self._depth = {level: depth for depth, level in enumerate(config.levels)}
        self._stack: list[_Open] = []
        self._opened: list[_Open] = []
        self._ids: set[str] = set()

    def page(self, lines: Sequence[Line]) -> None:
        """Process the lines of one page: header rules first, then body lines.

        Args:
            lines: The page's lines in reading order.
        """
        config = self._config
        header, body = config.bands(lines)
        for rule in (rule for rule in config.rules if rule.scope == "header"):
            hit = next((line for line in header if self._hit(rule, line)), None)
            if hit is not None:
                self._open(rule, hit, [], heading=False)
        index = 0
        while index < len(body):
            index = self._body(body, index)

    def finish(self) -> tuple[Section, ...]:
        """Return every section opened, in document order.

        Returns:
            The sections.
        """
        return tuple(opened.section(self._doc) for opened in self._opened)

    def _body(self, body: Sequence[Line], index: int) -> int:
        """Handle one body line: open a section on a heading, else append the line.

        Args:
            body: The page's body lines.
            index: Position of the line to handle.

        Returns:
            Position of the next unhandled line.
        """
        line = body[index]
        rule = next((rule for rule in self._config.rules if self._hit(rule, line, "body")), None)
        if rule is None:
            self._append(line)
            return index + 1
        wrapped: list[Line] = []
        for follower in body[index + 1 :]:
            if len(wrapped) >= self._config.max_continuation or not rule.continues(follower):
                break
            wrapped.append(follower)
        self._open(rule, line, wrapped, heading=True)
        return index + 1 + len(wrapped)

    def _hit(self, rule: HeadingRule, line: Line, scope: str = "header") -> bool:
        """Tell whether a rule of the given scope applies to and matches a line.

        Args:
            rule: Candidate rule.
            line: Candidate line.
            scope: ``header`` or ``body``.

        Returns:
            True on a match honouring scope, ``inside`` (an open section of that level, and
            key if given) and typography.
        """
        level, _, key = ("" if rule.inside is None else rule.inside).partition("/")
        inside = not level or any(
            opened.level == level and (not key or slug(opened.key) == slug(key))
            for opened in self._stack
        )
        return rule.scope == scope and inside and rule.styled(line) and rule.match(line) is not None

    def _open(self, rule: HeadingRule, line: Line, wrapped: list[Line], *, heading: bool) -> None:
        """Open the section announced by a heading, unless it repeats the open one.

        Args:
            rule: The matching rule.
            line: The heading line.
            wrapped: Continuation lines of the heading.
            heading: Whether the heading lines belong to the section text (body headings).
        """
        match = rule.match(line)
        if match is None:
            return
        groups = match.groupdict(default="")
        title = rule.value(line) if rule.title is None else rule.title.format(**groups)
        title = " ".join(" ".join([title, *(follower.text for follower in wrapped)]).split())
        key = title if rule.key is None else rule.key.format(**groups)
        current = next((opened for opened in self._stack if opened.level == rule.level), None)
        if current is not None and current.key == key:
            return
        section = self._push(rule.level, key, title, line.page, groups)
        if heading:
            for heading_line in (line, *wrapped):
                section.add(heading_line)

    def _append(self, line: Line) -> None:
        """Append a body line to the innermost open section, or to the preamble.

        Args:
            line: A body line that is not a heading.
        """
        if not self._stack:
            title = self._config.preamble
            self._push(self._config.levels[0], title, title, line.page, {})
        self._stack[-1].add(line)

    def _push(
        self, level: str, key: str, title: str, page: int, groups: Mapping[str, str]
    ) -> _Open:
        """Open a section, closing every open section at the same depth or deeper.

        Args:
            level: Section level.
            key: Section key, slugged into the last id component.
            title: Heading title.
            page: Opening page.
            groups: Captured groups; ``zone`` and ``article`` are read.

        Returns:
            The new open section.
        """
        depth = self._depth[level]
        self._stack = [opened for opened in self._stack if self._depth[opened.level] < depth]
        parent = self._stack[-1] if self._stack else None
        section = _Open(
            level=level,
            key=key,
            id=self._unique(f"{parent.id if parent else self._doc}/{slug(key)}"),
            path=(*(parent.path if parent else ()), title),
            zone=groups.get("zone") or (parent.zone if parent else None),
            article=groups.get("article") or None,
            page_start=page,
            page_end=page,
        )
        self._stack.append(section)
        self._opened.append(section)
        return section

    def _unique(self, base: str) -> str:
        """Reserve a section id, suffixing ``-2``, ``-3``... on collision.

        Args:
            base: The natural id.

        Returns:
            An id not used before in this document.
        """
        candidate, count = base, 1
        while candidate in self._ids:
            count += 1
            candidate = f"{base}-{count}"
        self._ids.add(candidate)
        return candidate


def split_document(doc: str, lines: Sequence[Line], config: SplitterConfig) -> tuple[Section, ...]:
    """Split a document's lines into heading-delimited sections.

    Sections partition the body text: each holds its own lines only, not its children's.
    Running headers and footers are excluded; repeated headings are dropped.

    Args:
        doc: Document id, the root of section ids (``{doc}/{key}/{key}...``).
        lines: The document's lines, in page and reading order.
        config: Splitter settings for the document kind.

    Returns:
        The sections in document order.
    """
    splitter = _Splitter(doc, config)
    for _, page_lines in groupby(lines, key=lambda line: line.page):
        splitter.page(list(page_lines))
    return splitter.finish()
