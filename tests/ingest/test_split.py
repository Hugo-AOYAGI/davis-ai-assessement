import pytest

from agent.contracts.inputs.corpus import Section

UMG = "plu_reglement/titre-ii/moulon/umg"
UMG_PAGES = {
    1: 320, 2: 321, 3: 321, 4: 322, 5: 324, 6: 324, 7: 325, 8: 325,
    9: 326, 10: 326, 11: 326, 12: 327, 13: 330, 14: 331, 15: 331, 16: 332,
}  # fmt: skip
LEXIQUE = "plu_reglement/titre-iii/lexique"
TERMS = [
    "Accès", "Acrotère", "Alignement", "Annexes", "Arase",
    "Arbres, arbustes et plantations", "Arbre de haute tige", "Aspirateurs statiques",
    "Axe de la voie", "Bardage", "Bardeau", "Bâtiments d’activités",  # noqa: RUF001
    "Bâtiment ou Construction principale", "Chien-assis", "CINASPIC", "Corniche", "Desserte",
    "Egout du toit", "Emprise au sol", "Espaces végétalisés (application des articles 13)",
    "Equipements collectifs", "Eternit", "Faîtage ou faîte", "Hauteur de construction (art.10)",
    "Imposte", "Limite séparative", "Lucarne", "Modénature", "Oriel",
    "Ouvertures ou éléments constituant des vues", "Ouvertures ou éléments ne créant pas de vues",
    "Parcelle", "Passage", "Pignon", "Rampe", "Reconstruction à l’identique",  # noqa: RUF001
    "Réhabilitation/rénovation", "Surface de plancher", "Unité foncière", "Voie", "Voirie",
    "Voussure",
]  # fmt: skip


def children(sections: dict[str, Section], parent: str) -> list[Section]:
    return [s for s in sections.values() if s.id.rsplit("/", 1)[0] == parent]


def test_umg_has_articles_1_to_16_on_their_pages(umg):
    articles = children(umg, UMG)
    assert [s.article for s in articles] == [str(n) for n in range(1, 17)]
    assert {int(s.article or 0): s.page_start for s in articles} == UMG_PAGES
    assert all(s.zone == "UMG" for s in articles)
    assert umg[f"{UMG}/10"].heading_path == (
        "TITRE II : DISPOSITIONS PAR ZONES",
        "Moulon",
        "Moulon - UMG",
        "ARTICLE 10 - zone UMG -HAUTEUR MAXIMALE DES CONSTRUCTIONS",
    )


@pytest.mark.parametrize("article", ["5", "14"])
def test_repealed_articles_are_sections(umg, article):
    assert "Abrogé par la loi ALUR" in umg[f"{UMG}/{article}"].text


def test_zone_intro_belongs_to_the_zone(umg):
    zone = umg[UMG]
    assert zone.zone == "UMG"
    assert zone.page_start == 320
    assert "La zone UMG correspond au quartier Joliot-Curie" in zone.text
    assert "La zone UMG correspond" not in umg[f"{UMG}/1"].text
    assert umg[f"{UMG}/1"].text.startswith("ARTICLE 1 - zone UMG")


def test_wrapped_article_title_is_joined(umg):
    assert umg[f"{UMG}/2"].heading_path[-1].endswith("SOUMISES A DES CONDITIONS PARTICULIERES")


def test_neighbour_zones_are_separate(umg):
    assert umg["plu_reglement/titre-ii/moulon/um/16"].page_end == 319
    assert umg["plu_reglement/titre-ii/moulon/ume"].page_start == 333


def test_running_header_and_footer_are_excluded(umg, titre_i, titre_iii):
    for sections in (umg, titre_i, titre_iii):
        for section in sections.values():
            assert "GIF-SUR-YVETTE" not in section.text
            assert "Règlement de zone" not in section.text
            assert "Modification n°1" not in section.text


def test_titre_i_articles_with_duplicate_number(titre_i):
    articles = children(titre_i, "plu_reglement/titre-i")
    assert [s.id.rsplit("/", 1)[1] for s in articles] == ["1", "2", "3", "4", "5", "6", "7", "5-2"]
    assert all(s.zone is None for s in articles)
    assert titre_i["plu_reglement/titre-i/5-2"].article == "5"
    assert titre_i["plu_reglement/titre-i/5-2"].page_start == 10
    assert titre_i["plu_reglement/preambule"].page_start == 2


def test_lexique_terms(titre_iii):
    terms = children(titre_iii, LEXIQUE)
    assert [s.heading_path[-1] for s in terms] == TERMS
    assert titre_iii[f"{LEXIQUE}/acces"].page_start == 374
    assert "Rénovation : restructuration" in titre_iii[f"{LEXIQUE}/rehabilitation-renovation"].text
    assert max(s.page_end for s in terms) == 379


def test_titre_iii_parts(titre_iii):
    parts = [s.id for s in children(titre_iii, "plu_reglement/titre-iii")]
    assert LEXIQUE in parts
    assert "plu_reglement/titre-iii/les-espaces-boises-classes" in parts
    assert titre_iii[LEXIQUE].heading_path == ("TITRE III : DISPOSITIONS DIVERSES", "Lexique")
    assert len(parts) == 4


def test_oap_chapter_8_is_one_section(oap):
    chapter = oap["oap/chapitre-8"]
    assert (chapter.page_start, chapter.page_end) == (33, 36)
    assert chapter.heading_path == ("8 Le quartier Joliot Curie",)
    assert chapter.text.splitlines()[0].split() == ["8", "Le", "quartier", "Joliot", "Curie"]
    assert chapter.text.count("Le quartier Joliot Curie") == 1
    assert [s.id for s in oap.values()].count("oap/chapitre-8") == 1
    assert not any(key.startswith("oap/chapitre-8-") for key in oap)
