import json
import logging
from pathlib import Path
from typing import cast

import pytest
from hydra.utils import instantiate
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from omegaconf import open_dict

from agent.adapters.images.pages import RegionError
from agent.agents.config import PROJECT_ROOT, load_config
from agent.contracts.envelope import (
    BuildingLimits,
    Distance,
    EnvelopeRules,
    EnvelopeStudy,
    Layout,
    OapChoice,
    SetbackRule,
)
from agent.contracts.evidence import (
    Ambiguity,
    Citation,
    ImageRegion,
    Limit,
    Resolution,
    Rule,
    SourceKind,
    StoredCrop,
)
from agent.contracts.findings.notes import DocNotes, Note, OpenPoint
from agent.contracts.findings.site import Edge, EdgeSide, Parcel, ParcelChoice, Site
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from agent.contracts.geometry import Boundary, BoundaryKind, Polygon
from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page
from agent.contracts.study import Admissibility, Regime, Study, Verdict, VerifiedStudy
from agent.runtime.geometry.envelope.study import EnvelopeSettings, compute_envelope_study
from agent.tools.study.checks import citation_rules
from agent.tools.study.gate import GeometrySettings, submit_study_tool
from agent.tools.study.inputs import Delivery, StudyInputs

PAGES = (
    Path(__file__).parents[2] / "runtime" / "citations" / "fixtures" / "plu_reglement_pages.json"
)
RECTANGLE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
SIDES = (EdgeSide.PUBLIC_LAND, EdgeSide.PARCEL, EdgeSide.PARCEL, EdgeSide.PARCEL)


def regulatory(page, article, quote, doc="plu_reglement"):
    return Citation(
        doc=doc, page=page, article=article, quote=quote, source_kind=SourceKind.REGULATORY
    )


ZONE = regulatory(
    320, "UMG - caractère", "La zone UMG correspond au quartier Joliot-Curie, situé au nord"
)
HOUSING = regulatory(
    320,
    "UMG - caractère",
    "des constructions à destination d'habitation, au bénéfice des étudiants, des chercheurs, "
    "et des familles",
)
ACCESS = regulatory(
    322,
    "UMG 3.2",
    "Aucune voie d'intérêt public ou privé ne doit avoir une largeur inférieure à 5 mètres pour "
    "une circulation à double sens",
)
DISTANCE = regulatory(
    326, "UMG 8", "6 mètres, si les deux façades ou parties de façades concernées ne comportent"
)
FOOTPRINT = regulatory(326, "UMG 9", "L'emprise au sol des constructions n'est pas réglementée")
HEIGHT = regulatory(
    326,
    "UMG 10",
    "la hauteur maximale des constructions est limitée à 20 mètres, avec un nombre de niveaux "
    "limité à R+5",
)
CADASTRE = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)
PLAN_REGION = ImageRegion(doc="plu_reglement_graphique", page=1, region=(10, 20, 110, 90))
OAP_VIEW = ImageRegion(doc="oap", page=34, region=(120, 400, 900, 1100))
RJA_QUESTION = "Which destination covers a Résidence Jeunes Actifs?"
OAP_QUESTION = "Does the OAP perimeter cover the whole parcel?"
SPACING_QUESTION = "Does UMG 8 apply to two buildings joined by a podium?"
OAP_ALIGNMENT = regulatory(34, None, "alignement", doc="oap")
KINDS = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)


@pytest.fixture
def site():
    polygon = Polygon(crs="EPSG:2154", exterior=RECTANGLE)
    return Site(
        address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
        longitude=2.16,
        latitude=48.71,
        choice=ParcelChoice(
            address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
            parcel_ids=("91272000AB0123",),
            rationale="Only parcel at the address.",
        ),
        parcels=(Parcel(id="91272000AB0123", area_m2=1200, polygon=polygon),),
        polygon=polygon,
        area_m2=1200,
        edges=tuple(
            Edge(start=start, end=end, length_m=1, other_side=side)
            for side, start, end in zip(SIDES, RECTANGLE[:-1], RECTANGLE[1:], strict=True)
        ),
        citations=(CADASTRE,),
    )


@pytest.fixture
def zone():
    return ZoneFindings(
        zone="UMG",
        overlays=(
            LegendItem(item="Périmètre d'OAP", applies=True, note="site inside"),
            LegendItem(item="Espace boisé classé", applies=False, note="none drawn"),
        ),
        rationale="Site found by the road layout.",
        region=PLAN_REGION,
    )


