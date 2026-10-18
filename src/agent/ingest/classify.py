from collections.abc import Callable
from functools import cache
from pathlib import Path

import pymupdf
from langchain_core.messages import HumanMessage, SystemMessage
from omegaconf import DictConfig
from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.inputs.corpus import DocumentKind
from agent.llm.factory import build_model


class Classification(Contract):
    """The type and title of a planning document."""

    kind: DocumentKind
    """``regulatory_text`` for the written rules (articles by zone), ``zoning_map`` for the
    graphic zoning plan (a map, usually without a text layer), ``oap`` for the orientations
    d'aménagement et de programmation (sector-by-sector development principles)."""
    title: str = Field(min_length=1)
    """Short human-readable title of the document, in its own language."""


def text_sample(path: Path, sample_pages: int, sample_chars: int) -> str:
    """Describe a PDF for the classifier: file facts and the start of its first text pages.

    Args:
        path: The PDF.
        sample_pages: Number of pages with a text layer to quote.
        sample_chars: Characters quoted from each of them.

    Returns:
        The sample, as plain text.
    """
    with pymupdf.open(path) as document:
        metadata = document.metadata or {}
        texts = [(index + 1, page.get_text().strip()) for index, page in enumerate(document)]
    text_pages = [(number, text) for number, text in texts if text]
    lines = [
        f"File name: {path.name}",
        f"Metadata title: {metadata.get('title') or '(none)'}",
        f"Pages: {len(texts)}",
        f"Pages with a text layer: {len(text_pages)}",
    ]
    for number, text in text_pages[:sample_pages]:
        lines += ["", f"--- Page {number} ---", text[:sample_chars]]
    return "\n".join(lines)


def make_classifier(
    models_cfg: DictConfig, node: str, prompt: str
) -> Callable[[str], Classification]:
    """Build a document classifier backed by a chat model with structured output.

    Args:
        models_cfg: The ``models`` config group.
        node: Model node key in ``models.nodes``, e.g. ``ingest_classifier``.
        prompt: System prompt text.

    Returns:
        A function mapping a text sample (see :func:`text_sample`) to a classification.
    """

    @cache
    def model() -> Callable[[str], Classification]:
        """Create the model only when a document needs inferred metadata."""
        structured = build_model(models_cfg, node).with_structured_output(Classification)

        def invoke(sample: str) -> Classification:
            """Classify a sample with the shared structured-output client."""
            result = structured.invoke([SystemMessage(prompt), HumanMessage(sample)])
            return (
                result
                if isinstance(result, Classification)
                else Classification.model_validate(result)
            )

        return invoke

    def classify(sample: str) -> Classification:
        """Classify one document from its text sample.

        Args:
            sample: The document sample.

        Returns:
            The model's classification.
        """
        return model()(sample)

    return classify
