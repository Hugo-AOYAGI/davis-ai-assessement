from pathlib import Path

import pymupdf

from agent.adapters.corpus.store import load_corpus
from agent.agents.config import load_config
from agent.contracts.inputs.corpus import DocumentKind
from agent.ingest.classify import Classification
from agent.ingest.pipeline import CorpusSettings, ingest_corpus, load_settings


def make_text_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 20), "Running header", fontsize=8)
    page.insert_text((72, 100), "Intro text", fontsize=10)
    page.insert_text((72, 150), "CHAPTER 1", fontsize=16)
    page.insert_text((72, 200), "Chapter body", fontsize=10)
    document.save(path)


def make_raster_pdf(path: Path) -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 70, 50), False)
    pixmap.clear_with(128)
    document = pymupdf.open()
    document.new_page().insert_image(pymupdf.Rect(0, 0, 350, 250), stream=pixmap.tobytes("jpeg"))
    document.save(path)


def settings() -> CorpusSettings:
    return CorpusSettings.model_validate(
        {
            "id": "demo@1",
            "dir": "data/demo",
            "documents": [
                {"id": "rules", "path": "src/rules.pdf", "legal_force": "conformity"},
                {"id": "map", "path": "src/map.pdf", "kind": "zoning_map", "title": "Plan"},
            ],
            "classifier": {"model": "m", "prompt": "p.md", "sample_pages": 1, "sample_chars": 50},
            "splitter": {
                "regulatory_text": {
                    "levels": ["chapter"],
                    "header_max_y": 40,
                    "footer_min_y": 800,
                    "max_continuation": 0,
                    "preamble": "Preamble",
                    "rules": [
                        {
                            "level": "chapter",
                            "pattern": r"^CHAPTER (?P<number>\d+)$",
                            "min_size": 14,
                        }
                    ],
                }
            },
            "search": {"stopwords": ["ignored by ingestion"]},
        }
    )


def test_ingest_corpus_saves_a_loadable_corpus(tmp_path: Path):
    (tmp_path / "src").mkdir()
    make_text_pdf(tmp_path / "src" / "rules.pdf")
    make_raster_pdf(tmp_path / "src" / "map.pdf")
    samples: list[str] = []

    def classify(sample: str) -> Classification:
        samples.append(sample)
        return Classification(kind=DocumentKind.REGULATORY_TEXT, title="Rules")

    corpus = ingest_corpus(settings(), tmp_path, classify)

    assert len(samples) == 1
    assert "rules.pdf" in samples[0]
    assert [(d.id, d.kind, d.title) for d in corpus.documents] == [
        ("rules", DocumentKind.REGULATORY_TEXT, "Rules"),
        ("map", DocumentKind.ZONING_MAP, "Plan"),
    ]
    assert [s.id for s in corpus.sections] == ["rules/preamble", "rules/chapter-1"]
    assert corpus.sections[1].text == "CHAPTER 1\nChapter body"
    assert "Running header" in corpus.pages[0].text
    assert corpus.pages[1].text == ""
    assert load_corpus(tmp_path / "data" / "demo") == corpus
    assert [path.name for path in (tmp_path / "data" / "demo").iterdir()] == ["corpus.json"]


def test_project_corpus_config_is_valid():
    loaded = load_settings(load_config().corpus)
    assert loaded.id == "gif-sur-yvette@2021-07-06"
    assert loaded.dir == "data/gif-sur-yvette@2021-07-06"
    assert [d.id for d in loaded.documents] == ["plu_reglement", "plu_reglement_graphique", "oap"]
    assert set(loaded.splitter) == {DocumentKind.REGULATORY_TEXT, DocumentKind.OAP}