@pytest.fixture
def rules():
    return DocNotes(
        label="rules",
        notes=(
            Note(topic="height", text="20 m, R+5.", citations=(HEIGHT,)),
            Note(topic="setbacks", text="6 m without windows.", citations=(DISTANCE,)),
            Note(topic="footprint", text="Not regulated.", citations=(FOOTPRINT,)),
        ),
        open_points=(OpenPoint(question=RJA_QUESTION, options=("habitation",), why="Not in PLU."),),
    )


@pytest.fixture
def oap():
    note = Note(
        topic="building_form",
        text="Aligned on the street.",
        citations=(OAP_ALIGNMENT,),
        views=(OAP_VIEW, PLAN_REGION, OAP_VIEW),
    )
    return DocNotes(
        label="oap",
        notes=(note,),
        open_points=(OpenPoint(question=OAP_QUESTION, why="The diagram is schematic."),),
    )


@pytest.fixture
def destinations():
    return DocNotes(
        label="destinations",
        notes=(Note(topic="housing", text="Hébergement.", citations=(HOUSING,)),),
    )


def distance(min_m):
    return Distance(min_m=min_m, rule="see article", citations=(DISTANCE,))


def limit(value, *citations):
    return Limit(value=value, rule="see article", citations=citations)


@pytest.fixture
def envelope_rules():
    return EnvelopeRules(
        setbacks=(
            SetbackRule(kind=BoundaryKind.ROAD, on_limit_allowed=False, with_windows=distance(5)),
            SetbackRule(kind=BoundaryKind.SIDE, on_limit_allowed=False, with_windows=distance(4)),
            SetbackRule(kind=BoundaryKind.REAR, on_limit_allowed=False, with_windows=distance(4)),
        ),
        buildings=(
            BuildingLimits(
                building="A", max_height_m=limit(20, HEIGHT), max_storeys=limit(6, HEIGHT)
            ),
        ),
        spacing_with_windows=distance(10),
        spacing_without_windows=distance(6),
        max_footprint_ratio=limit(None, FOOTPRINT),
        min_green_ratio=limit(0.5, DISTANCE),
    )


@pytest.fixture
def layout():
    return Layout(
        cut="along_long_axis",
        first_share=0.5,
        order=("A",),
        facing_windows=False,
        reasons="One building on the whole footprint.",
    )


def boundaries():
    return tuple(
        Boundary(kind=kind, start=start, end=end)
        for kind, start, end in zip(KINDS, RECTANGLE[:-1], RECTANGLE[1:], strict=True)
    )


def compute(rules, layout, open_points=()):
    return compute_envelope_study(
        Polygon(crs="EPSG:2154", exterior=RECTANGLE),
        boundaries(),
        rules,
        layout,
        settings=ENVELOPE,
        open_points=open_points,
    )


@pytest.fixture
def envelope(envelope_rules, layout):
    return compute(envelope_rules, layout)


def ambiguity(question):
    return Ambiguity(
        question=question,
        chosen="yes",
        rationale="Best supported reading.",
        resolved_by=Resolution.AGENT,
    )


@pytest.fixture
def study():
    return Study(
        address="4 rue Joliot Curie, 91190 Gif-sur-Yvette",
        program="RSE + RJA, two buildings",
        regime=Regime(
            zone="UMG",
            overlays=(LegendItem(item="Périmètre d'OAP", applies=True, note="site inside"),),
            oap_applicable=True,
            citations=(ZONE,),
        ),
        admissibility=(
            Admissibility(
                building="A",
                stated_use="Résidence sociale étudiante",
                destination="Habitation / Hébergement",
                verdict=Verdict.PERMITTED,
                citations=(HOUSING,),
            ),
        ),
        parking=(),
        conditions=(Rule(topic="access", text="Road at least 5 m wide.", citations=(ACCESS,)),),
        ambiguities=(
            ambiguity(" which DESTINATION covers a  Résidence Jeunes Actifs? "),
            ambiguity(OAP_QUESTION),
        ),
        summary="### Study",
    )


