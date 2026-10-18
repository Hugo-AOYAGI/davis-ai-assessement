import pytest
from pydantic import ValidationError

from agent.ingest.rules import HeadingRule, Line, SplitterConfig
from agent.ingest.split import split_document

BOLD = "Demo-Bold"
BODY = "Demo"


def line(page: int, text: str, y: float = 100.0, size: float = 9.0, font: str = BODY) -> Line:
    return Line(page=page, text=text, y0=y, size=size, font=font, lead=text)


def heading(page: int, text: str, y: float = 100.0) -> Line:
    return line(page, text, y, size=14.0, font=BOLD)


CHAPTER = HeadingRule(
    level="chapter",
    pattern=r"^(?P<number>\d+) (?P<title>.+)$",
    font="Bold",
    min_size=12,
    key="chapitre-{number}",
    title="{number} {title}",
)
ARTICLE = HeadingRule(
    level="article",
    inside="chapter",
    pattern=r"^Article (?P<article>\d+)",
    font="Bold",
    min_size=12,
    key="{article}",
    continuation=r"^[A-Z ]+$",
)
LABEL = HeadingRule(
    level="zone",
    scope="header",
    inside="chapter/chapitre-2",
    pattern=r"^Zone (?P<zone>[A-Z]+)$",
    key="{zone}",
)


def config(*rules: HeadingRule, **overrides: object) -> SplitterConfig:
    values: dict[str, object] = {
        "levels": ("chapter", "zone", "article"),
        "header_max_y": 50.0,
        "footer_min_y": 800.0,
        "max_continuation": 2,
        "preamble": "Préambule",
        "rules": rules,
    }
    return SplitterConfig.model_validate(values | overrides)


def test_running_heading_is_dropped():
    lines = [
        heading(1, "1 Intro"),
        line(1, "first", 120),
        heading(2, "1 Intro"),
        line(2, "second", 120),
        heading(3, "1 Intro"),
    ]
    (chapter,) = split_document("doc", lines, config(CHAPTER))
    assert chapter.id == "doc/chapitre-1"
    assert (chapter.page_start, chapter.page_end) == (1, 2)
    assert chapter.text == "1 Intro\nfirst\nsecond"


def test_preamble_and_hierarchical_ids():
    lines = [
        line(1, "cover text"),
        heading(2, "1 Intro"),
        heading(2, "Article 3 - Rules", 120),
        line(2, "body", 140),
    ]
    preamble, chapter, article = split_document("doc", lines, config(CHAPTER, ARTICLE))
    assert (preamble.id, preamble.heading_path, preamble.text) == (
        "doc/preambule",
        ("Préambule",),
        "cover text",
    )
    assert chapter.text == "1 Intro"
    assert article.id == "doc/chapitre-1/3"
    assert article.heading_path == ("1 Intro", "Article 3 - Rules")
    assert (article.article, article.text) == ("3", "Article 3 - Rules\nbody")


def test_continuation_lines_extend_the_title():
    lines = [
        heading(1, "1 Intro"),
        heading(1, "Article 1 - SOME", 120),
        heading(1, "LONG", 140),
        heading(1, "TITLE", 160),
        heading(1, "EXTRA", 180),
        line(1, "body", 200),
    ]
    sections = split_document("doc", lines, config(CHAPTER, ARTICLE))
    article = sections[1]
    assert article.heading_path[-1] == "Article 1 - SOME LONG TITLE"
    assert article.text == "Article 1 - SOME\nLONG\nTITLE\nEXTRA\nbody"


def test_duplicate_sibling_ids_are_suffixed():
    lines = [
        heading(1, "1 Intro"),
        heading(1, "Article 5 - A", 120),
        heading(1, "Article 6 - B", 140),
        heading(1, "Article 5 - C", 160),
    ]
    ids = [s.id for s in split_document("doc", lines, config(CHAPTER, ARTICLE))]
    assert ids == ["doc/chapitre-1", "doc/chapitre-1/5", "doc/chapitre-1/6", "doc/chapitre-1/5-2"]


def test_inside_restricts_rules():
    lines = [heading(1, "Article 1 - orphan"), heading(1, "1 Intro", 120)]
    sections = split_document("doc", lines, config(CHAPTER, ARTICLE))
    assert [s.id for s in sections] == ["doc/preambule", "doc/chapitre-1"]


def test_header_rule_opens_zone_and_header_is_excluded():
    lines = [
        heading(1, "1 Intro"),
        heading(2, "2 Zones"),
        line(3, "Zone UA", y=20),
        line(3, "ua text", 120),
        line(4, "Zone UA", y=20),
        heading(4, "Article 1 - X", 120),
        line(5, "Zone UB", y=20),
        line(5, "ub text", 120),
    ]
    by_id = {s.id: s for s in split_document("doc", lines, config(CHAPTER, ARTICLE, LABEL))}
    assert list(by_id) == [
        "doc/chapitre-1",
        "doc/chapitre-2",
        "doc/chapitre-2/ua",
        "doc/chapitre-2/ua/1",
        "doc/chapitre-2/ub",
    ]
    assert by_id["doc/chapitre-2/ua"].text == "ua text"
    assert by_id["doc/chapitre-2/ua"].page_start == 3
    assert by_id["doc/chapitre-2/ua/1"].zone == "UA"
    assert by_id["doc/chapitre-2/ub"].page_start == 5


def test_footer_band_and_marker():
    lines = [
        heading(1, "1 Intro"),
        line(1, "kept", 700),
        line(1, "12", 750),
        line(1, "Footer line", 750),
        line(1, "below", 760),
        line(2, "page footer", 810),
    ]
    (chapter,) = split_document("doc", lines, config(CHAPTER, footer="^Footer"))
    assert chapter.text == "1 Intro\nkept"


def test_rule_rejects_unknown_group():
    with pytest.raises(ValidationError):
        HeadingRule(level="chapter", pattern=r"^(?P<chapter>\d+)")


def test_config_rejects_unknown_level():
    with pytest.raises(ValidationError):
        config(HeadingRule(level="part", pattern="^x"))
