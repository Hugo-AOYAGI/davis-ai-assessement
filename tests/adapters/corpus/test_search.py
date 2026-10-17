from agent.adapters.corpus.search import Bm25

TEXTS = (
    "La hauteur maximale des constructions est de 20 mètres.",
    "Une place de stationnement par logement.",
    "Les clôtures ont une hauteur limitée.",
    "Emprise au sol des constructions.",
    "Les espaces verts représentent 30 % du terrain.",
    "Les accès doivent desservir la voie publique.",
    "Les toitures terrasses sont autorisées.",
)


def test_ranks_best_match_first():
    results = Bm25(TEXTS, stopwords=("la", "des", "de")).search("hauteur maximale", k=5)

    assert [index for index, _ in results] == [0, 2]
    assert results[0][1] > results[1][1] > 0


def test_accents_and_case_are_folded():
    results = Bm25(TEXTS).search("CLOTURES", k=5)

    assert [index for index, _ in results] == [2]


def test_k_limits_results():
    assert len(Bm25(TEXTS).search("hauteur constructions", k=1)) == 1


def test_empty_query_and_stopword_only_query():
    bm25 = Bm25(TEXTS, stopwords=("la",))

    assert bm25.search("", k=5) == []
    assert bm25.search("la", k=5) == []


def test_empty_corpus():
    assert Bm25([]).search("hauteur", k=5) == []
    assert Bm25(["", "!"]).search("hauteur", k=5) == []


def test_no_match_returns_nothing():
    assert Bm25(TEXTS).search("piscine", k=5) == []
