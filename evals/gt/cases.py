"""List or show the planned cases of a level (``evals/cases/<level>.yaml``).

uv run python -m evals.gt.cases list surveyor
uv run python -m evals.gt.cases show surveyor s02_croix_de_fer
"""

import sys
from pathlib import Path

import yaml
from pydantic import ConfigDict, TypeAdapter

from agent.contracts.base import Contract

_MIN_ARGS = 2
_SHOW_ARGS = 3

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"


class CaseDescription(Contract):
    """A case index entry, preserving its variable authoring/provenance metadata."""

    model_config = ConfigDict(frozen=True, extra="allow")
    id: str
    tests: str = ""


def load_cases(level: str) -> list[CaseDescription]:
    """Read and validate the case index of a level."""
    data = yaml.safe_load((CASES_DIR / f"{level}.yaml").read_text(encoding="utf-8"))
    entries = data.get("cases") if isinstance(data, dict) else data
    return TypeAdapter(list[CaseDescription]).validate_python(entries)


def _say(text: str | None) -> None:
    """Write one CLI output line."""
    sys.stdout.write(f"{text}\n")


def main(argv: list[str]) -> int:
    """Print the case ids with what each tests, or one case in full."""
    if (
        len(argv) < _MIN_ARGS
        or argv[0] not in {"list", "show"}
        or (argv[0] == "show" and len(argv) != _SHOW_ARGS)
    ):
        _say(__doc__)
        return 2
    if not (CASES_DIR / f"{argv[1]}.yaml").is_file():
        _say(f"no case index for {argv[1]}")
        return 1
    cases = load_cases(argv[1])
    if argv[0] == "list":
        for case in cases:
            _say(f"{case.id}: {case.tests}")
        return 0
    found = [case for case in cases if case.id == argv[2]]
    if not found:
        _say(f"no case {argv[2]} in {argv[1]}")
        return 1
    _say(yaml.safe_dump(found[0].model_dump(mode="json"), allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
