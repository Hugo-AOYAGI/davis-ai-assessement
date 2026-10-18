"""Intersect a parcel with the archived GPU source independently of agent geometry.

Run ``uv run python -m evals.gt.zones.oracle`` for the reference parcel. This command
needs the original archived shapefiles; retained snapshots remain inspectable offline.
"""

import argparse
import hashlib
import sys
from pathlib import Path

from evals.gt.geography.records import Intersection, OracleSnapshot, ParcelCollection
from evals.gt.geography.source import metric
from evals.gt.settings import ROOT, settings
from evals.gt.zones.shapes import read_shapes

_SETTINGS = settings()
DEFAULT_PARCEL = ROOT / _SETTINGS.reference_parcel
DEFAULT_ARCHIVE = ROOT / _SETTINGS.gpu_archive


def oracle(parcel_path: Path, archive: Path) -> OracleSnapshot:
    """Return independently calculated intersections and hashes of all source inputs."""
    feature = ParcelCollection.model_validate_json(parcel_path.read_bytes()).features[0]
    parcel = metric(feature)
    files = [parcel_path]
    layers: dict[str, tuple[Intersection, ...]] = {}
    for layer in _SETTINGS.zone_layers:
        path = archive / _SETTINGS.shape_template.format(layer=layer)
        files.extend(path.with_suffix(suffix) for suffix in (".shp", ".dbf", ".prj"))
        rows: list[Intersection] = []
        for index, (geometry, attributes) in enumerate(read_shapes(path), start=1):
            if geometry is None:
                continue
            intersection = geometry.intersection(parcel)
            rows.append(
                Intersection(
                    record=index,
                    attributes=attributes,
                    intersection_area_m2=intersection.area,
                    intersection_fraction=intersection.area / parcel.area,
                    intersection_length_m=intersection.length,
                    distance_m=geometry.distance(parcel),
                    bounds_l93=geometry.bounds,
                )
            )
        layers[layer] = tuple(sorted(rows, key=lambda row: row.distance_m))
    return OracleSnapshot(
        parcel_id=feature.properties.idu,
        parcel_area_m2=parcel.area,
        gpu_version=_SETTINGS.gpu_version,
        crs=_SETTINGS.metric_crs,
        sha256={
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
        layers=layers,
    )


def main() -> None:
    """Write oracle evidence as JSON; redirect standard output to retain a snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parcel", type=Path, default=DEFAULT_PARCEL)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args()
    sys.stdout.write(oracle(args.parcel, args.archive).model_dump_json(indent=2) + "\n")


if __name__ == "__main__":
    main()
