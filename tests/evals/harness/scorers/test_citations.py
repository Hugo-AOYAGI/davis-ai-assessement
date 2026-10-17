from agent.contracts.evidence import Citation, SourceKind
from evals.harness.items import Evidence, KeyFact
from evals.harness.scorers.citations import check_evidence, located_citations, score_citations
from evals.harness.scorers.facts import score_facts

RASTER = "plu_reglement_graphique"
OAP_LABEL = "Secteur à Orientation d'Aménagement et de Programmation"


def test_real_study_citations_are_all_valid(study, matcher):
    result = score_citations(study, matcher, [])
    assert (result.text_verifiable, result.verified, result.raster) == (38, 38, 0)
    assert result.share_valid == 1.0
    assert result.share_facts_cited is None


def test_json_output_gives_the_same_checks(study, study_json, matcher):
    assert score_citations(study_json, matcher, []) == score_citations(study, matcher, [])
    paths = [path for path, _ in located_citations(study_json)]
    assert paths == [path for path, _ in located_citations(study)]
    assert paths[0].startswith("study.")


def test_fabricated_quote_lowers_the_share(variant, matcher):
    def fabricate(data):
        data["envelope"]["rules"]["buildings"][0]["max_height_m"]["citations"][0]["quote"] = (
            "Hauteur 25 mètres."
        )

    result = score_citations(variant(fabricate), matcher, [])
    assert result.verified == result.text_verifiable - 1
    failed = [c for c in result.checks if not c.check.verified]
    assert failed[0].paths == ("envelope.rules.buildings.0.max_height_m.citations.0",)


def test_share_of_facts_cited_on_an_evidence_page(items, study, matcher):
    facts = [
        f for f in items["e01_reference"].facts if f.key != "envelope.proposal.total_volume_m3"
    ]
    off_page = KeyFact(
        key='envelope.rules.buildings[building~"Sociale"].max_height_m',
        expect=18,
        evidence=(Evidence(doc="plu_reglement", page=100),),
    )
    result = score_citations(study, matcher, score_facts([*facts, off_page], study, matcher))
    assert (result.facts_with_evidence, result.facts_cited) == (3, 2)
    assert result.share_facts_cited == 2 / 3


def test_raster_citation_is_recorded_and_valid_when_it_names_the_legend_item(variant, matcher):
    plan = Citation(doc=RASTER, page=1, quote=OAP_LABEL, source_kind=SourceKind.REGULATORY)

    def cite_plan(data):
        data["study"]["regime"]["citations"].append(plan.model_dump(mode="json"))

    result = score_citations(variant(cite_plan), matcher, [])
    assert (result.raster, result.text_verifiable) == (1, 38)
    assert matcher.valid_on(plan, [Evidence(doc=RASTER, page=1, quote=OAP_LABEL.upper())])
    assert matcher.valid_on(plan, [Evidence(doc=RASTER, page=1)])
    assert not matcher.valid_on(plan, [Evidence(doc=RASTER, page=1, quote="Zone humide")])


def test_geometric_citations_never_ground(study, matcher):
    geometric = study.site.citations[0]
    assert not matcher.valid_on(geometric, [Evidence(doc=geometric.doc, page=1)])


def test_check_evidence_verifies_the_item_quotes(items, matcher):
    checks = check_evidence(items["d02_uga_height"].facts, matcher)
    assert len(checks) == 3
    assert all(check.verified for check in checks)
