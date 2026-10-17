from collections.abc import Sequence

from rank_bm25 import BM25Okapi

from agent.adapters.corpus.text import tokens


class Bm25:
    """BM25 (Okapi) keyword ranking over a fixed sequence of texts.

    Texts and queries are tokenized with :func:`agent.adapters.corpus.text.tokens`, so matching
    ignores accents, case and the given stopwords.
    """

    def __init__(self, texts: Sequence[str], stopwords: Sequence[str] = ()) -> None:
        """Index the texts.

        Args:
            texts: The texts to rank; results refer to them by position.
            stopwords: Words ignored in texts and queries.
        """
        self._stopwords = frozenset(stopwords)
        tokenized = [tokens(text, self._stopwords) for text in texts]
        self._model = BM25Okapi(tokenized) if any(tokenized) else None

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Rank the texts against a query.

        Args:
            query: Free-text query.
            k: Maximum number of results.

        Returns:
            ``(index, score)`` pairs for texts scoring above zero, best first (ties keep text
            order). Empty when the query has no searchable word or nothing was indexed.
        """
        terms = tokens(query, self._stopwords)
        if self._model is None or not terms or k <= 0:
            return []
        scores = [float(score) for score in self._model.get_scores(terms)]
        ranked = sorted(
            ((index, score) for index, score in enumerate(scores) if score > 0),
            key=lambda pair: (-pair[1], pair[0]),
        )
        return ranked[:k]
