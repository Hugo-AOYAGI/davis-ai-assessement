import json
import logging
from pathlib import Path
from typing import cast

import pytest
from hydra.utils import instantiate
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from omegaconf import OmegaConf, open_dict

from agent.agents.config import load_config
from agent.contracts.evidence import Ambiguity, Citation, Limit, Resolution, Rule, SourceKind
from agent.contracts.findings.map import Overlay
from agent.contracts.findings.regulation import Admissibility, Verdict
from agent.contracts.findings.site import Parcel, SiteContext
from agent.contracts.geometry import Boundary, BoundaryKind, EnvelopeParameters, Polygon
from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page
from agent.contracts.study import Regime, Study, VerifiedStudy
from agent.tools.study.gate import submit_study_tool

PAGES = (
    Path(__file__).parents[2] / "runtime" / "citations" / "fixtures" / "plu_reglement_pages.json"
)
RECTANGLE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
KINDS = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)


def regulatory(page, article, quote):
    return Citation(
        doc="plu_reglement",
        page=page,
        article=article,
        quote=quote,
        source_kind=SourceKind.REGULATORY,
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


@pytest.fixture
def site():
    polygon = Polygon(crs="EPSG:2154", exterior=RECTANGLE)
    return SiteContext(
        address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
        longitude=2.16,
        latitude=48.71,
        parcels=(Parcel(id="91272000AB0123", area_m2=1200, polygon=polygon),),
        polygon=polygon,
        area_m2=1200,
        boundaries=tuple(
            Boundary(kind=kind, start=start, end=end)
            for kind, start, end in zip(KINDS, RECTANGLE[:-1], RECTANGLE[1:], strict=True)
        ),
        method="geocoded, single parcel",
        citations=(CADASTRE,),
    )


@pytest.fixture
def study():
    def limit(value, *citations):
        return Limit(value=value, rule="see article", citations=citations)

    return Study(
        address="4 rue Joliot Curie, 91190 Gif-sur-Yvette",
        program="RSE + RJA, two buildings",
        regime=Regime(
            zone="UMG",
            overlays=(Overlay(name="Espace boisé classé", applies=False, rationale="none drawn"),),
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
        envelope=EnvelopeParameters(
            setback_road_m=limit(5, DISTANCE),
            setback_side_m=limit(4, DISTANCE),
            setback_rear_m=limit(4, DISTANCE),
            max_height_m=limit(20, HEIGHT),
            max_storeys=limit(6, HEIGHT),
            max_footprint_ratio=limit(None, FOOTPRINT),
            min_green_ratio=limit(None),
        ),
        parking=(),
        conditions=(Rule(topic="access", text="Road at least 5 m wide.", citations=(ACCESS,)),),
        ambiguities=(
            Ambiguity(
                question="Which parcel does the address designate?",
                chosen="91272000AB0123",
                rationale="The geocoded point falls inside it.",
                resolved_by=Resolution.AGENT,
                citations=(CADASTRE,),
            ),
        ),
        summary="# Study",
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


def gate(policy="reject", corpus=fixture_corpus):
    return submit_study_tool(
        corpus=corpus,
        artifact="study",
        site_artifact="site",
        policy=policy,
        min_score=0.9,
        neighbour_pages=1,
        max_quote_chars=60,
        quad_segs=8,
        min_area_m2=1.0,
    )


def invoke(tool, study, site=None):
    artifacts = {} if site is None else {"site": site.model_dump(mode="json")}
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
    assert message(command).content == "study accepted."
    return VerifiedStudy.model_validate(command.update["artifacts"]["study"])


def citing(study, citation):
    regime = study.regime.model_copy(update={"citations": (citation,)})
    return study.model_copy(update={"regime": regime})


def test_verified_study_is_stored_with_envelope_and_deduplicated_checks(study, site):
    verified = stored(invoke(gate(), study, site))
    assert verified.study == study
    assert verified.site == site
    assert verified.envelope.site_area_m2 == pytest.approx(1200)
    assert verified.envelope.footprint_area_m2 == pytest.approx((40 - 4 - 4) * (30 - 5 - 4))
    assert verified.envelope.max_height_m == 20
    checks = verified.citation_checks
    assert [check.citation for check in checks][:3] == [
        ZONE,
        study.admissibility[0].citations[0],
        DISTANCE,
    ]
    assert len(checks) == 6
    assert all(check.verified for check in checks)
    assert CADASTRE not in [check.citation for check in checks]


def test_missing_site_is_rejected(study):
    content = rejection(invoke(gate(), study))
    assert "no site in state" in content
    assert "site_locator" in content
    assert "submit_site" in content


def test_fabricated_quote_is_rejected_with_path_and_score(study, site):
    fabricated = regulatory(326, "UMG 10", "La hauteur des constructions est limitée à 35 mètres")
    content = rejection(invoke(gate(), citing(study, fabricated), site))
    assert "- regime.citations.0 (plu_reglement p.326, UMG 10): quote not found verbatim" in content
    assert "< 0.90" in content
    assert "copy the exact text" in content


def test_duplicated_citation_lists_every_path(study, site):
    fabricated = regulatory(
        322, "UMG 3.2", "Toute voie nouvelle doit avoir une largeur de 8 mètres"
    )
    rule = study.conditions[0].model_copy(update={"citations": (fabricated,)})
    resubmitted = citing(study, fabricated).model_copy(update={"conditions": (rule,)})
    content = rejection(invoke(gate(), resubmitted, site))
    assert (
        "- regime.citations.0, conditions.0.citations.0 (plu_reglement p.322, UMG 3.2)" in content
    )
    assert content.count("quote not found") == 1


def test_wrong_page_is_reported(study, site):
    moved = HEIGHT.model_copy(update={"page": 320})
    content = rejection(invoke(gate(), citing(study, moved), site))
    assert (
        "(plu_reglement p.320, UMG 10): quote not found verbatim on p.320 or its neighbours"
        in content
    )
    assert "fix the page number" in content
    assert '"la hauteur maximale des constructions est limitée à 20 mè..."' in content


def test_changed_number_is_explained(study, site):
    changed = ACCESS.model_copy(
        update={"page": 321, "quote": ACCESS.quote.replace("5 mètres", "6 mètres")}
    )
    content = rejection(invoke(gate(), citing(study, changed), site))
    assert "its numbers differ from the page text, best on p.322)" in content


def test_unknown_document_lists_known_documents(study, site):
    unknown = ZONE.model_copy(update={"doc": "plu"})
    content = rejection(invoke(gate(), citing(study, unknown), site))
    assert "regime.citations.0 (plu p.320, UMG - caractère): unknown document 'plu'" in content
    assert "the corpus documents are plu_reglement." in content


def test_flag_policy_stores_unverified_checks(study, site, caplog):
    fabricated = regulatory(326, "UMG 10", "La hauteur des constructions est limitée à 35 mètres")
    with caplog.at_level(logging.WARNING, logger="agent.tools.study.gate"):
        verified = stored(invoke(gate(policy="flag"), citing(study, fabricated), site))
    (failed,) = [check for check in verified.citation_checks if not check.verified]
    assert failed.citation == fabricated
    assert failed.score < 0.9
    assert "1 unverified citation(s)" in caplog.text


MISLABELLED = HEIGHT.model_copy(update={"page": None, "source_kind": SourceKind.GEOMETRIC})
MISLABEL_ERROR = (
    "- regime.citations.0, ambiguities.0.citations.0 (plu_reglement): cites corpus document "
    "'plu_reglement' as geometric; corpus documents are regulatory sources: set source_kind to "
    "regulatory and give the page the quote is on."
)


def mislabelled(study, regime_citation):
    ambiguity = study.ambiguities[0].model_copy(update={"citations": (MISLABELLED,)})
    regime = study.regime.model_copy(update={"citations": (MISLABELLED, regime_citation)})
    return study.model_copy(update={"regime": regime, "ambiguities": (ambiguity,)})


def test_mislabelled_corpus_citation_is_rejected(study, site):
    content = rejection(invoke(gate(), mislabelled(study, ZONE), site))
    assert MISLABEL_ERROR in content
    assert content.count("cites corpus document") == 1


def test_mislabelled_corpus_citation_is_rejected_under_flag_with_unverified_ones(study, site):
    fabricated = regulatory(326, "UMG 10", "La hauteur des constructions est limitée à 35 mètres")
    content = rejection(invoke(gate(policy="flag"), mislabelled(study, fabricated), site))
    assert MISLABEL_ERROR in content
    assert "- regime.citations.1 (plu_reglement p.326, UMG 10): quote not found" in content


def test_other_geometric_citations_are_accepted_unchecked(study, site):
    verified = stored(invoke(gate(), citing(study, CADASTRE), site))
    assert verified.study.regime.citations == (CADASTRE,)
    assert all(check.citation.source_kind is SourceKind.REGULATORY for check in verified.citation_checks)
    assert CADASTRE not in [check.citation for check in verified.citation_checks]


def test_invalid_policy_fails_at_build_time():
    with pytest.raises(ValueError, match="unknown citation policy 'warn'"):
        gate(policy="warn")


def test_corpus_is_loaded_once(study, site):
    calls = []

    def counting():
        calls.append(1)
        return fixture_corpus()

    tool = gate(corpus=counting)
    assert not calls
    stored(invoke(tool, study, site))
    stored(invoke(tool, study, site))
    assert len(calls) == 1


def test_config_node_builds_the_tool(study, site):
    cfg = load_config()
    node = OmegaConf.create(
        {
            "_target_": "agent.tools.study.gate.submit_study_tool",
            "corpus": {"_target_": f"{__name__}.fixture_corpus", "_partial_": True},
            "artifact": "study",
            "site_artifact": "site",
            "policy": "${policies.citations.policy}",
            "min_score": "${policies.citations.min_score}",
            "neighbour_pages": "${policies.citations.neighbour_pages}",
            "max_quote_chars": "${policies.citations.max_quote_chars}",
            "quad_segs": "${policies.envelope.quad_segs}",
            "min_area_m2": "${policies.envelope.min_area_m2}",
        }
    )
    with open_dict(cfg):
        cfg.test_submit_study = node
    tool = instantiate(cfg.test_submit_study, _convert_="all")
    assert tool.name == "submit_study"
    stored(invoke(tool, study, site))
