import pytest

from agent.tools.regulation.navigate import (
    list_sections_tool,
    read_article_tool,
    read_pages_tool,
    read_section_tool,
    read_zone_tool,
)

GENERAL = ["plu_reglement/titre-i", "plu_reglement/titre-iii/lexique"]
UMG = "plu_reglement/titre-ii/moulon/umg"


def zone_tool(source, mode, max_chars=10_000):
    return read_zone_tool(corpus=source, mode=mode, general_sections=GENERAL, max_chars=max_chars)


def test_list_sections_documents(source, invoke):
    text = invoke(list_sections_tool(corpus=source)).content
    assert "# plu_reglement (regulatory_text): Règlement, 6 pages" in text
    assert (
        "- plu_reglement/titre-ii | TITRE II : DISPOSITIONS PAR ZONES | p.2 | 1 sub-sections"
        in text
    )
    assert "# plu_reglement_graphique (zoning_map): Plan de zonage, 1 pages\n(no sections)" in text
    assert "- oap/chapitre-8 | 8 Le quartier Joliot Curie | p.1-2" in text
    assert "titre-ii/moulon" not in text


def test_list_sections_one_document(source, invoke):
    text = invoke(list_sections_tool(corpus=source), doc="oap").content
    assert text.startswith("# oap (oap)")
    assert "plu_reglement" not in text


def test_list_sections_children(source, invoke):
    tool = list_sections_tool(corpus=source)
    text = invoke(tool, parent=UMG).content
    assert text.startswith(f"Sub-sections of {UMG} (Moulon - UMG):")
    assert f"- {UMG}/10 | ARTICLE 10 - zone UMG - HAUTEUR MAXIMALE | p.3-4" in text
    assert "has no sub-sections" in invoke(tool, parent=f"{UMG}/10").content


def test_list_sections_unknown_ids_are_tool_errors(source, invoke):
    tool = list_sections_tool(corpus=source)
    reply = invoke(tool, doc="plu")
    assert reply.status == "error"
    assert "Known documents" in reply.content
    assert "Did you mean" in invoke(tool, parent=f"{UMG}/1O").content


def test_read_zone_navigation(source, invoke):
    text = invoke(zone_tool(source, "navigation"), zone="umg", sector="Moulon").content
    assert text.startswith(f"## TITRE II : DISPOSITIONS PAR ZONES > Moulon > Moulon - UMG [{UMG}")
    assert "--- plu_reglement p.2 ---\nZone UMG \u2013 Joliot-Curie" in text
    assert f"- {UMG}/12 | ARTICLE 12 - zone UMG - STATIONNEMENT | p.4" in text
    assert "- plu_reglement/titre-iii/lexique | Lexique | p.5 | 2 sub-sections" in text
    assert "20 mètres" not in text


def test_read_zone_full_sections(source, invoke):
    text = invoke(zone_tool(source, "full_sections"), zone="UMG").content
    assert "--- plu_reglement p.4 ---\nDans le secteur UMGa :" in text
    assert "20 mètres." in text
    assert text.index("ARTICLE 12") < text.index("TITRE I :") < text.index("Emprise au sol :")


def test_read_zone_truncates(source, invoke):
    text = invoke(zone_tool(source, "full_sections", max_chars=300), zone="UMG").content
    assert text.endswith("Read the rest with read_article or read_section.]")
    assert "[truncated: reply limited to 300 characters." in text


def test_read_zone_unknown_zone(source, invoke):
    reply = invoke(zone_tool(source, "navigation"), zone="UX")
    assert reply.status == "error"
    assert "Known zones: UMG" in reply.content


def test_read_zone_rejects_an_unknown_mode(source):
    with pytest.raises(ValueError, match="RetrievalMode"):
        zone_tool(source, "everything")


def test_read_article(source, invoke):
    tool = read_article_tool(corpus=source, max_chars=10_000)
    text = invoke(tool, zone="UMG", article="10", sector="Moulon").content
    assert text.count("--- plu_reglement p.") == 2
    assert "--- plu_reglement p.3 ---" in text
    assert "--- plu_reglement p.4 ---" in text
    reply = invoke(tool, zone="UMG", article="99")
    assert reply.status == "error"
    assert "Available articles: 1, 10, 12" in reply.content


def test_read_section_navigation(source, invoke):
    tool = read_section_tool(corpus=source, mode="navigation", max_chars=10_000)
    text = invoke(tool, section_id="plu_reglement/titre-iii/lexique").content
    assert "--- plu_reglement p.5 ---\nLexique" in text
    assert "Sub-sections (read with read_section):" in text
    assert "- plu_reglement/titre-iii/lexique/emprise-au-sol | Emprise au sol : | p.6" in text
    assert "Projection verticale" not in text


def test_read_section_full_sections(source, invoke):
    tool = read_section_tool(corpus=source, mode="full_sections", max_chars=10_000)
    text = invoke(tool, section_id="plu_reglement/titre-iii/lexique").content
    assert "--- plu_reglement p.6 ---\nEmprise au sol :\nProjection verticale" in text
    assert "Sub-sections" not in text


def test_read_pages(source, invoke):
    tool = read_pages_tool(corpus=source, max_pages=2, max_chars=10_000)
    text = invoke(tool, doc="plu_reglement", start=3, end=4).content
    assert text.startswith("--- plu_reglement p.3 ---\nGIF-SUR-YVETTE")
    assert "--- plu_reglement p.4 ---" in text
    raster = invoke(tool, doc="plu_reglement_graphique", start=1, end=1).content
    assert raster == "--- plu_reglement_graphique p.1 ---\n(no text layer: raster page)"


def test_read_pages_errors(source, invoke):
    tool = read_pages_tool(corpus=source, max_pages=2, max_chars=10_000)
    too_many = invoke(tool, doc="plu_reglement", start=1, end=5)
    assert too_many.status == "error"
    assert "At most 2 pages per call" in too_many.content
    assert "Read 1-2 first" in too_many.content
    assert "valid pages are 1-6" in invoke(tool, doc="plu_reglement", start=6, end=7).content


def test_descriptions_follow_the_mode(source):
    navigation = zone_tool(source, "navigation").description
    full = zone_tool(source, "full_sections").description
    assert navigation.startswith("Open the chapter of a zone")
    assert full.startswith("Read the whole chapter of a zone")
    assert "--- <doc> p.<page> ---" in navigation
    tool = read_pages_tool(corpus=source, max_pages=4, max_chars=100)
    assert "at most 4 pages per call" in tool.description
    assert tool.args["start"]["description"].startswith("First page")
