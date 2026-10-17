from collections.abc import Callable
from pathlib import Path

from omegaconf import DictConfig, OmegaConf
from pydantic import ConfigDict, Field

from agent.adapters.corpus.store import save_corpus
from agent.contracts.base import Contract
from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page, Section
from agent.ingest.classify import Classification, text_sample
from agent.ingest.extract import extract_document
from agent.ingest.rules import SplitterConfig
from agent.ingest.split import split_document
from agent.observability.logs import get_logger

logger = get_logger(__name__)


class DocumentSettings(Contract):
    """One source PDF of the corpus.

    Unknown keys are ignored: the entry also holds settings read by the tools (``legal_force``).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(min_length=1)
    path: str
    """PDF path relative to the project root."""
    kind: DocumentKind | None = None
    """Forced kind; skips the classifier when set."""
    title: str | None = None
    """Forced title; replaces the classifier's title when set."""


class ClassifierSettings(Contract):
    """Document classifier settings."""

    model: str
    """Model node key in ``models.nodes``."""
    prompt: str
    """Prompt path relative to the project root."""
    sample_pages: int = Field(ge=1)
    sample_chars: int = Field(ge=1)


class CorpusSettings(Contract):
    """The part of the ``corpus`` config group used by ingestion.

    Unknown keys are ignored: the group also holds settings read by the corpus adapter.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(min_length=1)
    dir: str
    """Output directory relative to the project root."""
    documents: tuple[DocumentSettings, ...] = Field(min_length=1)
    classifier: ClassifierSettings
    splitter: dict[DocumentKind, SplitterConfig]
    """Heading splitter per kind; kinds without one get no sections."""


def load_settings(corpus_cfg: DictConfig) -> CorpusSettings:
    """Validate the ``corpus`` config group.

    Args:
        corpus_cfg: The ``corpus`` config group.

    Returns:
        The ingestion settings.
    """
    return CorpusSettings.model_validate(OmegaConf.to_container(corpus_cfg, resolve=True))


def _ingest_document(
    settings: CorpusSettings,
    document: DocumentSettings,
    root: Path,
    classify: Callable[[str], Classification],
) -> tuple[Document, tuple[Page, ...], tuple[Section, ...]]:
    """Extract, classify and split one PDF.

    Args:
        settings: Ingestion settings.
        document: The document's settings.
        root: Project root.
        classify: Classifier called when the kind or title is not forced.

    Returns:
        The document, its pages and its sections.
    """
    path = root / document.path
    kind, title = document.kind, document.title
    if kind is None or title is None:
        classifier = settings.classifier
        answer = classify(text_sample(path, classifier.sample_pages, classifier.sample_chars))
        kind, title = kind or answer.kind, title or answer.title
    extraction = extract_document(path, document.id)
    splitter = settings.splitter.get(kind)
    sections = () if splitter is None else split_document(document.id, extraction.lines, splitter)
    logger.info(
        "%s: %s, %d pages (%d without text), %d sections",
        document.id,
        kind,
        len(extraction.pages),
        sum(not page.text.strip() for page in extraction.pages),
        len(sections),
    )
    meta = Document(
        id=document.id,
        kind=kind,
        title=title,
        path=Path(document.path),
        page_count=len(extraction.pages),
    )
    return meta, extraction.pages, sections


def ingest_corpus(
    settings: CorpusSettings, root: Path, classify: Callable[[str], Classification]
) -> Corpus:
    """Ingest every configured PDF and save the corpus under ``settings.dir``.

    Args:
        settings: Ingestion settings (see :func:`load_settings`).
        root: Project root, against which config paths are resolved.
        classify: Document classifier (see ``make_classifier``).

    Returns:
        The saved corpus.
    """
    documents: list[Document] = []
    pages: list[Page] = []
    sections: list[Section] = []
    for document in settings.documents:
        meta, doc_pages, doc_sections = _ingest_document(settings, document, root, classify)
        documents.append(meta)
        pages.extend(doc_pages)
        sections.extend(doc_sections)
    corpus = Corpus(
        id=settings.id, documents=tuple(documents), pages=tuple(pages), sections=tuple(sections)
    )
    path = save_corpus(corpus, root / settings.dir)
    logger.info(
        "corpus %s: %d documents, %d pages, %d sections written to %s",
        corpus.id,
        len(documents),
        len(pages),
        len(sections),
        path,
    )
    return corpus
