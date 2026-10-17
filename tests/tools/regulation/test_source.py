import pytest
from langchain_core.tools import ToolException

from agent.tools.regulation.source import (
    CorpusSource,
    RetrievalMode,
    lookup_errors,
    require_positive,
)


def test_construction_loads_nothing(tmp_path):
    source = CorpusSource(directory=str(tmp_path / "missing"), lexicon=[], stopwords=[])
    with pytest.raises(FileNotFoundError, match="No ingested corpus"):
        source.index()


def test_relative_directory_resolves_against_project_root():
    source = CorpusSource(directory="data/somewhere", lexicon=[], stopwords=[])
    assert source.directory.is_absolute()
    assert (source.directory.parents[1] / "pyproject.toml").is_file()


def test_sources_on_one_directory_share_the_index(corpus_dir, source):
    other = CorpusSource(
        directory=str(corpus_dir), lexicon=source.lexicon, stopwords=source.stopwords
    )
    assert other.index() is source.index()


def test_lookup_errors_become_tool_errors():
    with pytest.raises(ToolException, match="Unknown zone"), lookup_errors():
        raise LookupError("Unknown zone 'X'.")


def test_require_positive_names_the_bad_knob():
    require_positive(max_chars=1)
    with pytest.raises(ValueError, match="max_pages=0"):
        require_positive(max_chars=10, max_pages=0)


def test_retrieval_modes():
    assert RetrievalMode("full_sections") is RetrievalMode.FULL_SECTIONS
    with pytest.raises(ValueError, match="nowhere"):
        RetrievalMode("nowhere")
