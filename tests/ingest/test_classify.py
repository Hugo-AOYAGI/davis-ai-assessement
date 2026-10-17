from collections.abc import Sequence
from pathlib import Path

import pymupdf
import pytest
from langchain_core.messages import BaseMessage

from agent.agents.config import load_config
from agent.contracts.inputs.corpus import DocumentKind
from agent.ingest import classify as classify_module
from agent.ingest.classify import Classification, make_classifier, text_sample


class FakeStructured:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.calls: list[Sequence[BaseMessage]] = []

    def invoke(self, messages: Sequence[BaseMessage]) -> object:
        self.calls.append(messages)
        return self.answer


class FakeModel:
    def __init__(self, structured: FakeStructured) -> None:
        self.structured = structured
        self.schema: object = None

    def with_structured_output(self, schema: object) -> FakeStructured:
        self.schema = schema
        return self.structured


def test_text_sample_describes_the_pdf(tmp_path: Path):
    document = pymupdf.open()
    document.new_page()
    for text in ("Première page de texte", "Deuxième page"):
        document.new_page().insert_text((72, 100), text)
    document.set_metadata({"title": "Règlement"})
    path = tmp_path / "reglement.pdf"
    document.save(path)
    sample = text_sample(path, sample_pages=1, sample_chars=8)
    assert "File name: reglement.pdf" in sample
    assert "Metadata title: Règlement" in sample
    assert "Pages: 3" in sample
    assert "Pages with a text layer: 2" in sample
    assert "--- Page 2 ---\nPremière" in sample
    assert "Deuxième" not in sample


@pytest.mark.parametrize(
    "answer",
    [
        {"kind": "oap", "title": "OAP"},
        Classification(kind=DocumentKind.OAP, title="OAP"),
    ],
)
def test_classifier_validates_structured_output(monkeypatch: pytest.MonkeyPatch, answer):
    structured = FakeStructured(answer)
    model = FakeModel(structured)
    monkeypatch.setattr(classify_module, "build_model", lambda cfg, node: model)
    classify = make_classifier(load_config(["subagents=[]"]).models, "ingest_classifier", "PROMPT")
    assert classify("sample") == Classification(kind=DocumentKind.OAP, title="OAP")
    assert model.schema is Classification
    system, human = structured.calls[0]
    assert (system.content, human.content) == ("PROMPT", "sample")
