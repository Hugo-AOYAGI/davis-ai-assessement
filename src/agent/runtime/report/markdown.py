from collections.abc import Iterable, Sequence

NONE = "—"


def escape_cell(text: str) -> str:
    """Make text safe inside a Markdown table cell.

    Args:
        text: Raw cell content.

    Returns:
        The text with pipes escaped and line breaks turned into ``<br>``.
    """
    lines = text.strip().replace("\r\n", "\n").split("\n")
    return "<br>".join(line.strip() for line in lines).replace("|", "\\|")


def one_line(text: str) -> str:
    """Collapse every run of whitespace, line breaks included, into a single space."""
    return " ".join(text.split())


def table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """Render a Markdown table, escaping every cell.

    Args:
        headers: Column titles.
        rows: One sequence of cells per row, in column order.

    Returns:
        The table, without a trailing newline.
    """
    lines = [_row(headers), _row(["---"] * len(headers))]
    lines.extend(_row(cells) for cells in rows)
    return "\n".join(lines)


def _row(cells: Sequence[str]) -> str:
    """Render one table row."""
    return "| " + " | ".join(escape_cell(cell) for cell in cells) + " |"


def bullets(items: Iterable[str], empty: str) -> str:
    """Render a bullet list, keeping multi-line items inside their bullet.

    Args:
        items: Item texts.
        empty: Text rendered instead when there is no item.

    Returns:
        The list, or ``empty``.
    """
    lines = [f"- {_indent(item.strip())}" for item in items]
    return "\n".join(lines) if lines else empty


def _indent(text: str) -> str:
    """Indent continuation lines so they stay in the current list item."""
    first, *rest = text.split("\n")
    return "\n".join([first, *(f"  {line}" if line.strip() else "" for line in rest)])


def number(value: float, decimals: int) -> str:
    """Format a number with at most ``decimals`` decimals, dropping trailing zeros.

    Args:
        value: Number to format.
        decimals: Maximum number of decimals.

    Returns:
        E.g. ``1200``, ``12.5``, ``4.25``.
    """
    text = f"{value:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def area(value: float) -> str:
    """Format a surface in square metres."""
    return f"{number(value, 1)} m²"


def metres(value: float) -> str:
    """Format a length in metres."""
    return f"{number(value, 2)} m"


def percent(ratio: float) -> str:
    """Format a ratio in [0, 1] as a percentage."""
    return f"{number(ratio * 100, 1)}%"