def fixture_corpus():
    raw = json.loads(PAGES.read_text(encoding="utf-8"))
    return Corpus(
        id="test",
        documents=(
            Document(
                id="plu_reglement",
                kind=DocumentKind.REGULATORY_TEXT,
                title="PLU - Règlement",
                path=Path("ressources/plu_reglement_91272_20210706.pdf"),
                page_count=465,
            ),
        ),
        pages=tuple(
            Page(doc="plu_reglement", number=int(number), text=text) for number, text in raw.items()
        ),
        sections=(),
    )


class FakeImages:
    """Writes a placeholder PNG per region; refuses the regions listed in ``invalid``."""

    def __init__(self, root, invalid=()):
        self.root = root
        self.invalid = set(invalid)
        self.saved = []

    def save_crop(self, region, directory):
        if region in self.invalid:
            msg = f"region {list(region.region)} exceeds the overview"
            raise RegionError(msg)
        x0, y0, x1, y1 = region.region
        target = directory / f"{region.doc}_p{region.page}_{x0}-{y0}-{x1}-{y1}.png"
        directory.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png")
        self.saved.append(region)
        return StoredCrop(
            region=region,
            pixels=(x0 * 2, y0 * 2, x1 * 2, y1 * 2),
            path=target.relative_to(self.root).as_posix(),
        )


INPUTS = StudyInputs(
    site=Delivery(artifact="site", producer="surveyor"),
    zone=Delivery(artifact="zone", producer="zoning_analyst"),
    notes=Delivery(artifact="notes.{label}", producer="doc_analyst"),
    envelope=Delivery(artifact="envelope", producer="architect"),
    labels=("rules", "oap", "destinations"),
    rules_label="rules",
    oap_label="oap",
)
GEOMETRY = GeometrySettings(snap_tolerance_m=0.5, collinear_angle_deg=20)
ENVELOPE = EnvelopeSettings(level_step_m=1, quad_segs=8, min_area_m2=1, cut_tolerance_m=0.01)


@pytest.fixture
def images(tmp_path):
    return FakeImages(tmp_path)


@pytest.fixture
def make_gate(tmp_path, images):
    def make(policy="reject", corpus=fixture_corpus, store=None):
        return submit_study_tool(
            name="submit_study",
            artifact="study",
            corpus=corpus,
            citations=citation_rules(
                policy=policy,
                min_score=0.9,
                neighbour_pages=1,
                max_quote_chars=60,
                check_raster=False,
            ),
            inputs=INPUTS,
            geometry=GEOMETRY,
            envelope=ENVELOPE,
            images=store or images,
            crops_dir=tmp_path / "crops",
        )

    return make


@pytest.fixture
def notes(rules, oap, destinations):
    return {
        f"notes.{doc_notes.label}": doc_notes.model_dump(mode="json")
        for doc_notes in (rules, oap, destinations)
    }


@pytest.fixture
def findings(site, zone, notes, envelope):
    return {
        "site": site.model_dump(mode="json"),
        "zone": zone.model_dump(mode="json"),
        **notes,
        "envelope": envelope.model_dump(mode="json"),
    }


FABRICATED = regulatory(326, "UMG 10", "La hauteur des constructions est limitée à 35 mètres")


def invoke(tool, study, artifacts):
    runtime = ToolRuntime(
        state={"messages": [], "artifacts": artifacts},
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="1",
        store=None,
    )
    args = {**study.model_dump(mode="json"), "runtime": runtime}
    result = tool.invoke({"type": "tool_call", "id": "1", "name": tool.name, "args": args})
    assert isinstance(result, Command)
    return cast("Command[str]", result)


def message(command):
    (only,) = command.update["messages"]
    assert isinstance(only, ToolMessage)
    return only


def rejection(command):
    assert "artifacts" not in command.update
    reply = message(command)
    assert reply.status == "error"
    assert reply.content.startswith("submit_study rejected, nothing was stored.")
    return reply.content


def stored(command):
    assert message(command).content.startswith("study accepted.")
    return VerifiedStudy.model_validate(command.update["artifacts"]["study"])


def citing(study, citation):
    regime = study.regime.model_copy(update={"citations": (citation,)})
    return study.model_copy(update={"regime": regime})


def test_accepted_study_is_completed(make_gate, study, findings, site, zone):
    verified = stored(invoke(make_gate(), study, findings))
    assert verified.study == study
    assert verified.site == site
    assert verified.zone == zone
    checks = verified.citation_checks
    assert [check.citation for check in checks][:2] == [ZONE, study.admissibility[0].citations[0]]
    assert len(checks) == 6
    assert all(check.verified for check in checks)


