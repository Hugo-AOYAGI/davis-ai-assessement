"""Rebuild the portable evaluation report from its retained score snapshots."""

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from evals.harness.passes.scoring import ItemResult

LEVELS = ("surveyor", "zoning", "doc", "e2e")
VERSIONS = (("v1-components", "v1-e2e"), ("v2-haiku",), ("v2-sonnet",))
LABELS = ("v1 Haiku", "v2 Haiku", "v2 Sonnet")


class Snapshot(BaseModel):
    """The item-level scores needed for the historical handoff report."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    items: tuple[ItemResult, ...]


def topic(key: str) -> str:
    """Group an end-to-end expected fact by the field it measures."""
    groups = (
        ("parcel_ids", "Parcels"),
        ("regime.zone", "Zone"),
        ("regime.overlays", "Legend items"),
        ("oap_applicable", "OAP applicability"),
        ("verdict", "Verdict"),
        ("max_footprint", "Footprint"),
        ("max_height", "Height"),
        ("max_storeys", "Storeys"),
        ("setbacks", "Setbacks"),
        ("green", "Green space"),
        ("parking", "Parking"),
        ("site_area", "Site area"),
    )
    return next((label for needle, label in groups if needle in key), "Other facts")


def load_versions(directory: Path) -> list[list[ItemResult]]:
    """Load the three configurations, rejecting mismatched item/fact denominators.

    Raises:
        ValueError: If a comparison contains missing, duplicate or changed expected facts.
    """
    versions = [
        [
            item
            for source in sources
            for item in Snapshot.model_validate_json(
                (directory / source / "scores.json").read_text(encoding="utf-8")
            ).items
        ]
        for sources in VERSIONS
    ]
    signatures = []
    for items in versions:
        if len({item.item_id for item in items}) != len(items):
            msg = "duplicate item in retained scores"
            raise ValueError(msg)
        signatures.append(
            {
                item.item_id: (item.level, tuple(f.key_or_statement for f in item.facts))
                for item in items
            }
        )
    if any(signature != signatures[0] for signature in signatures[1:]):
        msg = "retained scores do not compare the same items and expected facts"
        raise ValueError(msg)
    return versions


def payload(versions: list[list[ItemResult]]) -> str:
    """Build JavaScript constants from the scored items, without hand-entered totals."""
    selections = {
        level: [[item for item in items if item.level.value == level] for items in versions]
        for level in LEVELS
    }
    data = {
        "pass": {k: [sum(i.passed for i in v) for v in vs] for k, vs in selections.items()},
        "facts": {k: sum(len(i.facts) for i in vs[0]) for k, vs in selections.items()},
        "grounded": {
            k: [sum(f.grounded for i in v for f in i.facts) for v in vs]
            for k, vs in selections.items()
        },
        "cost": {
            k: [sum(i.run.cost_usd or 0 for i in v) / len(v) for v in vs]
            for k, vs in selections.items()
        },
        "time": {
            k: [sum(i.run.wall_time_s or 0 for i in v) / len(v) for v in vs]
            for k, vs in selections.items()
        },
    }
    counts = {k: len(vs[0]) for k, vs in selections.items()}
    end = selections["e2e"]
    topics = sorted({topic(f.key_or_statement) for i in end[0] for f in i.facts})
    grouped = [
        [
            label,
            [
                sum(f.grounded for i in v for f in i.facts if topic(f.key_or_statement) == label)
                for v in end
            ],
            sum(topic(f.key_or_statement) == label for i in end[0] for f in i.facts),
        ]
        for label in topics
    ]
    claims = {
        "checked": {
            k: sum(len(i.notes.must_not) if i.notes else 0 for i in vs[0])
            for k, vs in selections.items()
        },
        "hits": {
            k: [sum(j.hit for i in v if i.notes for j in i.notes.must_not) for v in vs]
            for k, vs in selections.items()
        },
    }
    constants = {
        "D": data,
        "E2E": grouped,
        "P": {
            key: {i.item_id: int(i.passed) for i in items}
            for key, items in zip("ABC", versions, strict=True)
        },
        "MN": claims,
        "COUNTS": counts,
        "FACT_TOTAL": sum(data["facts"].values()),
        "CASE_TOTAL": sum(counts.values()),
        "TOTAL_COST": [sum(i.run.cost_usd or 0 for i in items) for items in versions],
    }
    return "\n".join(f"const {key} = {json.dumps(value)};" for key, value in constants.items())


def claim_rows(versions: list[list[ItemResult]]) -> str:
    """Render forbidden claims with their actual judge descriptions and configurations."""
    hits: dict[tuple[str, str], list[str]] = defaultdict(list)
    for label, items in zip(LABELS, versions, strict=True):
        for item in items:
            for result in item.notes.must_not if item.notes else ():
                if result.hit:
                    hits[item.item_id, result.subject].append(label)
    return "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(cell)}</td>" for cell in (key, claim, ", ".join(v)))
        + "</tr>"
        for (key, claim), v in sorted(hits.items())
    )


def main() -> None:
    """Write a self-contained HTML report from the handoff directory supplied on the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path, help="Directory containing evaluation/ snapshots")
    args = parser.parse_args()
    directory = args.handoff / "evaluation"
    versions = load_versions(directory)
    template = (directory / "template.html").read_text(encoding="utf-8")
    rendered = template.replace("<!-- SCORE_DATA -->", payload(versions)).replace(
        "<!-- CLAIM_ROWS -->", claim_rows(versions)
    )
    totals = {
        "CASE_TOTAL": len(versions[0]),
        "FACT_TOTAL": sum(len(item.facts) for item in versions[0]),
        "CRITICAL_TOTAL": sum(f.critical for item in versions[0] for f in item.facts),
    }
    for key, value in totals.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    (args.handoff / "evaluation.html").write_text(rendered, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
