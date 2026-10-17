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


def test_extracts_lines_and_page_text(pdf):
    extraction = extract_document(pdf, "doc")
    first, raster, figure = extraction.pages
    assert first.text == "Header line\nBody line"
    body = next(line for line in extraction.lines if line.text == "Body line")
    assert (body.page, body.size, body.lead) == (1, 12.0, "Body line")
    assert body.y0 < 300 < body.y0 + 20
    assert raster.text == ""
    assert figure.text == "Schema"


def test_no_image_is_written(pdf, tmp_path):
    before = set(tmp_path.rglob("*"))
    extract_document(pdf, "doc")
    assert set(tmp_path.rglob("*")) == before


def test_lead_stops_at_font_change():
    rows = json.loads((FIXTURES / "reglement_titre_iii.json").read_text(encoding="utf-8"))
    lines = [Line.model_validate(row) for row in rows]
    egout = next(line for line in lines if line.text.startswith("Egout du toit"))
    assert egout.lead == "Egout du toit :"
    assert len(egout.text) > len(egout.lead)
    assert egout.font == "ArialNarrow-Bold"
