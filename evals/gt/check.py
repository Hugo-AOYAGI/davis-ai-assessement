"""Check an item file loads, and print what it holds (drafts accepted).

uv run python -m evals.gt.check evals/datasets/surveyor/s02_croix_de_fer.yaml
"""

import sys
from pathlib import Path

from evals.harness.items import ItemError, load_item


def _say(text: str | None) -> None:
    """Write one CLI output line."""
    sys.stdout.write(f"{text}\n")


def main(argv: list[str]) -> int:
    """Load each path; print one line per item, or the error."""
    if not argv:
        _say(__doc__)
        return 2
    status = 0
    for name in argv:
        try:
            item = load_item(Path(name))
        except ItemError as error:
            _say(f"INVALID {name}: {error}")
            status = 1
            continue
        _say(
            f"OK {item.id} [{item.level}, {item.status}] facts={len(item.facts)} "
            f"must_flag={len(item.must_flag)} must_not={len(item.must_not)}"
        )
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
