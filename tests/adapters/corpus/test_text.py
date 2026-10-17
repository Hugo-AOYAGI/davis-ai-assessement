import pytest

from agent.adapters.corpus.text import fold, slug, tokens


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Faîtage d\u2019un toit", "faitage d'un toit"),
        ("ÉLÉMENTS Accès", "elements acces"),
        ("déjà\u2018vu\u2019", "deja'vu'"),
        ("", ""),
    ],
)
def test_fold(text, expected):
    assert fold(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Titre III", "titre-iii"),
        ("Hauteur de construction (art.10)", "hauteur-de-construction-art-10"),
        ("Faîtage  ou faîte", "faitage-ou-faite"),
        ("Accès :", "acces"),
        ("Voie d\u2019accès", "voie-d-acces"),
        ("  --  ", ""),
    ],
)
def test_slug(text, expected):
    assert slug(text) == expected


def test_tokens_fold_and_drop_single_letters_but_keep_digits():
    assert tokens("L\u2019article 5 : R+2 à Gif") == ["article", "5", "2", "gif"]


def test_tokens_drop_folded_stopwords():
    assert tokens("La hauteur DES constructions", stopwords=("la", "dés")) == [
        "hauteur",
        "constructions",
    ]
