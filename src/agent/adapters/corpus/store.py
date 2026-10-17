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


def load_corpus(directory: Path) -> Corpus:
    """Read a corpus written by :func:`save_corpus`.

    Args:
        directory: Corpus directory.

    Returns:
        The corpus.

    Raises:
        FileNotFoundError: When the directory holds no ingested corpus.
    """
    path = directory / CORPUS_FILE
    if not path.is_file():
        msg = (
            f"No ingested corpus at {path}. "
            "Build it with `uv run python -m agent.entrypoints.ingest`."
        )
        raise FileNotFoundError(msg)
    return Corpus.model_validate(json.loads(path.read_text(encoding="utf-8")))