def test_edges_are_labelled(make_gate, study, findings):
    verified = stored(invoke(make_gate(), study, findings))
    assert [boundary.kind for boundary in verified.boundaries] == [
        BoundaryKind.ROAD,
        BoundaryKind.SIDE,
        BoundaryKind.REAR,
        BoundaryKind.SIDE,
    ]


def test_envelope_applies_setbacks_and_green_cap(make_gate, study, findings):
    envelope = stored(invoke(make_gate(), study, findings)).envelope
    windows = envelope.bounds[1]
    assert windows.footprint_area_m2 == pytest.approx((40 - 4 - 4) * (30 - 5 - 4))
    assert envelope.min_green_area_m2 == pytest.approx(600)
    assert windows.buildings[0].footprint_area_m2 == pytest.approx(600)
    assert envelope.proposal.total_volume_m3 == pytest.approx(600 * 20)


def test_envelope_is_recomputed(make_gate, study, findings, envelope):
    proposal = envelope.proposal.model_copy(update={"total_volume_m3": 1.0})
    findings["envelope"] = envelope.model_copy(update={"proposal": proposal}).model_dump(
        mode="json"
    )
    verified = stored(invoke(make_gate(), study, findings))
    assert verified.envelope == envelope


def test_reply_gives_the_envelope_figures(make_gate, study, findings):
    reply = message(invoke(make_gate(), study, findings)).content
    assert reply.startswith("study accepted.\n\nEnvelope recomputed by the gate")
    for line in (
        "- Site limits (edges by kind): 1 road, 2 side, 1 rear",
        "- Evidence crops saved: 2",
        "Site area: 1200 m²; minimum green area: 600 m²",
        "Bound largest",
        "Bound windows",
        "Proposal (cut along_long_axis",
        "- A: ground 600 m², height 20 m, volume 12000 m³",
    ):
        assert line in reply


def test_evidence_crops_are_saved_once(make_gate, study, findings, images, tmp_path):
    verified = stored(invoke(make_gate(), study, findings))
    assert [crop.region for crop in verified.evidence] == [PLAN_REGION, OAP_VIEW]
    assert images.saved == [PLAN_REGION, OAP_VIEW]
    for crop in verified.evidence:
        assert (tmp_path / crop.path).is_file()
        assert crop.path.startswith("crops/")


def test_rejected_study_saves_no_crop(make_gate, study, findings, images):
    rejection(invoke(make_gate(), citing(study, FABRICATED), findings))
    assert images.saved == []


def test_unsaved_crop_names_its_producer(make_gate, study, findings, tmp_path):
    store = FakeImages(tmp_path, invalid=(OAP_VIEW,))
    content = rejection(invoke(make_gate(store=store), study, findings))
    assert "(evidence) oap p.34 [120, 400, 900, 1100] from `notes.oap`: region" in content
    assert "Delegate to doc_analyst again" in content


@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        ("site", "no `site` artifact in state. Delegate to surveyor"),
        ("zone", "no `zone` artifact in state. Delegate to zoning_analyst"),
        ("notes.rules", "no `notes.rules` artifact in state. Delegate to doc_analyst with the"),
        ("notes.oap", "`oap` task of the playbook (label `oap`)"),
        ("notes.destinations", "(label `destinations`)"),
        ("envelope", "no `envelope` artifact in state. Delegate to architect"),
    ],
)
def test_missing_artifact_names_the_subagent(make_gate, study, findings, missing, expected):
    del findings[missing]
    content = rejection(invoke(make_gate(), study, findings))
    assert expected in content
    assert content.count("artifact in state") == 1


def test_every_missing_artifact_is_listed(make_gate, study):
    content = rejection(invoke(make_gate(), study, {}))
    assert content.count("artifact in state") == 6


def test_unmatched_open_points_are_listed(make_gate, study, findings):
    resubmitted = study.model_copy(update={"ambiguities": ()})
    content = rejection(invoke(make_gate(), resubmitted, findings))
    assert f'the open point "{RJA_QUESTION}" of `notes.rules` has no ambiguity' in content
    assert f'the open point "{OAP_QUESTION}" of `notes.oap` has no ambiguity' in content
    assert "copies this text exactly" in content


