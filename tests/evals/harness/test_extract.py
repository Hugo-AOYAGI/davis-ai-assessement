import pytest

from evals.harness.extract import KeyPathError, Segment, Selector, parse_key, resolve
from evals.harness.items import KeyFact


def test_parse_key_segments_and_selectors():
    assert parse_key('study.admissibility[building~"Sociale. [x]"].verdict') == (
        Segment("study", ()),
        Segment("admissibility", (Selector("building", "~", "Sociale. [x]"),)),
        Segment("verdict", ()),
    )
    assert parse_key("edges[other_side=public_land][length_m=2]") == (
        Segment(
            "edges",
            (Selector("other_side", "=", "public_land"), Selector("length_m", "=", "2")),
        ),
    )


@pytest.mark.parametrize("key", ["", ".a", "a.", "a[b]", "a[b=c", "a b", "1a", "a[b=c]x"])
def test_parse_key_rejects_bad_keys(key):
    with pytest.raises(KeyPathError):
        parse_key(key)


def test_limit_resolves_to_its_value_and_own_citations(study):
    [height] = resolve(study, 'envelope.rules.buildings[building~"Sociale"].max_height_m')
    assert height.value == 20.0
    assert height.path == "envelope.rules.buildings.0.max_height_m.value"
    assert height.citations == study.envelope.rules.buildings[0].max_height_m.citations


def test_field_inherits_citations_of_nearest_enclosing_object(study):
    [zone] = resolve(study, "study.regime.zone")
    assert zone.value == "UMG"
    assert zone.citations == study.study.regime.citations
    [verdict] = resolve(study, 'study.admissibility[building~"jeunes actifs"].verdict')
    assert verdict.value == "permitted"
    assert verdict.path == "study.admissibility.1.verdict"
    assert verdict.citations == study.study.admissibility[1].citations


def test_substring_selector_ignores_case_and_accents(study):
    assert len(resolve(study, 'study.admissibility[building~"SOCIALE ETUDIANTE"]')) == 1


def test_exact_selector_and_fan_out(study):
    assert len(resolve(study, "study.admissibility[verdict=permitted]")) == 2
    assert [r.value for r in resolve(study, "study.admissibility.verdict")] == [
        "permitted",
        "permitted",
    ]
    assert resolve(study, "study.admissibility[verdict=prohibited]") == []
    assert len(resolve(study, "site.edges[other_side=parcel]")) == 16


def test_list_field_resolves_to_one_element(study):
    [parcels] = resolve(study, "site.choice.parcel_ids")
    assert parcels.value == ["91272000CR0247"]
    assert parcels.citations == study.site.citations


def test_dict_output_resolves_like_the_model(study, study_json):
    key = "envelope.rules.min_green_ratio"
    assert resolve(study_json, key) == resolve(study, key)


def test_null_on_the_way_resolves_to_nothing(variant):
    no_footprint = variant(lambda data: data["envelope"]["proposal"].update(footprint=None))
    assert resolve(no_footprint, "envelope.proposal.footprint.crs") == []


def test_unknown_field_and_selector_on_scalar_raise(study):
    with pytest.raises(KeyPathError, match="no field 'polygon_area'"):
        resolve(study, "site.polygon_area")
    with pytest.raises(KeyPathError, match="not a list"):
        resolve(study, "study.regime[zone=UMG]")
    with pytest.raises(KeyPathError, match="no field 'nope'"):
        resolve(study, "study.admissibility[nope=x]")


def test_every_example_key_resolves_on_its_contract(items, study):
    outputs = {
        "s01_joliot_curie": study.site,
        "z01_zone_boundary": study.zone,
        "e01_reference": study,
    }
    for item_id, output in outputs.items():
        for fact in items[item_id].facts:
            assert isinstance(fact, KeyFact)
            assert resolve(output, fact.key), (item_id, fact.key)
