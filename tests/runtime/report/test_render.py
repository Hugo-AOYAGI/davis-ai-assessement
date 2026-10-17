from agent.contracts.evidence import Limit
from agent.runtime.report.render import render_report

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
    "## Citations",
)


def line_with(report, *fragments):
    return next(line for line in report.splitlines() if all(f in line for f in fragments))


def test_headings_in_order(verified):
    lines = render_report(verified, max_quote_chars=200).splitlines()
    positions = [lines.index(heading) for heading in HEADINGS]
    assert positions == sorted(positions)


def test_header_summary_and_site(verified):
    report = render_report(verified, max_quote_chars=200)
    assert "**Program:** RSE + RJA, two buildings" in report
    assert "The program is **buildable** in zone UMG." in report
    assert "| 91272000AB0123 | 1200 |" in report
    assert "- Site area: 1200 m²" in report
    assert "- Road limit is the southern edge." in report
    assert "- (cadastre): 91272000AB0123" in report
    assert "- (ban): 4 Rue Joliot Curie" in report


def test_regime_and_admissibility(verified):
    report = render_report(verified, max_quote_chars=200)
    assert "Zone: **UMG** [1, 3]" in report
    assert "| Espace boisé classé | no | none drawn |  |" in report
    assert "| Linéaire commercial | yes | along the street | [3] |" in report
    assert "OAP applicable: **yes**" in report
    assert "- **landscape**: Keep a planted strip. [5]" in report
    row = line_with(report, "| B |")
    assert "| conditional | Social mix required | [3] |" in row
    assert "| permitted | none | [3] |" in line_with(report, "| A |")


def test_envelope_parameters(verified):
    report = render_report(verified, max_quote_chars=200)
    assert "| Setback from road limits | 5 m | see article | [2] |" in report
    assert "| Maximum height | 20 m | see article | [1] |" in report
    assert "| Maximum storeys | 6 | see article | [1] |" in report
    assert "| Maximum footprint ratio | not set | see article |  |" in report
    assert "| Minimum green ratio | 20% | see article | [1] |" in report


def test_computed_envelope(verified):
    report = render_report(verified, max_quote_chars=200)
    assert "| Buildable footprint after setbacks | 651 m² |" in report
    assert "| Minimum green area | 240 m² |" in report
    assert "| Maximum volume | 13020 m³ |" in report
    assert "- Setbacks applied as straight offsets." in report


def test_missing_computed_values_render_as_dash(verified):
    envelope = verified.envelope.model_copy(
        update={
            "footprint": None,
            "footprint_area_m2": 0,
            "max_footprint_area_m2": 0,
            "min_green_area_m2": None,
            "max_height_m": None,
            "max_volume_m3": None,
        }
    )
    report = render_report(verified.model_copy(update={"envelope": envelope}), max_quote_chars=200)
    assert (
        "| Buildable footprint after setbacks | 0 m² (nothing remains after setbacks) |" in report
    )
    assert "| Minimum green area | — |" in report
    assert "| Maximum height | — |" in report
    assert "| Maximum volume | — |" in report


def test_parking_conditions_and_ambiguities(verified):
    report = render_report(verified, max_quote_chars=200)
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
    report = render_report(verified, max_quote_chars=200)
    citations = report.split("## Citations", 1)[1]
    assert "| 1 | plu_reglement | 327 | UMG 10 | La hauteur maximale est fixée à 20 mètres |" in (
        citations
    )
    assert "| verified | 0.99 |" in line_with(citations, "| 1 |")
    assert "Recul minimal de 5 mètres \\| par rapport" in citations
    assert "| verified (found on p.326) | 0.91 |" in line_with(citations, "| 2 |")
    assert "| NOT VERIFIED | 0.43 |" in line_with(citations, "| 4 |")


def test_long_quote_truncated(verified):
    report = render_report(verified, max_quote_chars=60)
    row = line_with(report.split("## Citations", 1)[1], "| 5 |")
    quote = row.split(" | ")[4]
    assert quote.endswith("…")
    assert len(quote) == 60


def test_uncited_and_unchecked_citations(verified):
    regime = verified.study.regime.model_copy(update={"citations": (verified.site.citations[0],)})
    study = verified.study.model_copy(update={"regime": regime, "ambiguities": ()})
    report = render_report(
        verified.model_copy(update={"study": study, "citation_checks": ()}), max_quote_chars=200
    )
    assert "Zone: **UMG** (cadastre)" in report
    assert "| Maximum height | 20 m | see article | (plu_reglement, p.327) |" in report
    assert "No regulatory citation was checked." in report
    assert "## Ambiguities\n\nNone recorded." in report


def test_table_cells_escape_newlines(verified):
    parameters = verified.study.envelope.model_copy(
        update={"max_storeys": Limit(value=None, rule="R+5\nplus attic | roof")}
    )
    study = verified.study.model_copy(update={"envelope": parameters})
    report = render_report(verified.model_copy(update={"study": study}), max_quote_chars=200)
    assert "| Maximum storeys | not set | R+5<br>plus attic \\| roof |  |" in report


def test_deterministic(verified):
    assert render_report(verified, max_quote_chars=200) == render_report(
        verified, max_quote_chars=200
    )
    assert render_report(verified, max_quote_chars=200).endswith("\n")