def test_open_point_and_citation_errors_are_reported_together(make_gate, study, findings):
    resubmitted = citing(study, FABRICATED).model_copy(
        update={"ambiguities": study.ambiguities[:1]}
    )
    content = rejection(invoke(make_gate(), resubmitted, findings))
    assert OAP_QUESTION in content
    assert RJA_QUESTION not in content
    assert "regime.citations.0 (plu_reglement p.326, UMG 10): quote not found verbatim" in content


def test_fabricated_quote_is_rejected_with_path_and_score(make_gate, study, findings):
    content = rejection(invoke(make_gate(), citing(study, FABRICATED), findings))
    assert "- regime.citations.0 (plu_reglement p.326, UMG 10): quote not found verbatim" in content
    assert "< 0.90" in content
    assert "copy the exact text" in content


def test_wrong_page_is_reported(make_gate, study, findings):
    moved = HEIGHT.model_copy(update={"page": 320})
    content = rejection(invoke(make_gate(), citing(study, moved), findings))
    assert "quote not found verbatim on p.320 or its neighbours" in content
    assert "fix the page number" in content


def test_unknown_document_lists_known_documents(make_gate, study, findings):
    unknown = ZONE.model_copy(update={"doc": "plu"})
    content = rejection(invoke(make_gate(), citing(study, unknown), findings))
    assert "unknown document 'plu'; the corpus documents are plu_reglement." in content


def test_flag_policy_stores_unverified_checks(make_gate, study, findings, caplog):
    with caplog.at_level(logging.WARNING, logger="agent"):
        verified = stored(invoke(make_gate(policy="flag"), citing(study, FABRICATED), findings))
    (failed,) = [check for check in verified.citation_checks if not check.verified]
    assert failed.citation == FABRICATED
    assert "1 unverified citation(s)" in caplog.text


def test_mislabelled_corpus_citation_is_rejected(make_gate, study, findings):
    mislabelled = DISTANCE.model_copy(update={"page": None, "source_kind": SourceKind.GEOMETRIC})
    content = rejection(invoke(make_gate(), citing(study, mislabelled), findings))
    assert "cites corpus document 'plu_reglement' as geometric" in content


def test_geometric_citations_are_accepted_unchecked(make_gate, study, findings):
    verified = stored(invoke(make_gate(), citing(study, CADASTRE), findings))
    assert CADASTRE not in [check.citation for check in verified.citation_checks]


def test_invalid_policy_fails_at_build_time(make_gate):
    with pytest.raises(ValueError, match="unknown citation policy 'warn'"):
        make_gate(policy="warn")


def test_corpus_is_loaded_once(make_gate, study, findings):
    calls = []

    def counting():
        calls.append(1)
        return fixture_corpus()

    tool = make_gate(corpus=counting)
    assert not calls
    stored(invoke(tool, study, findings))
    stored(invoke(tool, study, findings))
    assert len(calls) == 1


def test_notes_key_needs_a_label_placeholder():
    with pytest.raises(ValueError, match="placeholder"):
        StudyInputs.model_validate(
            {**INPUTS.model_dump(), "notes": {"artifact": "notes", "producer": "doc_analyst"}}
        )


def test_notes_labels_are_read_from_the_keys():
    keys = ("site", "notes.rules", "notes.rules_parking", "notes.", "envelope")
    assert INPUTS.notes_labels(keys) == ["rules", "rules_parking"]


def test_config_node_builds_the_tool(study, findings, tmp_path):
    cfg = load_config()
    node = cfg.agent.tools[1]
    assert node.inputs.labels == ["rules", "oap", "destinations"]
    with open_dict(cfg):
        node.corpus = {"_target_": f"{__name__}.fixture_corpus", "_partial_": True}
        node.images = {"_target_": f"{FakeImages.__module__}.FakeImages", "root": str(tmp_path)}
        node.crops_dir = {"_target_": "pathlib.Path", "_args_": [str(tmp_path / "crops")]}
    tool = instantiate(node, _convert_="all")
    assert tool.name == "submit_study"
    stored(invoke(tool, study, findings))


def test_default_crops_dir_is_under_the_project_root():
    cfg = load_config()
    crops_dir = instantiate(cfg.agent.tools[1].crops_dir)
    assert crops_dir == PROJECT_ROOT / cfg.policies.evidence.crops_dir


def store_envelope(findings, envelope):
    findings["envelope"] = envelope.model_dump(mode="json")


