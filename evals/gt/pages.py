"""Read the corpus pages and check quotes, for writing `doc` items (short output on purpose).

    uv run python -m evals.gt.pages find plu_reglement "acrotère" [--max 15]
    uv run python -m evals.gt.pages find plu_reglement UGa hauteur
    uv run python -m evals.gt.pages read plu_reglement 91 92 [--max-chars 6000]
    uv run python -m evals.gt.pages verify plu_reglement 91 "10 mètres à l\u2019acrotère"
    uv run python -m evals.gt.pages verify evals/datasets/doc/d02_uga_height.yaml

Pages are 1-based PDF indices (the printed page number of the regulation is one lower). `find`
matches case- and accent-insensitively; one argument is a regular expression, several are
words that must all occur on the page. `verify` runs the harness citation matcher (the one
that scores agent citations: same settings, same normalisation); on failure it says where the
quote does match, if anywhere in the document.
"""

import re
import sys
import unicodedata
from functools import cache
from pathlib import Path

import yaml

from agent.adapters.corpus.store import load_corpus
from agent.contracts.evidence import Citation, SourceKind
from agent.contracts.inputs.corpus import Corpus
from agent.runtime.citations.match import check_citation
from agent.tools.study.checks import corpus_facts
from agent.tools.study.messages import Verification
from evals.gt.settings import ROOT, settings
from evals.harness.matching.grounding import CitationMatcher

_PAGE_SETTINGS = settings().pages
_TASK_ARGS = 3
_QUOTE_ARGS = 4
_ITEM_ARGS = 2
_BOILERPLATE = tuple(re.compile(pattern, re.IGNORECASE) for pattern in _PAGE_SETTINGS.boilerplate)


def _say(text: str | None) -> None:
    """Write one CLI output line."""
    sys.stdout.write(f"{text}\n")


@cache
def _settings() -> tuple[Path, Verification]:
    """Corpus directory and ``policies.citations`` settings, read from ``conf/``."""
    corpus_cfg = yaml.safe_load((ROOT / "conf/corpus/default.yaml").read_text(encoding="utf-8"))
    policy = yaml.safe_load((ROOT / "conf/policies/default.yaml").read_text(encoding="utf-8"))
    settings = policy["citations"]
    verification = Verification(
        settings["min_score"], settings["neighbour_pages"], settings["max_quote_chars"]
    )
    return ROOT / "data" / str(corpus_cfg["id"]), verification


@cache
def _corpus() -> Corpus:
    """The ingested corpus."""
    return load_corpus(_settings()[0])


@cache
def _matcher() -> CitationMatcher:
    """The harness citation matcher, with the configured settings."""
    verification = _settings()[1]
    return CitationMatcher(corpus_facts(_corpus()), verification, check_raster=False)


def _unaccent(text: str) -> str:
    """Strip accents and unify apostrophes and spaces; case is kept so regex escapes survive."""
    text = unicodedata.normalize("NFKD", text.replace("\u2019", "'").replace("\u00a0", " "))
    return "".join(c for c in text if not unicodedata.combining(c))


def _fold(text: str) -> str:
    """Lowercase, strip accents and unify apostrophes and spaces, for searching."""
    return _unaccent(text).lower()


def _doc_id(name: str) -> str:
    """Resolve a document id or a unique prefix of one."""
    ids = [document.id for document in _corpus().documents]
    if name in ids:
        return name
    matches = [doc for doc in ids if doc.startswith(name)]
    if len(matches) != 1:
        msg = f"unknown document {name!r}; documents: {', '.join(ids)}"
        raise SystemExit(msg)
    return matches[0]


def _page_text(doc: str, number: int) -> str:
    """Text of one page (empty if the page does not exist)."""
    for page in _corpus().pages:
        if page.doc == doc and page.number == number:
            return page.text
    return ""


def _trim(text: str) -> str:
    """Drop page headers and footers and blank lines."""
    lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not any(rule.match(line.strip()) for rule in _BOILERPLATE)
    ]
    return "\n".join(lines)


