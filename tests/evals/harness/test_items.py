from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from evals.harness.items import (
    DocInput,
    E2EInput,
    Item,
    ItemError,
    KeyFact,
    Level,
    StatementFact,
    Status,
    SurveyorInput,
    ZoningInput,
    load_item,
    load_items,
)

ITEMS = Path(__file__).parents[1] / "fixtures" / "items"


def raw(name: str) -> dict[str, Any]:
    return yaml.safe_load((ITEMS / f"{name}.yaml").read_text(encoding="utf-8"))


def test_the_four_examples_parse_with_their_level_input(items):
    expected = {
        "s01_joliot_curie": (Level.SURVEYOR, SurveyorInput, Status.VERIFIED),
        "z01_zone_boundary": (Level.ZONING, ZoningInput, Status.DRAFT),
        "d02_uga_height": (Level.DOC, DocInput, Status.VERIFIED),
        "e01_reference": (Level.E2E, E2EInput, Status.DRAFT),
    }
    assert {key: (i.level, type(i.input), i.status) for key, i in items.items()} == expected


def test_example_contents(items):
    s01, d02, e01 = items["s01_joliot_curie"], items["d02_uga_height"], items["e01_reference"]
    assert isinstance(s01.facts[0], KeyFact)
    assert s01.facts[0].expect == ("91272000CR0247",)
    assert s01.facts[2].tolerance == 0.02
    assert all(isinstance(fact, StatementFact) for fact in d02.facts)
    assert d02.facts[0].evidence[0].page == 91
    assert isinstance(d02.input, DocInput)
    assert d02.input.context.zone == "UGa"
    assert e01.from_items == ("s01", "z05", "d01", "d11")
    footprint = next(f for f in e01.facts if f.key == "study.envelope.max_footprint_ratio")
    assert footprint.expect is None
    assert "expect" in footprint.model_fields_set
    assert footprint.evidence[0].quote is None


def test_load_items_returns_verified_items_by_default():
    assert [item.id for item in load_items(ITEMS)] == ["d02_uga_height", "s01_joliot_curie"]


@pytest.mark.parametrize("name", ["e01_reference", "z01_zone_boundary"])
def test_verified_item_with_placeholder_is_rejected(name):
    data = raw(name) | {"status": "verified"}
    with pytest.raises(ValidationError, match="unfilled placeholders"):
        Item.model_validate(data)


@pytest.mark.parametrize(
    ("fact", "message"),
    [
        ({"key": "zone", "expect": "UA", "any_of": ["UA"]}, "exactly one expectation"),
        ({"key": "zone"}, "found: none"),
        ({"key": "zone", "at_least": 1, "tolerance": 0.1}, "tolerance only applies"),
        ({"key": "zone[", "expect": "UA"}, "invalid key"),
        ({"key": "a..b", "expect": 1}, "invalid key"),
        ({"key": "zone", "expect": "UA", "unknown": 1}, "Extra inputs"),
    ],
)
def test_bad_key_facts_are_rejected(fact, message):
    with pytest.raises(ValidationError, match=message):
        KeyFact.model_validate(fact)


def test_present_and_absent_count_as_one_expectation():
    fact = KeyFact.model_validate({"key": "overlays", "present": ["A"], "absent": ["B"]})
    assert fact.present == ("A",)
    assert fact.absent == ("B",)


def test_input_is_validated_against_the_level():
    data = raw("d02_uga_height")
    data["input"].pop("context")
    with pytest.raises(ValidationError, match="context"):
        Item.model_validate(data)
    surveyor_input_on_zoning = raw("z01_zone_boundary") | {"input": {"address": "x"}}
    with pytest.raises(ValidationError, match="parcel_ids"):
        Item.model_validate(surveyor_input_on_zoning)


def test_level_specific_fields():
    with pytest.raises(ValidationError, match="from_items is only for e2e"):
        Item.model_validate(raw("s01_joliot_curie") | {"from_items": ["x"]})
    statement = {"statement": "The site is CR0247"}
    with pytest.raises(ValidationError, match="statement facts are only for doc"):
        Item.model_validate(raw("s01_joliot_curie") | {"facts": [statement]})


def test_unknown_level_is_rejected():
    with pytest.raises(ValidationError, match="level"):
        Item.model_validate(raw("s01_joliot_curie") | {"level": "planner"})


def test_invalid_file_error_names_the_file(tmp_path):
    (tmp_path / "a.yaml").write_text("id: a\nlevel: surveyor\n", encoding="utf-8")
    with pytest.raises(ItemError, match=r"a\.yaml"):
        load_items(tmp_path)
    (tmp_path / "a.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    with pytest.raises(ItemError, match=r"a\.yaml"):
        load_item(tmp_path / "a.yaml")


def test_duplicate_ids_are_rejected(tmp_path):
    text = (ITEMS / "s01_joliot_curie.yaml").read_text(encoding="utf-8")
    (tmp_path / "a.yaml").write_text(text, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ItemError, match="duplicate item ids"):
        load_items(tmp_path)
