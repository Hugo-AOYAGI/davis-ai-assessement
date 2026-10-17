from typing import Any

import pytest

from agent.contracts.revision import Edit, Revision
from agent.runtime.submissions.edits import EditError, apply_edits

DRAFT: dict[str, Any] = {
    "label": "rules",
    "notes": [
        {"topic": "height", "citations": [{"quote": "a"}, {"quote": "b"}, {"quote": "c"}]},
        {"topic": "access", "citations": [{"quote": "d"}]},
        {"topic": "parking", "citations": []},
    ],
}


def apply(edits, draft=DRAFT) -> Any:
    return apply_edits(draft, edits)


def edit(path, **kwargs):
    return Edit(path=path, **kwargs)


def errors_of(edits):
    with pytest.raises(EditError) as info:
        apply(edits)
    return info.value.errors


def test_sets_a_nested_value():
    result = apply([edit("notes.0.citations.1.quote", value="B")])
    assert result["notes"][0]["citations"][1] == {"quote": "B"}
    assert DRAFT["notes"][0]["citations"][1] == {"quote": "b"}


def test_replaces_a_whole_item():
    result = apply([edit("notes.1", value={"topic": "roads", "citations": []})])
    assert result["notes"][1] == {"topic": "roads", "citations": []}


def test_adds_a_missing_key():
    result = apply([edit("notes.2.text", value="none"), edit("open", value=[])])
    assert result["notes"][2]["text"] == "none"
    assert result["open"] == []


def test_null_is_a_value():
    result = apply([edit("label", value=None)])
    assert result["label"] is None


def test_appends_at_list_length():
    result = apply(
        [edit("notes.1.citations.2", value={"quote": "f"}), edit("notes.1.citations.1", value={})],
    )
    assert result["notes"][1]["citations"] == [{"quote": "d"}, {}, {"quote": "f"}]


def test_removes_one_item():
    result = apply([edit("notes.0.citations.1", remove=True)])
    assert result["notes"][0]["citations"] == [{"quote": "a"}, {"quote": "c"}]


def test_removes_several_items_with_original_indices():
    result = apply(
        [
            edit("notes.0.citations.0", remove=True),
            edit("notes.0.citations.2", remove=True),
            edit("notes.1", remove=True),
        ],
    )
    assert result["notes"][0]["citations"] == [{"quote": "b"}]
    assert [note["topic"] for note in result["notes"]] == ["height", "parking"]


def test_paths_refer_to_the_original_draft():
    result = apply(
        [
            edit("notes.0", remove=True),
            edit("notes.2.topic", value="cars"),
            edit("notes.1.citations.0.quote", value="D"),
        ],
    )
    assert result["notes"] == [
        {"topic": "access", "citations": [{"quote": "D"}]},
        {"topic": "cars", "citations": []},
    ]


def test_removes_a_key():
    result = apply([edit("label", remove=True)])
    assert "label" not in result


def test_remove_with_null_value_is_a_removal():
    result = apply([edit("label", value=None, remove=True)])
    assert "label" not in result


def test_no_edit_returns_a_copy():
    result = apply([])
    assert result == DRAFT
    assert result is not DRAFT


@pytest.mark.parametrize(
    ("path", "kwargs", "expected"),
    [
        ("notes.5.topic", {"value": "x"}, "notes.5.topic: notes has 3 items, no index 5"),
        ("notes.0.title", {"remove": True}, "notes.0.title: notes.0 has no field 'title'"),
        ("notes.x", {"value": 1}, "notes.x: notes is a list: 'x' is not an index"),
        ("notes.-1", {"value": 1}, "notes.-1: notes is a list: '-1' is not an index"),
        ("label.x", {"value": 1}, "label.x: label is a value, not an object or a list"),
        ("nope.x", {"value": 1}, "nope.x: the result has no field 'nope'"),
        ("notes..topic", {"value": 1}, "notes..topic: empty step after notes"),
        ("notes.3", {"remove": True}, "notes.3: notes has 3 items, no index 3"),
        ("notes.4", {"value": {}}, "notes.4: notes has 3 items, append at index 3, not 4"),
        ("label", {}, "label: give a value, or remove: true"),
        ("label", {"value": "x", "remove": True}, "label: give a value or remove: true, not both"),
    ],
)
def test_bad_edit_is_reported(path, kwargs, expected):
    assert errors_of([edit(path, **kwargs)]) == (expected,)


def test_overlapping_edits_are_reported():
    errors = errors_of(
        [
            edit("notes.0", remove=True),
            edit("notes.0.topic", value="x"),
            edit("label", value="a"),
            edit("label", value="b"),
        ]
    )
    assert errors == (
        "notes.0.topic: inside notes.0, which another edit changes",
        "label: edited twice",
    )


def test_nothing_is_applied_when_an_edit_is_bad():
    draft = {"label": "rules", "notes": [{"topic": "height"}]}
    with pytest.raises(EditError) as info:
        apply(
            draft=draft,
            edits=[edit("label", value="ok"), edit("notes.3", remove=True), edit("topic", value=1)],
        )
    assert info.value.errors == ("notes.3: notes has 1 items, no index 3",)
    assert draft == {"label": "rules", "notes": [{"topic": "height"}]}


def test_revision_accepts_an_empty_list():
    assert Revision.model_validate({"edits": []}).edits == ()


def test_aliased_list_indices_cannot_remove_the_same_item_twice():
    assert errors_of([edit("notes.0", remove=True), edit("notes.00", remove=True)]) == (
        "notes.0: edited twice",
    )


def test_aliased_list_indices_cannot_hide_an_overlapping_edit():
    assert errors_of([edit("notes.0", value=None), edit("notes.00.topic", value="x")]) == (
        "notes.00.topic: inside notes.0, which another edit changes",
    )


def test_numeric_object_keys_remain_distinct():
    result = apply(
        [edit("0", value="first"), edit("00", value="second")],
        draft={"0": "old", "00": "old"},
    )
    assert result == {"0": "first", "00": "second"}
