import pytest

from agent.runtime.citations.normalise import normalise


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("con\N{LATIN SMALL LIGATURE FI}ance", "confiance"),
        ("construc\N{SOFT HYPHEN}tion", "construction"),
        ("construc\N{SOFT HYPHEN}\ntion", "construction"),
        ("construc-\ntion", "construction"),
        ("construc- tion", "construction"),
        ("ci-\naprès", "ciaprès"),
        ("ci-après", "ciaprès"),
        ("zone UM \N{EN DASH} OBLIGATIONS", "zone um - obligations"),
        ("a \N{EM DASH} b \N{MINUS SIGN} c", "a - b - c"),
        ("d\N{RIGHT SINGLE QUOTATION MARK}habitation", "d'habitation"),
        ("d\N{ACUTE ACCENT}habitation", "d'habitation"),
        ("\N{LEFT DOUBLE QUOTATION MARK}texte\N{RIGHT DOUBLE QUOTATION MARK}", '"texte"'),
        (
            "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{NO-BREAK SPACE}texte"
            "\N{NARROW NO-BREAK SPACE}\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}",
            '"texte"',
        ),
        ("hauteur : 20 m", "hauteur: 20 m"),
        ("hauteur\N{NARROW NO-BREAK SPACE}; ok ?", "hauteur; ok?"),
        ("  Mètres\t\n\N{NO-BREAK SPACE} ÉTÉ  ", "mètres été"),
        ("20 m\N{SUPERSCRIPT TWO}", "20 m2"),
        ("1,80 mètre, 2 et 3", "1.80 mètre, 2 et 3"),
    ],
)
def test_normalise(raw, expected):
    assert normalise(raw) == expected


def test_spaced_hyphen_is_kept():
    assert normalise("Moulon - UMG") == "moulon - umg"


def test_accents_are_kept():
    assert normalise("Règlement") == "règlement"
