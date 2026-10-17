from agent.contracts.evidence import Citation, CitationCheck, Limit, SourceKind
from agent.runtime.report.render import render_report


def render(verified, max_quote_chars=200):
    return render_report(verified, max_quote_chars=max_quote_chars, crops_link_base="evidence")


HEADINGS = (
    "# Buildability study: 4 rue Joliot Curie, 91190 Gif-sur-Yvette",
    "## Summary",
    "## Site",
    "## Regulatory regime",
    "## Program admissibility",
    "## Envelope",
    "## Parking",
    "## Other conditions",
    "## Ambiguities",
    "## Evidence",
    "## Citations",
)


def line_with(report, *fragments):
    return next(line for line in report.splitlines() if all(f in line for f in fragments))


def test_headings_in_order(verified):
    lines = render(verified).splitlines()
    positions = [lines.index(heading) for heading in HEADINGS]
    assert positions == sorted(positions)


def test_header_summary_and_site(verified):
    report = render(verified)
    assert "**Program:** RSE + RJA, two buildings" in report
    assert "The program is **buildable** in zone UMG." in report
    assert "| 91272000AB0123 | 1200 |" in report
    assert "- Site area: 1200 m²" in report
    assert "- Cadastre is current." in report
    assert "### Parcel choice\n\nAddress point 2.5 m from AB0123; AB0124 rejected" in report
    assert "| road | 1 | 40 m |" in report
    assert "| side | 2 | 60 m |" in report
    assert "| rear | 1 | 40 m |" in report
    assert "- (cadastre): 91272000AB0123" in report
    assert "- (ban): 4 Rue Joliot Curie" in report


def test_regime_and_admissibility(verified):
    report = render(verified)
    assert "Zone: **UMG** [1, 3]" in report
    assert "Zone read on the plan: **UMG**. Site found by the road layout" in report
    assert "| Linéaire commercial | along the street |" in report
    assert "Checked on the plan, not applying: Espace boisé classé." in report
    assert "OAP applicable: **yes**" in report
    assert "- **landscape**: Keep a planted strip. [5]" in report
    row = line_with(report, "| B |")
    assert "| conditional | Social mix required | [3] |" in row
    assert "| permitted | none | [3] |" in line_with(report, "| A |")


def test_envelope_rules(verified):
    report = render(verified)
    assert "Site area: 1200 m². Minimum green area: 240 m²." in report
    assert "| road | not allowed | 5 m: see article | — | [2] |" in report
    assert "| rear | allowed | — | 4 m: see article | [1] |" in report
    assert "| A | 20 m | 6 | see article | [1] |" in report
    assert "| B | 18 m | not set | see article | [1] |" in report
    assert "| Spacing, no facing window | 6 m: see article | [1] |" in report
    assert "| Maximum footprint ratio | not set: see article |  |" in report
    assert "| Minimum green ratio | 20%: see article | [1] |" in report


def test_bounds(verified):
    report = render(verified)
    largest = report.split("### Bound: largest", 1)[1].split("### Bound: windows", 1)[0]
    assert "Ground footprint after setbacks: 800 m². Total volume: 16000 m³." in largest
    assert "| A | 800 m² | 20 m | 16000 m³ | 0-20 m: 800 m² | yes |" in largest
    assert "| B | 800 m² | 18 m | 14400 m³ | 0-18 m: 800 m² | yes |" in largest
    windows = report.split("### Bound: windows", 1)[1].split("### Proposal", 1)[0]
    assert "| A | 672 m² | 20 m | 13440 m³ |" in windows


def test_proposal(verified):
    report = render(verified)
    proposal = report.split("### Proposal", 1)[1].split("### Envelope assumptions", 1)[0]
    assert proposal.startswith(
        "\n\nCut along long axis, first share 50%, order A, B, facing facades without windows."
    )
    row = line_with(proposal, "| A |")
    assert "| 20 m |" in row
    assert row.endswith("| yes |")
    assert "| 18 m |" in line_with(proposal, "| B |")
    assert "**Reasons**: A on the street, B at the back." in proposal
    assert (
        "- **landscape**: Keep a planted strip. Followed by: B set back behind the strip. [5]"
        in (proposal)
    )
    assumptions = report.split("### Envelope assumptions", 1)[1].split("## Parking", 1)[0]
    assert "- Every facade facing a limit has windows" in assumptions


