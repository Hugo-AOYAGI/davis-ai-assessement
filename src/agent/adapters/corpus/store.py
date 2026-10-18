import json
from pathlib import Path

from agent.contracts.inputs.corpus import Corpus

CORPUS_FILE = "corpus.json"


def save_corpus(corpus: Corpus, directory: Path) -> Path:
    """Write a corpus to ``directory/corpus.json``, document paths in POSIX form.

    Args:
        corpus: The ingested corpus.
        directory: Corpus directory, created if missing.

    Returns:
        Path of the written file.
    """
    directory.mkdir(parents=True, exist_ok=True)
    data = corpus.model_dump(mode="json", exclude={"documents"})
    data["documents"] = [
        {**document.model_dump(mode="json"), "path": document.path.as_posix()}
        for document in corpus.documents
    ]
    path = directory / CORPUS_FILE
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_corpus(directory: Path, expected_id: str | None = None) -> Corpus:
    """Read a corpus written by :func:`save_corpus`.

    Args:
        directory: Corpus directory.
        expected_id: Configured identity to verify, when supplied.

    Returns:
        The corpus.

    Raises:
        FileNotFoundError: When the directory holds no ingested corpus.
        ValueError: If its identity differs from the configured corpus.
    """
    path = directory / CORPUS_FILE
    if not path.is_file():
        msg = (
            f"No ingested corpus at {path}. "
            "Build it with `uv run python -m agent.entrypoints.ingest`."
        )
        raise FileNotFoundError(msg)
    corpus = Corpus.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if expected_id is not None and corpus.id != expected_id:
        msg = f"Corpus at {path} has id {corpus.id!r}, expected {expected_id!r}. Check corpus.dir."
        raise ValueError(msg)
    return corpus
