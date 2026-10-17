import pytest

from agent.tools.regulation.lookup import get_definition_tool, search_tool


def test_get_definition(source, invoke):
    tool = get_definition_tool(corpus=source, max_results=3, max_chars=10_000)
    text = invoke(tool, term="HAUTEUR").content
    assert text.startswith(
        "## TITRE III : DISPOSITIONS DIVERSES > Lexique > Hauteur : "
        "[plu_reglement/titre-iii/lexique/hauteur, p.5]\n--- plu_reglement p.5 ---\nHauteur :"
    )


def test_get_definition_limits_results(source, invoke):
    tool = get_definition_tool(corpus=source, max_results=1, max_chars=10_000)
    text = invoke(tool, term="au").content
    assert text.count("## ") == 1


def test_get_definition_suggests_search(source, invoke):
    tool = get_definition_tool(corpus=source, max_results=3, max_chars=10_000)
    reply = invoke(tool, term="prospect")
    assert reply.status == "success"
    assert "No lexique entry matches 'prospect'" in reply.content
    assert "search" in reply.content


def test_search_hit_with_page_of_the_snippet(source, invoke):
    tool = search_tool(corpus=source, k=3, snippet_chars=60)
    text = invoke(tool, query="édicules techniques").content
    lines = text.split("\n")
    assert lines[1] == (
        "- plu_reglement/titre-ii/moulon/umg/10 | TITRE II : DISPOSITIONS PAR ZONES > Moulon > "
        "Moulon - UMG > ARTICLE 10 - zone UMG - HAUTEUR MAXIMALE | p.3-4"
    )
    assert lines[2].startswith("  (p.4) ")
    assert "édicules techniques" in lines[2]


def test_search_snippet_prefers_the_passage_with_most_words(source, invoke):
    tool = search_tool(corpus=source, k=1, snippet_chars=40)
    text = invoke(tool, query="stationnement résidences étudiantes").content
    assert "(p.4) …" in text
    assert "résidences étudiantes" in text


def test_search_in_one_document(source, invoke):
    tool = search_tool(corpus=source, k=5, snippet_chars=80)
    text = invoke(tool, query="stationnement", doc="oap").content
    assert "- oap/chapitre-8 |" in text
    assert "(p.2) " in text
    assert "plu_reglement" not in text


def test_search_without_hits(source, invoke):
    tool = search_tool(corpus=source, k=5, snippet_chars=80)
    reply = invoke(tool, query="piscine")
    assert "No section matches 'piscine'" in reply.content
    assert "Try other words" in reply.content


def test_search_unknown_document(source, invoke):
    reply = invoke(search_tool(corpus=source, k=5, snippet_chars=80), query="x", doc="nope")
    assert reply.status == "error"


def test_limits_are_checked(source):
    with pytest.raises(ValueError, match="k=0"):
        search_tool(corpus=source, k=0, snippet_chars=80)
