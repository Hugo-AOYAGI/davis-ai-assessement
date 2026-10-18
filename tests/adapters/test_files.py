from pathlib import Path

import pytest

from agent.adapters.files import publish


def test_publishes_the_body_and_leaves_no_temporary(tmp_path):
    target = tmp_path / "cache" / "a.json"
    publish(target, b"{}")
    assert target.read_bytes() == b"{}"
    assert [p.name for p in target.parent.iterdir()] == ["a.json"]


def test_replacement_failure_does_not_claim_an_existing_file_was_updated(tmp_path, monkeypatch):
    target = tmp_path / "a.json"
    target.write_bytes(b"first")

    def refuse(self, other):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(PermissionError):
        publish(target, b"second")
    assert target.read_bytes() == b"first"
    assert [p.name for p in tmp_path.iterdir()] == ["a.json"]


def test_raises_when_replace_is_refused_and_nothing_was_published(tmp_path, monkeypatch):
    def refuse(self, other):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(PermissionError):
        publish(tmp_path / "a.json", b"x")
    assert list(tmp_path.iterdir()) == []
