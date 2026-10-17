import pytest
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agent.contracts.inputs.corpus import Section
from evals.harness.items import Evidence, KeyFact, StatementFact
from evals.harness.scorers.trajectory import RunCost, pages_read, score_trajectory

UMG = "plu_reglement/titre-ii/moulon/umg"


def section(section_id: str, start: int, end: int) -> Section:
    return Section(
        id=section_id,
        doc=section_id.partition("/")[0],
        heading_path=(section_id,),
        page_start=start,
        page_end=end,
        text="",
    )


SECTIONS = [
    section(UMG, 320, 320),
    section(f"{UMG}/10", 326, 326),
    section(f"{UMG}/12", 327, 330),
    section("plu_reglement/titre-i", 5, 8),
]


def call(name: str, call_id: str, **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def reply(call_id: str, status: str = "success") -> ToolMessage:
    return ToolMessage(content="ok", tool_call_id=call_id, status=status)


MESSAGES: list[BaseMessage] = [
    call("search", "1", query="hauteur"),
    reply("1"),
    call("read_section", "2", section_id=UMG),
    reply("2"),
    call("read_pages", "3", doc="plu_reglement", start=5, end=6),
    reply("3"),
    call("read_pages", "4", doc="plu_reglement", start=90, end=91),
    reply("4", "error"),
    call("view_image", "5", doc="oap", page=33),
    reply("5"),
    call("submit_notes", "6", label="rules"),
    reply("6", "error"),
    call("submit_notes", "7", label="rules"),
    reply("7"),
    call("read_pages", "8", doc="plu_reglement", start=374, end=375),
    reply("8"),
]


def fact(page: int, doc: str = "plu_reglement") -> KeyFact:
    return KeyFact(key=f"p{page}", expect=1, evidence=(Evidence(doc=doc, page=page),))


def test_pages_read_before_the_last_submission():
    full = pages_read(MESSAGES, sections=SECTIONS, mode="full_sections")
    assert full == {
        *(("plu_reglement", page) for page in (5, 6, 320, 326, 327, 328, 329, 330)),
        ("oap", 33),
    }
    navigation = pages_read(MESSAGES, sections=SECTIONS, mode="navigation")
    assert navigation == {
        ("plu_reglement", 5),
        ("plu_reglement", 6),
        ("plu_reglement", 320),
        ("oap", 33),
    }


def test_score_trajectory():
    facts = [
        fact(326),
        fact(91),
        fact(374),
        StatementFact(statement="OAP", evidence=(Evidence(doc="oap", page=33),)),
        KeyFact(key="zone", expect="UMG"),
    ]
    result = score_trajectory(
        MESSAGES,
        facts,
        sections=SECTIONS,
        mode="full_sections",
        cost=RunCost(cost_usd=0.3, wall_time_s=12.0),
    )
    assert result.tool_calls == {
        "search": 1,
        "read_section": 1,
        "read_pages": 3,
        "view_image": 1,
        "submit_notes": 2,
    }
    assert result.rejections == {"submit_notes": 1}
    assert [(r.fact, r.read) for r in result.reads] == [
        ("p326", True),
        ("p91", False),
        ("p374", False),
        ("OAP", True),
    ]
    assert result.read_share == 0.5
    assert result.cost.cost_usd == 0.3


def test_run_without_submission_counts_every_read():
    messages = MESSAGES[:4] + MESSAGES[-2:]
    assert ("plu_reglement", 374) in pages_read(messages, sections=SECTIONS, mode="navigation")
    result = score_trajectory(messages, [], sections=SECTIONS, mode="navigation")
    assert (result.read_share, result.rejections) == (None, {})


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="paged"):
        pages_read(MESSAGES, sections=SECTIONS, mode="paged")
