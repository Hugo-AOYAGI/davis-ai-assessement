import pytest

from agent.tools.documents.navigate import (
    list_documents_tool,
    list_sections_tool,
    read_pages_tool,
    read_section_tool,
)

UMG = "plu_reglement/titre-ii/moulon/umg"
DOCUMENTS = [
    {"id": "plu_reglement", "path": "a.pdf", "legal_force": "conformity"},
    {"id": "plu_reglement_graphique", "path": "b.pdf", "legal_force": "conformity"},
    {"id": "oap", "path": "c.pdf", "legal_force": "compatibility"},
]


def test_list_documents(source, invoke):
    text = invoke(list_documents_tool(corpus=source, documents=DOCUMENTS)).content
    lines = text.split("\n")
    assert lines[1:4] == [
        "- plu_reglement | regulatory_text | Règlement | 6 pages | legal force: conformity",
        "- plu_reglement_graphique | zoning_map | Plan de zonage | 1 pages | legal force: "
        "conformity | image only",
        "- oap | oap | OAP | 2 pages | legal force: compatibility",
    ]
    assert lines[5] == "Legal force:"
    assert lines[6].startswith("- conformity: the project must follow the document exactly")
    assert lines[7].startswith("- compatibility: the project must not contradict")


def test_list_documents_without_force_and_unused_forces(source, invoke):
    tool = list_documents_tool(corpus=source, documents=DOCUMENTS[:1])
    text = invoke(tool).content
    assert "- oap | oap | OAP | 2 pages | legal force: not stated" in text
    assert "compatibility" not in text


def test_list_documents_rejects_an_unknown_force(source):
    with pytest.raises(ValueError, match="binding"):
        list_documents_tool(corpus=source, documents=[{"id": "x", "legal_force": "binding"}])


def test_list_sections_document(source, invoke):
    tool = list_sections_tool(corpus=source)
    text = invoke(tool, doc="plu_reglement").content
    assert text.startswith("# plu_reglement (regulatory_text): Règlement, 6 pages")
    assert (
        "- plu_reglement/titre-ii | TITRE II : DISPOSITIONS PAR ZONES | p.2 | 1 sub-sections"
        in text
    )
    assert "titre-ii/moulon" not in text
    plan = invoke(tool, doc="plu_reglement_graphique").content
    assert plan == "# plu_reglement_graphique (zoning_map): Plan de zonage, 1 pages\n(no sections)"


def test_list_sections_children(source, invoke):
    tool = list_sections_tool(corpus=source)
    text = invoke(tool, doc="plu_reglement", parent=UMG).content
    assert text.startswith(f"Sub-sections of {UMG} (Moulon - UMG):")
    assert f"- {UMG}/10 | ARTICLE 10 - zone UMG - HAUTEUR MAXIMALE | p.3-4" in text
    assert "has no sub-sections" in invoke(tool, doc="plu_reglement", parent=f"{UMG}/10").content


def test_list_sections_errors(source, invoke):
    tool = list_sections_tool(corpus=source)
    reply = invoke(tool, doc="plu")
    assert reply.status == "error"
    assert "Known documents" in reply.content
    assert "Did you mean" in invoke(tool, doc="plu_reglement", parent=f"{UMG}/1O").content
    other = invoke(tool, doc="oap", parent=UMG)
    assert other.status == "error"
    assert "belongs to document 'plu_reglement', not 'oap'" in other.content


def test_read_section_navigation(source, invoke):
    tool = read_section_tool(corpus=source, mode="navigation", max_chars=10_000)
    text = invoke(tool, section_id="plu_reglement/titre-iii/lexique").content
    assert "--- plu_reglement p.5 ---\nLexique" in text
    assert "Sub-sections (read with read_section):" in text
    assert "- plu_reglement/titre-iii/lexique/emprise-au-sol | Emprise au sol : | p.6" in text
    assert "Projection verticale" not in text


def test_read_section_full_sections(source, invoke):
    tool = read_section_tool(corpus=source, mode="full_sections", max_chars=10_000)
    text = invoke(tool, section_id=UMG).content
    assert "--- plu_reglement p.4 ---\nDans le secteur UMGa :" in text
    assert "20 mètres." in text
    assert text.index("ARTICLE 1 ") < text.index("ARTICLE 10") < text.index("ARTICLE 12")
    assert "Sub-sections" not in text


def test_read_section_truncates_and_reports_unknown_ids(source, invoke):
    tool = read_section_tool(corpus=source, mode="full_sections", max_chars=300)
    text = invoke(tool, section_id=UMG).content
    assert text.endswith("Read its sub-sections one by one.]")
    reply = invoke(tool, section_id=f"{UMG}/99")
    assert reply.status == "error"
    assert "Unknown section" in reply.content


def test_read_section_rejects_an_unknown_mode(source):
    with pytest.raises(ValueError, match="everything"):
        read_section_tool(corpus=source, mode="everything", max_chars=100)


def test_read_pages(source, invoke):
    tool = read_pages_tool(corpus=source, max_pages=2, max_chars=10_000)
    text = invoke(tool, doc="plu_reglement", start=3, end=4).content
    assert text.startswith("--- plu_reglement p.3 ---\nGIF-SUR-YVETTE")
    assert "--- plu_reglement p.4 ---" in text
    raster = invoke(tool, doc="plu_reglement_graphique", start=1, end=1).content
    assert raster == (
        "--- plu_reglement_graphique p.1 ---\n(no text layer: look at the page with view_image)"
    )


def test_read_pages_errors(source, invoke):
    tool = read_pages_tool(corpus=source, max_pages=2, max_chars=10_000)
    too_many = invoke(tool, doc="plu_reglement", start=1, end=5)
    assert too_many.status == "error"
    assert "At most 2 pages per call" in too_many.content
    assert "Read 1-2 first" in too_many.content
    assert "valid pages are 1-6" in invoke(tool, doc="plu_reglement", start=6, end=7).content


def test_descriptions(source):
    navigation = read_section_tool(corpus=source, mode="navigation", max_chars=10).description
    full = read_section_tool(corpus=source, mode="full_sections", max_chars=10).description
    assert "outline of its direct sub-sections" in navigation
    assert "with all its sub-sections" in full
    assert "--- <doc> p.<page> ---" in navigation
    tool = read_pages_tool(corpus=source, max_pages=4, max_chars=100)
    assert "at most 4 pages per call" in tool.description
    assert tool.args["start"]["description"].startswith("First page")
    listing = list_documents_tool(corpus=source, documents=DOCUMENTS)
    assert listing.name == "list_documents"
    assert "legal force" in listing.description
