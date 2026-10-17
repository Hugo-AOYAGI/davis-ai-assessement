from pathlib import Path

import pytest

from agent.adapters.corpus.index import CorpusIndex
from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page, Section

STOPWORDS = ("de", "des", "du", "la", "le", "les", "et", "en", "au")

T1 = "TITRE I : DISPOSITIONS GENERALES"
T2 = "TITRE II : DISPOSITIONS PAR ZONES"
T3 = "TITRE III : ANNEXES"
LEX = "Lexique"

Row = tuple[str, tuple[str, ...], str | None, str | None, int, str]

REGLEMENT: tuple[Row, ...] = (
    ("preamble", ("Préambule",), None, None, 1, "Le présent règlement s'applique à la commune."),
    ("titre-i", (T1,), None, None, 2, "Dispositions applicables à toutes les zones."),
    ("titre-i/5", (T1, "ARTICLE 5 - ADAPTATIONS MINEURES"), None, "5", 2, "Adaptations."),
    (
        "titre-i/5-2",
        (T1, "ARTICLE 5 - RECONSTRUCTION"),
        None,
        "5",
        3,
        "Reconstruction à l'identique.",
    ),
    ("titre-ii", (T2,), None, None, 4, "Chapitres par zones."),
    ("titre-ii/vallee", (T2, "Vallée"), None, None, 4, "Secteur de la vallée."),
    ("titre-ii/vallee/ua", (T2, "Vallée", "Vallée - UA"), "UA", None, 4, "Zone centrale ancienne."),
    (
        "titre-ii/vallee/ua/1",
        (T2, "Vallée", "Vallée - UA", "ARTICLE 1 - zone UA - OCCUPATIONS INTERDITES"),
        "UA",
        "1",
        5,
        "Les entrepôts sont interdits.",
    ),
    ("titre-ii/chevry", (T2, "Chevry"), None, None, 6, "Secteur de Chevry."),
    ("titre-ii/chevry/ua", (T2, "Chevry", "Chevry - UA"), "UA", None, 6, "Zone de Chevry."),
    (
        "titre-ii/chevry/ua/1",
        (T2, "Chevry", "Chevry - UA", "ARTICLE 1 - zone UA - OCCUPATIONS INTERDITES"),
        "UA",
        "1",
        6,
        "Les industries sont interdites.",
    ),
    (
        "titre-ii/chevry/ua/2",
        (T2, "Chevry", "Chevry - UA", "ARTICLE 2 - zone UA - OCCUPATIONS SOUMISES"),
        "UA",
        "2",
        7,
        "Les commerces sont autorisés sous conditions.",
    ),
    ("titre-ii/moulon", (T2, "Moulon"), None, None, 8, "Secteur du Moulon."),
    ("titre-ii/moulon/umg", (T2, "Moulon", "Moulon - UMG"), "UMG", None, 8, "Zone mixte."),
    (
        "titre-ii/moulon/umg/1",
        (T2, "Moulon", "Moulon - UMG", "ARTICLE 1 - zone UMG - OCCUPATIONS INTERDITES"),
        "UMG",
        "1",
        8,
        "Les dépôts sont interdits.",
    ),
    (
        "titre-ii/moulon/umg/10",
        (
            T2,
            "Moulon",
            "Moulon - UMG",
            "ARTICLE 10 - zone UMG - HAUTEUR MAXIMALE DES CONSTRUCTIONS",
        ),
        "UMG",
        "10",
        9,
        "La hauteur maximale des constructions est fixée à 20 mètres au faîtage.",
    ),
    (
        "titre-ii/moulon/umg/12",
        (T2, "Moulon", "Moulon - UMG", "ARTICLE 12 - zone UMG - STATIONNEMENT"),
        "UMG",
        "12",
        10,
        "Une place de stationnement par logement.",
    ),
    ("titre-iii", (T3,), None, None, 11, "Annexes."),
    ("titre-iii/lexique", (T3, LEX), None, None, 11, "Définitions."),
    ("titre-iii/lexique/acces", (T3, LEX, "Accès :"), None, None, 11, "Passage vers la voie."),
    (
        "titre-iii/lexique/acces-privatif",
        (T3, LEX, "Accès privatif"),
        None,
        None,
        11,
        "Accès réservé aux occupants.",
    ),
    (
        "titre-iii/lexique/voie-d-acces",
        (T3, LEX, "Voie d\u2019accès"),
        None,
        None,
        12,
        "Voie desservant un terrain.",
    ),
    (
        "titre-iii/lexique/hauteur-de-construction-art-10",
        (T3, LEX, "Hauteur de construction (art.10)"),
        None,
        None,
        12,
        "Mesurée depuis le terrain naturel.",
    ),
    (
        "titre-iii/lexique/faitage-ou-faite",
        (T3, LEX, "Faîtage  ou faîte"),
        None,
        None,
        12,
        "Ligne de jonction supérieure des pans de toiture.",
    ),
)


def _section(doc: str, row: Row) -> Section:
    key, path, zone, article, page, body = row
    return Section(
        id=f"{doc}/{key}",
        doc=doc,
        heading_path=path,
        zone=zone,
        article=article,
        page_start=page,
        page_end=page,
        text=f"{path[-1]}\n{body}",
    )


def build_corpus() -> Corpus:
    documents = (
        Document(
            id="plu_reglement",
            kind=DocumentKind.REGULATORY_TEXT,
            title="Règlement",
            path=Path("ressources/reglement.pdf"),
            page_count=12,
        ),
        Document(
            id="plu_reglement_graphique",
            kind=DocumentKind.ZONING_MAP,
            title="Plan de zonage",
            path=Path("ressources/graphique.pdf"),
            page_count=1,
        ),
        Document(
            id="oap",
            kind=DocumentKind.OAP,
            title="OAP",
            path=Path("ressources/oap.pdf"),
            page_count=4,
        ),
    )
    pages = (
        *(Page(doc="plu_reglement", number=n, text=f"règlement page {n}") for n in range(1, 13)),
        Page(doc="plu_reglement_graphique", number=1, text=""),
        *(Page(doc="oap", number=n, text=f"oap page {n}") for n in range(1, 5)),
    )
    oap = Section(
        id="oap/chapitre-8",
        doc="oap",
        heading_path=("8    Le quartier Joliot Curie",),
        page_start=3,
        page_end=4,
        text="8    Le quartier Joliot Curie\nUne hauteur modérée en bordure du parc.",
    )
    sections = (*(_section("plu_reglement", row) for row in REGLEMENT), oap)
    return Corpus(id="test", documents=documents, pages=pages, sections=sections)


@pytest.fixture
def corpus() -> Corpus:
    return build_corpus()


@pytest.fixture
def index(corpus: Corpus) -> CorpusIndex:
    return CorpusIndex(corpus, stopwords=STOPWORDS)
