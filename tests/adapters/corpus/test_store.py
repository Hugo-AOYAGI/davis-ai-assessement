import json
from pathlib import Path

import pytest

from agent.adapters.corpus.store import CORPUS_FILE, image_path, load_corpus, save_corpus


def test_image_path_layout(tmp_path):
    assert image_path(tmp_path, "oap", 7, "png") == tmp_path / "images" / "oap" / "p0007.png"


def test_round_trip_stores_relative_and_loads_absolute(tmp_path, corpus_factory):
    directory = tmp_path / "corpus"
    image = image_path(directory, "plu_reglement_graphique", 1, "jpg")
    corpus = corpus_factory(image)

    path = save_corpus(corpus, directory)

    assert path == directory / CORPUS_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    stored = [page["image"] for page in raw["pages"] if page["image"] is not None]
    assert stored == ["images/plu_reglement_graphique/p0001.jpg"]
    assert "Règlement" in path.read_text(encoding="utf-8")
    assert raw["documents"][0]["path"] == "ressources/reglement.pdf"

    loaded = load_corpus(directory)
    loaded_image = next(page.image for page in loaded.pages if page.image is not None)
    assert loaded_image.is_absolute()
    assert loaded_image == image.resolve()
    assert loaded.sections == corpus.sections
    assert loaded.documents == corpus.documents


def test_image_outside_directory_stays_absolute(tmp_path, corpus_factory):
    outside = (tmp_path / "elsewhere" / "map.jpg").resolve()
    save_corpus(corpus_factory(outside), tmp_path / "corpus")

    loaded = load_corpus(tmp_path / "corpus")

    assert next(page.image for page in loaded.pages if page.image) == outside


def test_relative_image_resolved_against_directory(tmp_path, corpus):
    directory = tmp_path / "corpus"
    directory.mkdir()
    data = corpus.model_dump(mode="json")
    (directory / CORPUS_FILE).write_text(json.dumps(data), encoding="utf-8")

    loaded = load_corpus(directory)

    image = next(page.image for page in loaded.pages if page.image)
    assert image == (directory / "images" / "plu_reglement_graphique" / "p0001.jpg").resolve()


def test_missing_corpus_tells_how_to_ingest(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"agent\.entrypoints\.ingest"):
        load_corpus(tmp_path / Path("missing"))
