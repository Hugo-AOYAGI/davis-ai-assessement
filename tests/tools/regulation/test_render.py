from agent.contracts.inputs.corpus import Page, Section
from agent.tools.regulation.render import (
    outline,
    paginate,
    render_pages,
    render_section,
    truncate,
)

ARTICLE_10 = "plu_reglement/titre-ii/moulon/umg/10"


def test_article_spanning_two_pages(index):
    chunks = paginate(index.section(ARTICLE_10), index)
    assert chunks == [
        (
            3,
            "ARTICLE 10 - zone UMG - HAUTEUR MAXIMALE\nDans le secteur UMGa :\n"
            "la hauteur maximale des constructions est fixée à\n20 mètres.",
        ),
        (4, "Dans le secteur UMGa :\nles édicules techniques peuvent dépasser de\n2 m."),
    ]


def test_repeated_line_moves_to_the_next_page(index):
    (first, _), (second, text) = paginate(index.section(ARTICLE_10), index)
    assert (first, second) == (3, 4)
    assert text.startswith("Dans le secteur UMGa :")


def test_short_lines_stay_with_the_previous_line(index):
    chunks = dict(paginate(index.section(ARTICLE_10), index))
    assert chunks[3].endswith("20 mètres.")
    assert chunks[4].endswith("2 m.")


def test_article_starting_mid_page(index):
    assert paginate(index.section("plu_reglement/titre-ii/moulon/umg/12"), index)[0][0] == 4


def test_lines_found_nowhere_stay_on_the_current_page(index):
    section = Section(
        id="plu_reglement/x",
        doc="plu_reglement",
        heading_path=("X",),
        page_start=3,
        page_end=9,
        text="Une ligne absente de toutes les pages\nles édicules techniques peuvent dépasser de",
    )
    assert [page for page, _ in paginate(section, index)] == [3, 4]


def test_empty_section_has_no_chunks(index):
    section = index.section(ARTICLE_10).model_copy(update={"text": " \n"})
    assert paginate(section, index) == []


def test_render_section_heading_and_markers(index):
    text = render_section(index.section(ARTICLE_10), index)
    lines = text.split("\n")
    assert lines[0] == (
        "## TITRE II : DISPOSITIONS PAR ZONES > Moulon > Moulon - UMG > "
        f"ARTICLE 10 - zone UMG - HAUTEUR MAXIMALE [{ARTICLE_10}, p.3-4]"
    )
    assert lines[1] == "--- plu_reglement p.3 ---"
    assert lines[lines.index("--- plu_reglement p.4 ---") - 1] == "20 mètres."


def test_render_pages_marks_raster_pages(index):
    pages = [index.page("plu_reglement", 6), Page(doc="plan", number=1, text="")]
    text = render_pages(pages)
    assert text.startswith("--- plu_reglement p.6 ---\nGIF-SUR-YVETTE")
    assert text.endswith("--- plan p.1 ---\n(no text layer: raster page)")


def test_outline_counts_sub_sections(index):
    lines = outline(
        [index.section("plu_reglement/titre-i"), index.section("plu_reglement/titre-i/1")], index
    ).split("\n")
    assert lines == [
        "- plu_reglement/titre-i | TITRE I : DISPOSITIONS GENERALES | p.1 | 1 sub-sections",
        "- plu_reglement/titre-i/1 | ARTICLE 1 - CHAMP D\u2019APPLICATION | p.1",
    ]


def test_truncate_cuts_at_a_line_break():
    assert truncate("short", 10, "hint") == "short"
    text = truncate("first line\nsecond line\nthird", 15, "Read less.")
    assert text == "first line\n[truncated: reply limited to 15 characters. Read less.]"


def test_truncate_without_line_break():
    assert truncate("abcdefghij", 4, "h").startswith("abcd\n[truncated")
