import pytest
from pydantic import ValidationError

from agent.contracts.evidence import Citation, ImageRegion, SourceKind
from agent.contracts.findings.notes import DocNotes, Note, OpenPoint
from agent.contracts.findings.site import Site


def region(*box):
    return ImageRegion(doc="oap", page=34, region=box)


def note(topic: str, citation: Citation) -> Note:
    return Note(topic=topic, text="What the page says.", citations=(citation,))


def test_region_accepts_a_box():
    assert region(0, 0, 10, 20).region == (0, 0, 10, 20)


@pytest.mark.parametrize("box", [(10, 0, 10, 5), (0, 8, 5, 3), (-1, 0, 5, 5), (0, -2, 5, 5)])
def test_region_rejects_empty_or_negative_boxes(box):
    with pytest.raises(ValidationError, match="x1 > x0 >= 0 and y1 > y0 >= 0"):
        region(*box)


def test_region_needs_four_values():
    with pytest.raises(ValidationError):
        ImageRegion.model_validate({"doc": "oap", "page": 34, "region": [0, 0, 10]})


def test_region_reads_a_json_list():
    parsed = ImageRegion.model_validate({"doc": "oap", "page": 34, "region": [1, 2, 3, 4]})
    assert parsed.region == (1, 2, 3, 4)


@pytest.mark.parametrize("label", ["Rules", "1rules", "rules-oap", ""])
def test_notes_label_pattern(label, citation: Citation):
    with pytest.raises(ValidationError):
        DocNotes(label=label, notes=(note("uses", citation),))


def test_notes_without_topics_accept_any_topic(citation: Citation):
    notes = DocNotes(label="chat_1", notes=(note("heights", citation),))
    assert notes.topics == ()


def test_notes_cover_every_topic(citation: Citation):
    notes = DocNotes(
        label="rules",
        topics=("uses", "height"),
        notes=(note("uses", citation), note("height", citation), note("uses", citation)),
        open_points=(OpenPoint(question="Which destination?", why="Not defined."),),
    )
    assert len(notes.notes) == 3


def test_notes_missing_and_extra_topics_are_named(citation: Citation):
    with pytest.raises(ValidationError) as info:
        DocNotes(
            label="rules",
            topics=("uses", "height"),
            notes=(note("uses", citation), note("parking", citation)),
        )
    message = str(info.value)
    assert "no note for topic 'height'" in message
    assert "topic 'parking' is not in topics" in message


def test_note_needs_a_citation():
    with pytest.raises(ValidationError):
        Note(topic="uses", text="x", citations=())


def test_site_rejects_regulatory_citations(site: Site, citation: Citation):
    data = site.model_dump()
    data["citations"] = [citation.model_dump()]
    with pytest.raises(ValidationError, match="geometric"):
        Site.model_validate(data)


def test_site_accepts_geometric_citations(site: Site):
    assert all(c.source_kind is SourceKind.GEOMETRIC for c in site.citations)
