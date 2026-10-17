from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from pydantic import JsonValue

from agent.adapters.corpus.index import CorpusIndex, load_index
from agent.adapters.corpus.store import save_corpus
from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page, Section
from agent.tools.documents.source import CorpusSource

STOPWORDS = ["de", "des", "du", "la", "le", "les", "et", "en", "au", "pour"]

HEADER = ["GIF-SUR-YVETTE - Plan Local d\u2019Urbanisme", "Règlement de zone"]
FOOTER = "Modification n°1 approuvée le 6 juillet 2021"

T1 = "TITRE I : DISPOSITIONS GENERALES"
T2 = "TITRE II : DISPOSITIONS PAR ZONES"
T3 = "TITRE III : DISPOSITIONS DIVERSES"
UMG = (T2, "Moulon", "Moulon - UMG")

TITRE_I = [T1, "Le présent titre s\u2019applique à toutes les zones du PLU."]
TITRE_I_1 = [
    "ARTICLE 1 - CHAMP D\u2019APPLICATION",
    "Le règlement s\u2019applique à l\u2019ensemble du territoire communal.",
]
TITRE_II = [T2]
MOULON = ["Moulon"]
UMG_INTRO = ["Zone UMG \u2013 Joliot-Curie", "La zone UMG correspond au quartier Joliot-Curie."]
UMG_1 = ["ARTICLE 1 - zone UMG - OCCUPATIONS INTERDITES", "Les entrepôts sont interdits."]
UMG_10_A = [
    "ARTICLE 10 - zone UMG - HAUTEUR MAXIMALE",
    "Dans le secteur UMGa :",
    "la hauteur maximale des constructions est fixée à",
    "20 mètres.",
]
UMG_10_B = ["Dans le secteur UMGa :", "les édicules techniques peuvent dépasser de", "2 m."]
UMG_12 = [
    "ARTICLE 12 - zone UMG - STATIONNEMENT",
    "1 place par tranche de 150 m² pour les résidences étudiantes.",
]
TITRE_III = [T3]
LEXIQUE = ["Lexique", "Les définitions suivantes s\u2019appliquent au règlement."]
HAUTEUR = ["Hauteur :", "La hauteur est mesurée depuis le terrain naturel jusqu\u2019au faîtage."]
EMPRISE = ["Emprise au sol :", "Projection verticale du volume de la construction."]
OAP_A = ["8 Le quartier Joliot Curie", "Les hauteurs restent modérées en bordure du parc."]
OAP_B = ["Le stationnement est mutualisé dans des parkings silos."]

PLU_PAGES = {
    1: TITRE_I + TITRE_I_1,
    2: TITRE_II + MOULON + UMG_INTRO + UMG_1,
    3: UMG_10_A,
    4: UMG_10_B + UMG_12,
    5: TITRE_III + LEXIQUE + HAUTEUR,
    6: EMPRISE,
}

SectionRow = tuple[str, tuple[str, ...], str | None, str | None, int, int, list[str]]

SECTIONS: list[SectionRow] = [
    ("titre-i", (T1,), None, None, 1, 1, TITRE_I),
    ("titre-i/1", (T1, TITRE_I_1[0]), None, "1", 1, 1, TITRE_I_1),
    ("titre-ii", (T2,), None, None, 2, 2, TITRE_II),
    ("titre-ii/moulon", (T2, "Moulon"), None, None, 2, 2, MOULON),
    ("titre-ii/moulon/umg", UMG, "UMG", None, 2, 2, UMG_INTRO),
    ("titre-ii/moulon/umg/1", (*UMG, UMG_1[0]), "UMG", "1", 2, 2, UMG_1),
    ("titre-ii/moulon/umg/10", (*UMG, UMG_10_A[0]), "UMG", "10", 3, 4, UMG_10_A + UMG_10_B),
    ("titre-ii/moulon/umg/12", (*UMG, UMG_12[0]), "UMG", "12", 4, 4, UMG_12),
    ("titre-iii", (T3,), None, None, 5, 5, TITRE_III),
    ("titre-iii/lexique", (T3, "Lexique"), None, None, 5, 5, LEXIQUE),
    ("titre-iii/lexique/hauteur", (T3, "Lexique", "Hauteur :"), None, None, 5, 5, HAUTEUR),
    ("titre-iii/lexique/emprise-au-sol", (T3, "Lexique", EMPRISE[0]), None, None, 6, 6, EMPRISE),
]  # fmt: skip


def page_text(number: int, body: list[str]) -> str:
    return "\n".join([*HEADER, *body, FOOTER, str(number)])


def build_corpus() -> Corpus:
    documents = (
        Document(
            id="plu_reglement",
            kind=DocumentKind.REGULATORY_TEXT,
            title="Règlement",
            path=Path("ressources/reglement.pdf"),
            page_count=6,
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
            page_count=2,
        ),
    )
    pages = (
        *(Page(doc="plu_reglement", number=n, text=page_text(n, b)) for n, b in PLU_PAGES.items()),
        Page(doc="plu_reglement_graphique", number=1, text=""),
        Page(doc="oap", number=1, text=page_text(1, OAP_A)),
        Page(doc="oap", number=2, text=page_text(2, OAP_B)),
    )
    sections = [
        Section(
            id=f"plu_reglement/{key}",
            doc="plu_reglement",
            heading_path=path,
            zone=zone,
            article=article,
            page_start=start,
            page_end=end,
            text="\n".join(lines),
        )
        for key, path, zone, article, start, end, lines in SECTIONS
    ]
    sections.append(
        Section(
            id="oap/chapitre-8",
            doc="oap",
            heading_path=(OAP_A[0],),
            page_start=1,
            page_end=2,
            text="\n".join(OAP_A + OAP_B),
        )
    )
    return Corpus(id="test", documents=documents, pages=pages, sections=tuple(sections))


@pytest.fixture(scope="session")
def corpus_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("corpus")
    save_corpus(build_corpus(), directory)
    return directory


@pytest.fixture(scope="session")
def source(corpus_dir) -> CorpusSource:
    return CorpusSource(directory=corpus_dir, stopwords=STOPWORDS)


@pytest.fixture(scope="session")
def index(source: CorpusSource) -> CorpusIndex:
    return source.index()


@pytest.fixture(scope="session", autouse=True)
def clear_index_cache():
    yield
    load_index.cache_clear()


def call(tool: BaseTool, **args: JsonValue) -> ToolMessage:
    message = tool.invoke({"type": "tool_call", "id": "1", "name": tool.name, "args": args})
    assert isinstance(message, ToolMessage)
    return message


@pytest.fixture
def invoke():
    return call
