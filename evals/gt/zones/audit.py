"""Audit the zoning benchmark against retained independent oracle snapshots.

``uv run python -m evals.gt.zones.audit`` also recomputes all intersections from
the local archived shapefiles. This is a dataset check, not an agent experiment.
"""

import sys
from pathlib import Path

from evals.gt.geography.records import Intersection, OracleSnapshot
from evals.gt.settings import ROOT, settings
from evals.gt.zones.oracle import DEFAULT_ARCHIVE, oracle
from evals.harness.items import KeyFact, ZoningInput, load_item

FIXTURES = ROOT / "evals/fixtures/zoning"
_SETTINGS = settings()
_PPRI = "Zone de risques d'inondation (PPRi Vallée de l'Yvette approuvé le 26 septembre 2006)"
_RESERVED = (
    "Emplacements réservés pour équipements et aménagements divers, "
    "création ou amélioration de voirie"
)
_RETAIL = "Linéaire identifié pour la sauvegarde du commerce"
_LABEL_RULES = {
    "Espaces Boisés Classés": ("PRESCRIPTION_SURF", "01", ""),
    "Secteur à Orientation d'Aménagement et de Programmation": ("PRESCRIPTION_SURF", "18", ""),
    _PPRI: ("PRESCRIPTION_SURF", "02", "inondation"),
    "Zone humide": ("PRESCRIPTION_SURF", "31", ""),
    _RESERVED: ("PRESCRIPTION_SURF", "05", ""),
    "Zone correspondant au périmètre de prescriptions sanitaires": (
        "PRESCRIPTION_SURF",
        "02",
        "prescription sanitaire",
    ),
    _RETAIL: ("PRESCRIPTION_LIN", "22", ""),
}


def _label_rows(label: str, layers: dict[str, tuple[Intersection, ...]]) -> list[Intersection]:
    """Map exact printed labels to independent CNIG features, without agent tools."""
    layer, type_code, fragment = _LABEL_RULES[label]
    return [
        row
        for row in layers[layer]
        if row.attributes["TYPEPSC"] == type_code and fragment in row.attributes["LIBELLE"].lower()
    ]


def _applies(row: Intersection, *, linear: bool) -> bool:
    """Use positive area for surfaces; a shared surface boundary is not applicability."""
    if linear:
        return bool(row.intersection_length_m > _SETTINGS.min_linear_length_m)
    return bool(row.intersection_area_m2 > 0)


def _check_overlays(
    item_id: str, fact: KeyFact, layers: dict[str, tuple[Intersection, ...]]
) -> None:
    """Check asserted presences and absences against their appropriate source layers."""
    for label in fact.present or ():
        if not any(_applies(row, linear=label == _RETAIL) for row in _label_rows(label, layers)):
            msg = f"{item_id}: unproven presence of {label}"
            raise ValueError(msg)
    for label in fact.absent or ():
        if any(_applies(row, linear=label == _RETAIL) for row in _label_rows(label, layers)):
            msg = f"{item_id}: false absence of {label}"
            raise ValueError(msg)


def _check_zone(item_id: str, fact: KeyFact, zones: set[str]) -> None:
    """Check that all meaningful intersecting zones are represented in the expectation."""
    expected = set(fact.any_of or (fact.expect,))
    if zones != expected:
        msg = f"{item_id}: expected zones {expected}, oracle gives {zones}"
        raise ValueError(msg)


def audit(path: Path) -> None:
    """Check item expectations and saved calculations against the original geometry."""
    item = load_item(path)
    snapshot = OracleSnapshot.model_validate_json(
        (FIXTURES / f"{item.id}.oracle.json").read_bytes()
    )
    recomputed = oracle(FIXTURES / f"{item.id}.cadastre.json", DEFAULT_ARCHIVE)
    if snapshot != recomputed:
        msg = f"{item.id}: stale oracle snapshot"
        raise ValueError(msg)
    if not isinstance(item.input, ZoningInput) or list(item.input.parcel_ids) != [
        recomputed.parcel_id
    ]:
        msg = f"{item.id}: item parcel does not match the fixture"
        raise ValueError(msg)
    zones = {
        row.attributes["LIBELLE"]
        for row in recomputed.layers["ZONE_URBA"]
        if row.intersection_area_m2 > _SETTINGS.min_zone_area_m2
    }
    for fact in item.facts:
        if not isinstance(fact, KeyFact):
            continue
        if fact.key == "zone":
            _check_zone(item.id, fact, zones)
        if fact.key == "overlays":
            _check_overlays(item.id, fact, recomputed.layers)


def main() -> None:
    """Check all saved zoning items, including drafts, then print the checked count."""
    paths = sorted((ROOT / "evals/datasets/zoning").glob("*.yaml"))
    for path in paths:
        audit(path)
    sys.stdout.write(f"{len(paths)} zoning items: snapshots and spatial facts agree\n")


if __name__ == "__main__":
    main()