def find(doc: str, terms: list[str], limit: int = _PAGE_SETTINGS.search_limit) -> int:
    """Print the pages matching the terms, with one snippet each."""
    doc = _doc_id(doc)
    try:
        patterns = [
            re.compile(re.escape(_fold(term)) if len(terms) > 1 else _unaccent(term), re.IGNORECASE)
            for term in terms
        ]
    except re.error as error:
        _say(f"bad regex: {error}")
        return 2
    hits = 0
    total = 0
    for page in _corpus().pages:
        if page.doc != doc:
            continue
        text = " ".join(_fold(page.text).split())
        found = [pattern.search(text) for pattern in patterns]
        if all(found):
            total += 1
            if hits < limit:
                first = found[0]
                assert first is not None  # noqa: S101
                start = max(first.start() - _PAGE_SETTINGS.snippet_chars, 0)
                end = first.end() + _PAGE_SETTINGS.snippet_chars
                _say(f"p.{page.number}: ...{text[start:end]}...")
                hits += 1
    if total > hits:
        _say(f"({total - hits} more pages; narrow the search or raise --max)")
    if not total:
        _say("no match")
    return 0 if total else 1


def read(doc: str, numbers: list[int], max_chars: int = _PAGE_SETTINGS.max_chars) -> int:
    """Print the trimmed text of the pages, truncated to ``max_chars`` per page."""
    doc = _doc_id(doc)
    for number in numbers:
        text = _trim(_page_text(doc, number))
        if not text:
            _say(f"--- {doc} p.{number} --- (no such page or no text)")
            continue
        suffix = f"\n[... {len(text) - max_chars} more chars]" if len(text) > max_chars else ""
        _say(f"--- {doc} p.{number} ---\n{text[:max_chars]}{suffix}")
    return 0


def verify_quote(doc: str, page: int, quote: str) -> bool:
    """Check one quote with the harness matcher; print one line."""
    doc = _doc_id(doc)
    citation = Citation(doc=doc, page=page, quote=quote, source_kind=SourceKind.REGULATORY)
    check = _matcher().check(citation)
    if not check.text_verifiable:
        _say(f"SKIP {doc} p.{page}: no text layer, quote not checkable")
        return True
    if check.verified:
        _say(f"OK   {doc} p.{page} score={check.score:.2f}")
        return True
    elsewhere = _where_it_matches(citation)
    hint = (
        f"; matches on p.{elsewhere}"
        if elsewhere is not None
        else "; matches on no page of the document"
    )
    _say(f'FAIL {doc} p.{page} score={check.score:.2f}{hint}: "{quote[:80]}"')
    return False


def _where_it_matches(citation: Citation) -> int | None:
    """Page of the document where the quote verifies, if any."""
    pages = _matcher()._corpus.pages
    policy = _settings()[1]
    for number in sorted({page for (doc, page) in pages if doc == citation.doc}):
        other = citation.model_copy(update={"page": number})
        check = check_citation(other, pages, min_score=policy.min_score, neighbour_pages=0)
        if check.verified:
            return number
    return None


def verify_item(path: Path) -> bool:
    """Check every evidence quote of an item file; print failures and a summary."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    checked = failed = 0
    for fact in data.get("facts", []):
        for evidence in fact.get("evidence", []):
            if not evidence.get("quote"):
                continue
            checked += 1
            if not verify_quote(evidence["doc"], evidence["page"], evidence["quote"]):
                failed += 1
    _say(f"{checked - failed}/{checked} quotes verified")
    return failed == 0


def main(argv: list[str]) -> int:
    """Dispatch ``find``, ``read`` and ``verify``."""
    limit = _PAGE_SETTINGS.search_limit
    max_chars = _PAGE_SETTINGS.max_chars
    args = list(argv)
    for flag in ("--max", "--max-chars"):
        if flag in args:
            index = args.index(flag)
            value = int(args[index + 1])
            del args[index : index + 2]
            if flag == "--max":
                limit = value
            else:
                max_chars = value
    if len(args) >= _TASK_ARGS and args[0] == "find":
        return find(args[1], args[2:], limit)
    if len(args) >= _TASK_ARGS and args[0] == "read" and all(a.isdigit() for a in args[2:]):
        return read(args[1], [int(a) for a in args[2:]], max_chars)
    if len(args) == _QUOTE_ARGS and args[0] == "verify" and args[2].isdigit():
        return 0 if verify_quote(args[1], int(args[2]), args[3]) else 1
    if len(args) == _ITEM_ARGS and args[0] == "verify" and args[1].endswith((".yaml", ".yml")):
        return 0 if verify_item(Path(args[1])) else 1
    _say(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
