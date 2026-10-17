import json
from pathlib import Path

import pytest

from agent.adapters.corpus.store import CORPUS_FILE, load_corpus, save_corpus


def test_round_trip(tmp_path, corpus):
    directory = tmp_path / "corpus"

    path = save_corpus(corpus, directory)

    assert path == directory / CORPUS_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "Règlement" in path.read_text(encoding="utf-8")
    assert raw["documents"][0]["path"] == "ressources/reglement.pdf"
    assert set(raw["pages"][0]) == {"doc", "number", "text"}
    assert load_corpus(directory) == corpus


def test_missing_corpus_tells_how_to_ingest(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"agent\.entrypoints\.ingest"):
        load_corpus(tmp_path / Path("missing"))
