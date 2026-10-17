from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from agent.adapters.corpus.index import CorpusIndex, load_index

# Tools may not import agent.agents.config (layering), so the root is derived here:
# src/agent/tools/regulation/source.py -> parents[4] is the repository root.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


class RetrievalMode(StrEnum):
    """How much text the reading tools return per call."""

    NAVIGATION = "navigation"
    """One level at a time: a section's own text and an outline of its sub-sections."""
    FULL_SECTIONS = "full_sections"
    """Whole sections, with all their sub-sections."""


class CorpusSource:
    """The ingested corpus the regulation tools read, loaded on first use and shared."""

    def __init__(self, *, directory: str, lexicon: Sequence[str], stopwords: Sequence[str]) -> None:
        """Keep the settings; nothing is loaded, so graphs build without the corpus on disk.

        Args:
            directory: Corpus directory, absolute or relative to the project root.
            lexicon: Ids of glossary sections whose children are term definitions.
            stopwords: Words ignored by keyword search.
        """
        path = Path(directory)
        self.directory = (path if path.is_absolute() else _PROJECT_ROOT / path).resolve()
        self.lexicon = tuple(lexicon)
        self.stopwords = tuple(stopwords)

    def index(self) -> CorpusIndex:
        """Return the corpus index, the same one for every tool reading this directory.

        Raises:
            FileNotFoundError: When the corpus has not been ingested.
        """
        return load_index(self.directory, self.lexicon, self.stopwords)


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
        msg = f"regulation tool limits must be at least 1: {', '.join(invalid)}"
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
