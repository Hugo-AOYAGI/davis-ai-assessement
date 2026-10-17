import re
import unicodedata

_APOSTROPHES = (
    "\N{RIGHT SINGLE QUOTATION MARK}\N{LEFT SINGLE QUOTATION MARK}"
    "\N{SINGLE HIGH-REVERSED-9 QUOTATION MARK}\N{ACUTE ACCENT}\N{GRAVE ACCENT}"
    "\N{MODIFIER LETTER APOSTROPHE}\N{PRIME}"
)
_OPENING_QUOTES = (
    "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{LEFT DOUBLE QUOTATION MARK}"
    "\N{DOUBLE LOW-9 QUOTATION MARK}"
)
_CLOSING_QUOTES = "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}"
_DASHES = (
    "\N{HYPHEN}\N{NON-BREAKING HYPHEN}\N{FIGURE DASH}\N{EN DASH}\N{EM DASH}\N{MINUS SIGN}"
    "\N{SOFT HYPHEN}"
)
_INVISIBLE = (
    "\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NON-JOINER}\N{ZERO WIDTH JOINER}\N{WORD JOINER}"
    "\N{ZERO WIDTH NO-BREAK SPACE}"
)
_CHARACTERS = str.maketrans(
    {
        **dict.fromkeys(_APOSTROPHES, "'"),
        **dict.fromkeys(_OPENING_QUOTES + _CLOSING_QUOTES, '"'),
        **dict.fromkeys(_DASHES, "-"),
        **dict.fromkeys(_INVISIBLE),
    }
)
_OPENING_QUOTE = re.compile(f"([{_OPENING_QUOTES}])\\s+")
_CLOSING_QUOTE = re.compile(f"\\s+([{_CLOSING_QUOTES}])")
_HYPHENATION = re.compile(r"(?<=\w)-\s*(?=\w)")
_SPACE_BEFORE = re.compile(r"\s+(?=[,.;:!?)\]])")
_SPACE_AFTER = re.compile(r"(?<=[(\[])\s+")
_WHITESPACE = re.compile(r"\s+")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")


def normalise(text: str) -> str:
    r"""Reduce a text to a canonical form so that a quote can be found verbatim in a page.

    Applied identically to quotes and page text. Typographic quotes, apostrophes and dashes are
    unified, NFKC expands ligatures and compatibility characters, French typographic spaces (inside
    guillemets, before ``: ; ? !``) are dropped, case is folded and whitespace collapsed. Accents
    are kept and the French decimal comma becomes a point (``1,5`` reads ``1.5``). Every hyphen
    between two word characters is removed, whether or not a line break follows it, so that
    ``construc-\ntion`` matches ``construction`` and ``ci-\naprès`` (a compound broken at a line
    end) still matches ``ci-après``.

    Args:
        text: Raw quote or page text.

    Returns:
        The normalised text, on a single line.
    """
    text = _OPENING_QUOTE.sub(r"\1", text)
    text = _CLOSING_QUOTE.sub(r"\1", text)
    text = unicodedata.normalize("NFKC", text.translate(_CHARACTERS))
    text = _HYPHENATION.sub("", text)
    text = _SPACE_BEFORE.sub("", text)
    text = _SPACE_AFTER.sub("", text)
    text = _DECIMAL_COMMA.sub(".", text)
    return _WHITESPACE.sub(" ", text).casefold().strip()
