from enum import StrEnum
from pathlib import Path

from pydantic import Field

from agent.contracts.base import Contract


class DocumentKind(StrEnum):
    """Document type, which selects the ingestion pipeline."""

    REGULATORY_TEXT = "regulatory_text"
    ZONING_MAP = "zoning_map"
    OAP = "oap"


class Document(Contract):
    """A source document of the corpus."""

    id: str = Field(min_length=1)
    """Short id used in citations, e.g. ``plu_reglement``."""
    kind: DocumentKind
    title: str = Field(min_length=1)
    path: Path
    """Source PDF."""
    page_count: int = Field(ge=1)


class Page(Contract):
    """One page of a document."""

    doc: str = Field(min_length=1)
    number: int = Field(ge=1)
    """1-based PDF page index."""
    text: str
    """Extracted text layer; empty for raster pages."""


class Section(Contract):
    """A heading-delimited part of a document (title, chapter, zone, article...)."""

    id: str = Field(min_length=1)
    """Stable id, e.g. ``plu_reglement/UMG/10``."""
    doc: str = Field(min_length=1)
    heading_path: tuple[str, ...] = Field(min_length=1)
    """Headings from the document root down to this section."""
    zone: str | None = None
    article: str | None = None
    """Article number within the zone chapter."""
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    text: str


class Corpus(Contract):
    """An ingested corpus, as written by ``ingest`` and read by the corpus adapter."""

    id: str = Field(min_length=1)
    documents: tuple[Document, ...] = Field(min_length=1)
    pages: tuple[Page, ...]
    sections: tuple[Section, ...]