def test_envelope_citation_outside_the_rules_notes_is_rejected(
    make_gate, study, findings, envelope_rules, layout
):
    foreign = Distance(min_m=4, rule="see article", citations=(ACCESS,))
    side = envelope_rules.setbacks[1].model_copy(update={"with_windows": foreign})
    rules = envelope_rules.model_copy(
        update={"setbacks": (envelope_rules.setbacks[0], side, envelope_rules.setbacks[2])}
    )
    store_envelope(findings, compute(rules, layout))
    content = rejection(invoke(make_gate(), study, findings))
    assert (
        "envelope.rules.setbacks.1.with_windows.citations.0 (plu_reglement p.322, UMG 3.2): "
        "not a citation of `notes.rules`. Delegate to architect again" in content
    )


def test_layout_oap_citation_must_come_from_the_oap_notes(
    make_gate, study, findings, envelope_rules, layout
):
    def choice(citation):
        prescription = Rule(topic="alignment", text="On the street.", citations=(citation,))
        return OapChoice(prescription=prescription, how="A on the alignment.")

    store_envelope(
        findings, compute(envelope_rules, layout.model_copy(update={"oap": (choice(HEIGHT),)}))
    )
    content = rejection(invoke(make_gate(), study, findings))
    path = "envelope.layout.oap.0.prescription.citations.0"
    assert f"{path} (plu_reglement p.326, UMG 10): not a citation of `notes.oap`" in content
    store_envelope(
        findings,
        compute(envelope_rules, layout.model_copy(update={"oap": (choice(OAP_ALIGNMENT),)})),
    )
    content = rejection(invoke(make_gate(), study, findings))
    assert "not a citation of `notes.oap`" not in content
    assert f"{path} (oap p.34): unknown document 'oap'" in content


def test_layout_height_above_the_maximum_is_rejected(make_gate, study, findings, envelope):
    taller = envelope.layout.model_copy(update={"heights_m": (25.0,)})
    store_envelope(findings, envelope.model_copy(update={"layout": taller}))
    content = rejection(invoke(make_gate(), study, findings))
    assert "envelope.layout.heights_m.0: 25 m is above the maximum height of 'A' (20 m)" in content


def test_buildings_must_match_admissibility(make_gate, study, findings, envelope_rules, layout):
    limits = envelope_rules.buildings[0]
    rules = envelope_rules.model_copy(
        update={"buildings": (limits, limits.model_copy(update={"building": "B"}))}
    )
    store_envelope(findings, compute(rules, layout.model_copy(update={"order": ("A", "B")})))
    content = rejection(invoke(make_gate(), study, findings))
    assert (
        "envelope.rules.buildings: buildings 'A', 'B' do not match admissibility buildings 'A'"
        in content
    )


def test_envelope_open_points_need_an_ambiguity(make_gate, study, findings, envelope_rules, layout):
    point = OpenPoint(question=SPACING_QUESTION, why="UMG 8 is silent.")
    store_envelope(findings, compute(envelope_rules, layout, open_points=(point,)))
    content = rejection(invoke(make_gate(), study, findings))
    assert f'the open point "{SPACING_QUESTION}" of `envelope` has no ambiguity' in content
    answered = study.model_copy(
        update={"ambiguities": (*study.ambiguities, ambiguity(SPACING_QUESTION))}
    )
    stored(invoke(make_gate(), answered, findings))


def test_open_points_of_every_notes_artifact_are_checked(make_gate, study, findings):
    extra = DocNotes(
        label="rules_parking",
        notes=(Note(topic="parking", text="1 space.", citations=(HEIGHT,)),),
        open_points=(OpenPoint(question="Is the cap per unit?", why="Unclear."),),
    )
    findings["notes.rules_parking"] = extra.model_dump(mode="json")
    content = rejection(invoke(make_gate(), study, findings))
    assert (
        'the open point "Is the cap per unit?" of `notes.rules_parking` has no ambiguity' in content
    )


def test_envelope_citations_are_checked_and_numbered(make_gate, study, findings):
    verified = stored(invoke(make_gate(), study, findings))
    cited = [check.citation for check in verified.citation_checks]
    assert cited == [ZONE, HOUSING, ACCESS, DISTANCE, HEIGHT, FOOTPRINT]


def test_accepted_envelope_is_typed(make_gate, study, findings):
    assert isinstance(stored(invoke(make_gate(), study, findings)).envelope, EnvelopeStudy)
