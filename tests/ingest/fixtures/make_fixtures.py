"""Regenerate the splitter fixtures: ``uv run python tests/ingest/fixtures/make_fixtures.py``."""

import json
from pathlib import Path

import pymupdf

from agent.agents.config import PROJECT_ROOT
from agent.ingest.extract import page_lines

HERE = Path(__file__).parent
REGLEMENT = PROJECT_ROOT / "ressources" / "plu_reglement_91272_20210706.pdf"
OAP = PROJECT_ROOT / "ressources" / "oap_91272_20210706.pdf"

FIXTURES = {
    "reglement_titre_i.json": (REGLEMENT, [*range(2, 12)]),
    # p11 opens Titre II, so the Moulon header labels apply.
    "reglement_umg.json": (REGLEMENT, [11, 305, *range(319, 334)]),
    "reglement_titre_iii.json": (REGLEMENT, [*range(365, 382)]),
    "oap.json": (OAP, [1, 2, 3, *range(32, 37)]),
}


def dump(pdf: Path, pages: list[int]) -> list[dict[str, object]]:
    with pymupdf.open(pdf) as document:
        lines = [line for number in pages for line in page_lines(document[number - 1], number)]
    return [
        {**line.model_dump(), "y0": round(line.y0, 2)} | {"size": round(line.size, 2)}
        for line in lines
    ]


def main() -> None:
    for name, (pdf, pages) in FIXTURES.items():
        rows = [json.dumps(row, ensure_ascii=False) for row in dump(pdf, pages)]
        (HERE / name).write_text("[\n" + ",\n".join(rows) + "\n]\n", encoding="utf-8")


if __name__ == "__main__":
    main()
