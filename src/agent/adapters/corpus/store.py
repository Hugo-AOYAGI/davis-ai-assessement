import json
from pathlib import Path

from agent.contracts.inputs.corpus import Corpus, Page

CORPUS_FILE = "corpus.json"


def image_path(directory: Path, doc: str, number: int, suffix: str) -> Path:
    """Return where the image of a page is stored inside a corpus directory.

    Args:
        directory: Corpus directory.
        doc: Document id.
        number: 1-based page number.
        suffix: File extension without the dot, e.g. ``jpg``.

    Returns:
        ``directory/images/<doc>/p<number:04d>.<suffix>``.
    """
    return directory / "images" / doc / f"p{number:04d}.{suffix}"


def save_corpus(corpus: Corpus, directory: Path) -> Path:
    """Write a corpus to ``directory/corpus.json``.

    Paths are written in POSIX form. Page images lying inside ``directory`` are stored relative
    to it, so the directory can be moved or shared as a whole.

    Args:
        corpus: The ingested corpus.
        directory: Corpus directory, created if missing.

    Returns:
        Path of the written file.
    """
    directory.mkdir(parents=True, exist_ok=True)
    data = corpus.model_dump(mode="json", exclude={"documents", "pages"})
    data["documents"] = [
        {**document.model_dump(mode="json"), "path": document.path.as_posix()}
        for document in corpus.documents
    ]
    data["pages"] = [
        {**page.model_dump(mode="json"), "image": _stored_image(page.image, directory)}
        for page in corpus.pages
    ]
    path = directory / CORPUS_FILE
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_corpus(directory: Path) -> Corpus:
    """Read a corpus written by :func:`save_corpus`.

    Args:
        directory: Corpus directory.

    Returns:
        The corpus, with page image paths made absolute.

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
    corpus = Corpus.model_validate(json.loads(path.read_text(encoding="utf-8")))
    pages = tuple(_absolute_image(page, directory) for page in corpus.pages)
    return corpus.model_copy(update={"pages": pages})


def _stored_image(image: Path | None, directory: Path) -> str | None:
    """Return the serialized image path: relative when inside the directory, else absolute."""
    if image is None:
        return None
    root, resolved = directory.resolve(), image.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return resolved.as_posix()


def _absolute_image(page: Page, directory: Path) -> Page:
    """Return the page with its image path resolved against the corpus directory."""
    if page.image is None or page.image.is_absolute():
        return page
    return page.model_copy(update={"image": (directory / page.image).resolve()})
