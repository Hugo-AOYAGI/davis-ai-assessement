import pytest

from agent.contracts.evidence import Ambiguity, Citation, ImageRegion, Resolution, SourceKind
from agent.contracts.findings.notes import DocNotes, Note, OpenPoint
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from evals.harness.items import Item
from evals.harness.judge import ANTI_PATTERNS, Judge, JudgePrompts, Question
from evals.harness.judging.views import ViewSettings
from evals.harness.scorers.notes import NO_OUTPUT, NotesScore, score_notes

ACROTERE = f"10 mètres à l{chr(0x2019)}acrotère"
SEP = "\n<<>>\n"


class ScriptedJudgeModel:
    def __init__(self, decide):
        self.decide = decide
        self.asked = []

    def invoke(self, messages, /):
        question, subject, output = messages[1].content.split(SEP)
        self.asked.append((Question(question), subject, output))
        return self.decide(Question(question), subject, output)


def judge_with(decide):
    model = ScriptedJudgeModel(decide)
    prompts = JudgePrompts(
        system="s", questions={q: f"{q.value}{SEP}$subject{SEP}$output" for q in Question}
    )
    views = ViewSettings(max_quote_chars=200, crops_link_base="evidence")
    return Judge(model, model_id="m", prompts=prompts, views=views), model


def no(question, subject, output):
    return {"verdict": "no", "reason": "not there"}


def item(level, payload, **extra):
    return Item.model_validate(
        {
            "id": "i",
            "level": level,
            "tests": "t",
            "status": "draft",
            "built_by": "test",
            "input": payload,
            **extra,
        }
    )


ZONING = item(
    "zoning",
    {"address": "a", "parcel_ids": ["P1"], "program": "housing"},
    must_flag=["The site lies across a zone boundary (UA / UH)"],
    must_not=["States zone UH", "States an EBC applies"],
)
DOC = item(
    "doc",
    {"label": "rules", "aim": "heights", "context": {"zone": "UGa", "program": "housing"}},
    facts=[
        {
            "statement": "Maximum height in UGa is 10 m",
            "critical": True,
            "evidence": [{"doc": "plu_reglement", "page": 91, "quote": ACROTERE}],
        },
        {"statement": "Footprint is 15 %"},
    ],
    must_not=["States a maximum height of 7 m"],
)
E2E = item(
    "e2e",
    {"address": "a", "program": "p"},
    must_flag=["Jeunes Actifs destination is undefined"],
)


def zone():
    return ZoneFindings(
        zone="UA",
        overlays=(
            LegendItem(item="Espaces Boisés Classés", applies=False, note="none near"),
            LegendItem(item="Linéaire commercial", applies=True, note="along the street"),
        ),
        rationale="Found by the church.",
        region=ImageRegion(doc="plan", page=1, region=(0, 0, 10, 10)),
        ambiguities=(
            Ambiguity(
                question="Is the site across the UA / UH boundary?",
                options=("UA", "UH"),
                chosen="UA",
                rationale="Most of it is UA.",
                resolved_by=Resolution.AGENT,
            ),
        ),
    )


def notes():
    real = Citation(doc="plu_reglement", page=91, quote=ACROTERE, source_kind=SourceKind.REGULATORY)
    return DocNotes(
        label="rules",
        notes=(
            Note(topic="footprint", text="Footprint 15 %.", citations=(real,)),
            Note(topic="height", text="Height 10 m at the acroterion.", citations=(real,)),
        ),
        open_points=(OpenPoint(question="Does 7 m apply?", why="struck through"),),
    )


def test_surveyor_items_ask_nothing():
    judge, model = judge_with(no)
    surveyor = item("surveyor", {"address": "a"})
    assert score_notes(surveyor, {"anything": 1}, judge) == NotesScore()
    assert model.asked == []


def test_zoning_must_flag_and_must_not(study):
    def decide(question, subject, output):
        hit = question is Question.MUST_FLAG or "UH" in subject
        return {"verdict": "yes" if hit else "no", "reason": "r"}

    judge, model = judge_with(decide)
    score = score_notes(ZONING, zone().model_dump(mode="json"), judge)
    assert [j.hit for j in score.must_flag] == [True]
    assert score.must_not_hits == (True, False)
    assert score.anti_patterns == ()
    _, subject, output = model.asked[0]
    assert subject == ZONING.must_flag[0]
    assert "Zone: UA" in output
    assert "[does not apply] Espaces Boisés Classés: none near" in output
    assert "[applies] Linéaire commercial" in output
    assert "Is the site across the UA / UH boundary? (options: UA | UH) chosen: UA" in output
    assert "Found by the church." in output


def test_doc_coverage_one_call_per_statement(matcher):
    def decide(question, subject, output):
        if question is Question.COVERS and "height" in subject:
            return {"verdict": "yes", "reason": "note 2", "notes": [2, 2, 9]}
        if question is Question.COVERS:
            return {"verdict": "no", "reason": "none", "notes": [1]}
        return {"verdict": "no", "reason": "r"}

    judge, model = judge_with(decide)
    score = score_notes(DOC, notes(), judge, matcher=matcher)
    covers = [entry for entry in model.asked if entry[0] is Question.COVERS]
    assert len(covers) == 2
    assert covers[0][2].startswith("[1] (footprint) Footprint 15 %.")
    assert "[2] (height) Height 10 m" in covers[0][2]
    assert [c.notes for c in score.coverage] == [(2,), ()]
    height, footprint = score.statements
    assert (height.correct, height.grounded, height.critical) == (True, True, True)
    assert (footprint.correct, footprint.grounded) == (False, False)
    assert score.must_not_hits == (False,)
    must_not_view = next(e[2] for e in model.asked if e[0] is Question.MUST_NOT)
    assert "Open points:" in must_not_view
    assert "Does 7 m apply?" in must_not_view


def test_doc_statements_need_a_matcher():
    judge, _ = judge_with(no)
    with pytest.raises(ValueError, match="matcher"):
        score_notes(DOC, notes(), judge)


def test_e2e_checks_the_six_anti_patterns_on_the_report(study):
    judge, model = judge_with(
        lambda q, s, o: {"verdict": "yes" if q is Question.HEDGING else "no", "reason": "r"}
    )
    score = score_notes(E2E, study, judge)
    assert [j.question for j in score.anti_patterns] == list(ANTI_PATTERNS)
    assert [j.hit for j in score.anti_patterns] == [True, False, False, False, False, False]
    assert all(entry[2].startswith("# Buildability study") for entry in model.asked)
    assert len(model.asked) == 1 + len(ANTI_PATTERNS)


def test_missing_output_costs_no_call(matcher):
    judge, model = judge_with(no)
    score = score_notes(DOC, None, judge, matcher=matcher)
    assert model.asked == []
    assert score.must_not_hits == (False,)
    assert [c.reason for c in score.coverage] == [NO_OUTPUT, NO_OUTPUT]
    assert [s.correct for s in score.statements] == [False, False]
    flagged = score_notes(ZONING, None, judge)
    assert [(j.hit, j.reason) for j in flagged.must_flag] == [(False, NO_OUTPUT)]
