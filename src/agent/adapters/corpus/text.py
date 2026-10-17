import re
import unicodedata
from collections.abc import Iterable

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'"})
_WORD = re.compile(r"\w+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def fold(text: str) -> str:
    """Fold text for comparison: accents removed, case folded, apostrophes unified.

    Args:
        text: Any text.

    Returns:
        The folded text, e.g. ``"Faîtage Élevé"`` → ``"faitage eleve"``.
    """
    decomposed = unicodedata.normalize("NFKD", text.translate(_APOSTROPHES))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.casefold()


def slug(text: str) -> str:
    """Turn a heading or key into an id component.

    Args:
        text: Any text.

    Returns:
        Lowercase ASCII words joined by ``-``, e.g. ``"Titre III"`` → ``"titre-iii"``.
    """
    return _NON_ALNUM.sub("-", fold(text)).strip("-")


def tokens(text: str, stopwords: Iterable[str] = ()) -> list[str]:
    """Split text into folded search tokens.

    Single-character tokens are dropped unless they are digits, since numbers such as
    article or storey counts matter in regulatory text.

    Args:
        text: Any text.
        stopwords: Words to drop, compared after folding.

    Returns:
        The tokens, in text order.
    """
    stop = {fold(word) for word in stopwords}
    return [
        token
        for token in _WORD.findall(fold(text))
        if token not in stop and (len(token) > 1 or token.isdigit())
    ]