def test_proposal_that_does_not_fit(verified):
    proposal = verified.envelope.proposal.model_copy(
        update={"fits": False, "warnings": ("The spacing does not fit.",)}
    )
    envelope = verified.envelope.model_copy(update={"proposal": proposal})
    report = render(verified.model_copy(update={"envelope": envelope}))
    section = report.split("### Proposal", 1)[1]
    assert "- **Warning**: The spacing does not fit." in section
    assert line_with(section, "| A |").endswith("| no |")


def test_parking_conditions_and_ambiguities(verified):
    report = render(verified)
    assert (
        "| résidence étudiante | 1 space per 150 m² of floor area | 1 place / 150 m² SDP | [4] |"
        in (report)
    )
    assert "- **access**: Access from a public road. [1]" in report
    assert "1. **Is the RJA a hébergement?**" in report
    assert "   - Options: hébergement; logement" in report
    assert "   - Chosen: hébergement" in report
    assert "   - Resolved by: agent" in report
    assert "   - Sources: [3]" in report


def test_citations_table(verified):
    report = render(verified)
    citations = report.split("## Citations", 1)[1]
    assert "| 1 | plu_reglement | 327 | UMG 10 | La hauteur maximale est fixée à 20 mètres |" in (
        citations
    )
    assert "| verified | 0.99 |" in line_with(citations, "| 1 |")
    assert "Recul minimal de 5 mètres \\| par rapport" in citations
    assert "| verified (found on p.326) | 0.91 |" in line_with(citations, "| 2 |")
    assert "| NOT VERIFIED | 0.43 |" in line_with(citations, "| 4 |")


def test_raster_citation_is_numbered_but_not_text_verifiable(verified):
    plan = Citation(
        doc="plu_reglement_graphique",
        page=1,
        article="Légende",
        quote="UMG",
        source_kind=SourceKind.REGULATORY,
    )
    regime = verified.study.regime.model_copy(update={"citations": (plan,)})
    study = verified.study.model_copy(update={"regime": regime})
    check = CitationCheck(citation=plan, verified=False, score=0.0, text_verifiable=False)
    report = render(
        verified.model_copy(
            update={"study": study, "citation_checks": (*verified.citation_checks, check)}
        ),
        max_quote_chars=200,
    )
    assert "Zone: **UMG** [6]" in report
    row = line_with(report.split("## Citations", 1)[1], "| 6 |")
    assert row.endswith(
        "| plu_reglement_graphique | 1 | Légende | UMG | not text-verifiable (raster) | — |"
    )
    assert "NOT VERIFIED" not in row


def test_long_quote_truncated(verified):
    report = render(verified, max_quote_chars=60)
    row = line_with(report.split("## Citations", 1)[1], "| 5 |")
    quote = row.split(" | ")[4]
    assert quote.endswith("…")
    assert len(quote) == 60


def test_uncited_and_unchecked_citations(verified):
    regime = verified.study.regime.model_copy(update={"citations": (verified.site.citations[0],)})
    study = verified.study.model_copy(update={"regime": regime, "ambiguities": ()})
    report = render(verified.model_copy(update={"study": study, "citation_checks": ()}))
    assert "Zone: **UMG** (cadastre)" in report
    assert "| A | 20 m | 6 | see article | (plu_reglement, p.327) |" in report
    assert "No regulatory citation was checked." in report
    assert "## Ambiguities\n\nNone recorded." in report


def test_table_cells_escape_newlines(verified):
    rules = verified.envelope.rules
    height = Limit(
        value=20, rule="R+5\nplus attic | roof", citations=rules.buildings[0].max_height_m.citations
    )
    first = rules.buildings[0].model_copy(update={"max_height_m": height})
    rules = rules.model_copy(update={"buildings": (first, rules.buildings[1])})
    envelope = verified.envelope.model_copy(update={"rules": rules})
    report = render(verified.model_copy(update={"envelope": envelope}))
    assert "| A | 20 m | 6 | R+5<br>plus attic \\| roof | [1] |" in report


def test_deterministic(verified):
    assert render(verified) == render(verified)
    assert render(verified).endswith("\n")


def test_evidence_links_crops_under_the_base(verified):
    report = render(verified)
    evidence = report.split("## Evidence", 1)[1].split("## Citations", 1)[0]
    assert (
        "![plu_reglement_graphique p.1, region [10, 20, 110, 90]]"
        "(evidence/plu_reglement_graphique_p1_10-20-110-90.png)" in evidence
    )
    assert "*oap p.34, region [120, 400, 900, 1100] (overview pixels)*" in evidence


def test_no_evidence(verified):
    report = render(verified.model_copy(update={"evidence": ()}))
    assert "## Evidence\n\nNo image evidence saved." in report
