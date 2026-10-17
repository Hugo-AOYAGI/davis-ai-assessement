import json
from pathlib import Path

import pymupdf
import pytest

from agent.ingest.extract import extract_document
from agent.ingest.rules import Line

FIXTURES = Path(__file__).parent / "fixtures"


def png(width: int, height: int) -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pixmap.clear_with(200)
    data = pixmap.tobytes("png")
    assert isinstance(data, bytes)
    return data


def make_pdf(path: Path) -> Path:
    document = pymupdf.open()
    text_page = document.new_page()
    text_page.insert_text((72, 100), "Header line", fontsize=8)
    text_page.insert_text((72, 300), "Body line", fontsize=12)
    raster_page = document.new_page()
    raster_page.insert_image(pymupdf.Rect(0, 0, 300, 200), stream=png(60, 40))
    figure_page = document.new_page()
    figure_page.insert_text((72, 100), "Schema", fontsize=12)
    figure_page.insert_image(pymupdf.Rect(72, 200, 272, 400), stream=png(20, 20))
    document.save(path)
    return path


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    return make_pdf(tmp_path / "sample.pdf")


def test_extracts_lines_and_page_text(pdf, tmp_path):
    extraction = extract_document(pdf, "doc", tmp_path / "corpus", figures=False, dpi=36)
    first, raster, figure = extraction.pages
    assert first.text == "Header line\nBody line"
    assert first.image is None
    body = next(line for line in extraction.lines if line.text == "Body line")
    assert (body.page, body.size, body.lead) == (1, 12.0, "Body line")
    assert body.y0 < 300 < body.y0 + 20
    assert raster.text == ""
    assert figure.image is None
    assert (extraction.raster_pages, extraction.figure_pages) == (1, 0)


def test_raster_page_keeps_native_image(pdf, tmp_path):
    corpus = tmp_path / "corpus"
    raster = extract_document(pdf, "doc", corpus, figures=False, dpi=36).pages[1]
    assert raster.image == corpus / "images" / "doc" / "p0002.png"
    stored = pymupdf.Pixmap(str(raster.image))
    assert (stored.width, stored.height) == (60, 40)


def test_figure_pages_are_rendered(pdf, tmp_path):
    corpus = tmp_path / "corpus"
    extraction = extract_document(pdf, "doc", corpus, figures=True, dpi=36)
    assert extraction.pages[0].image is None
    assert extraction.pages[2].image == corpus / "images" / "doc" / "p0003.png"
    image = extraction.pages[2].image
    assert image is not None
    assert image.is_file()
    assert (extraction.raster_pages, extraction.figure_pages) == (1, 1)


def test_lead_stops_at_font_change():
    rows = json.loads((FIXTURES / "reglement_titre_iii.json").read_text(encoding="utf-8"))
    lines = [Line.model_validate(row) for row in rows]
    egout = next(line for line in lines if line.text.startswith("Egout du toit"))
    assert egout.lead == "Egout du toit :"
    assert len(egout.text) > len(egout.lead)
    assert egout.font == "ArialNarrow-Bold"
