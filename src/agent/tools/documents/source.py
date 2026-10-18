from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from agent.adapters.corpus.index import CorpusIndex, load_index


class RetrievalMode(StrEnum):
    """How much text the reading tools return per call."""

    NAVIGATION = "navigation"
    """One level at a time: a section's own text and an outline of its sub-sections."""
    FULL_SECTIONS = "full_sections"
    """Whole sections, with all their sub-sections."""


class CorpusSource:
    """The ingested corpus the document tools read, loaded on first use and shared."""

    def __init__(
        self, *, directory: Path, stopwords: Sequence[str], expected_id: str | None = None
    ) -> None:
        """Keep the settings; nothing is loaded, so graphs build without the corpus on disk.

        Args:
            directory: Corpus directory.
            stopwords: Words ignored by keyword search.
            expected_id: Configured corpus identity, checked on first use.
        """
        self.directory = Path(directory).resolve()
        self.stopwords = tuple(stopwords)
        self.expected_id = expected_id

    def index(self) -> CorpusIndex:
        """Return the corpus index, the same one for every tool reading this directory.

        Raises:
            FileNotFoundError: When the corpus has not been ingested.
        """
        return load_index(self.directory, self.stopwords, self.expected_id)


@contextmanager
def lookup_errors() -> Generator[None]:
    """Turn corpus lookup errors into tool errors, which the model reads and can act on."""
    try:
        yield
    except LookupError as error:
        raise ToolException(str(error)) from error


def require_positive(**limits: int) -> None:
    """Check tool limits from config.

    Args:
        **limits: Limit values by knob name.

    Raises:
        ValueError: If a limit is below 1.
    """
    invalid = [f"{name}={value}" for name, value in limits.items() if value < 1]
    if invalid:
        msg = f"document tool limits must be at least 1: {', '.join(invalid)}"
        raise ValueError(msg)


def as_tool(function: Callable[..., str], description: str | None = None) -> BaseTool:
    """Wrap a reading function as a tool named after it.

    Argument descriptions come from the function's ``Args:`` section; ``ToolException`` errors
    are returned to the model as the tool's reply.

    Args:
        function: The tool body, with a Google-style docstring.
        description: What the model reads; defaults to the docstring before ``Args:``.

    Returns:
        The tool.
    """
    return StructuredTool.from_function(
        function, description=description, parse_docstring=True, handle_tool_error=True
    )
