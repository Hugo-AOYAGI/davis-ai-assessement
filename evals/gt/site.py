"""Oracle for surveyor items, independent of the agent's geocoder and parcel search.

Random cases come from the BAN export (``cad_parcelles`` column); parcel existence, area, polygon
and neighbours come from the cadastre (API Carto). Output is a few lines.

    uv run python -m evals.gt.site random --seed 7 --n 6       # BAN addresses linked to a parcel
    uv run python -m evals.gt.site ban "4 rue Joliot Curie"    # BAN rows matching a text or id
    uv run python -m evals.gt.site parcel 91272000CR0247 [more ids] [--save poly.geojson]
    uv run python -m evals.gt.site near 2.1653 48.7098 [radius_m] # parcels around a point
"""

import argparse
import json
import random
import sys
from pathlib import Path

import shapely
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from evals.gt.geography.source import (
    _TO_GEO,
    _TO_METRIC,
    around,
    by_id,
    describe,
    fold,
    load_ban,
    metric,
    sector,
    transform,
)
from evals.gt.settings import settings

_SETTINGS = settings()


def say(*lines: str) -> None:
    """Write machine-readable command output to standard output."""
    sys.stdout.write("\n".join(lines) + "\n")


def run_random(args: argparse.Namespace) -> None:
    """Draw BAN addresses that link exactly one parcel, certified, one per street."""
    rows = [
        r
        for r in load_ban()
        if r["cad_parcelles"]
        and "|" not in r["cad_parcelles"]
        and r["certification_commune"] == "1"
    ]
    if args.sector:
        rows = [r for r in rows if sector(float(r["lon"]), float(r["lat"])) == args.sector]
    random.Random(args.seed).shuffle(rows)  # noqa: S311
    seen: set[str] = set()
    for row in rows:
        if row["nom_voie"] in seen:
            continue
        seen.add(row["nom_voie"])
        say(describe(row))
        if len(seen) >= args.n:
            break


def run_ban(args: argparse.Namespace) -> None:
    """List BAN rows whose id equals the query or whose address contains it."""
    query = fold(args.query)
    hits = [
        r
        for r in load_ban()
        if r["id"] == args.query or query in fold(f"{r['numero']}{r['rep'] or ''} {r['nom_voie']}")
    ]
    say(f"{len(hits)} BAN row(s)", *(describe(r) for r in hits[: _SETTINGS.max_listed]))


def run_parcel(args: argparse.Namespace) -> None:
    """Check parcels exist, then print area, neighbours and unregistered frontage."""
    features = {idu: by_id(idu) for idu in args.ids}
    missing = [idu for idu, feature in features.items() if feature is None]
    for idu, feature in features.items():
        if feature is not None:
            props = feature.properties
            say(f"{idu}: exists, contenance={props.contenance} m2")
    if missing:
        say(f"NOT IN CADASTRE: {', '.join(missing)}")
        return
    union = unary_union([metric(f) for f in features.values() if f is not None])
    if union.geom_type != "Polygon":
        say(f"selection is not one piece ({union.geom_type}); ids not adjacent")
        return
    centre = transform(_TO_GEO, union.centroid)
    say(
        f"site {'+'.join(args.ids)}: polygon area={union.area:.1f} m2, "
        f"perimeter={union.length:.1f} m, centroid={centre.x:.5f},{centre.y:.5f}"
    )
    report_neighbours(union, set(args.ids))
    if args.save:
        feature = {"type": "Feature", "properties": {"ids": args.ids}, "geometry": None}
        feature["geometry"] = mapping(transform(_TO_GEO, union))
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(feature), encoding="utf-8")
        say(f"polygon (WGS84) saved to {args.save}")


def report_neighbours(union: BaseGeometry, own: set[str]) -> None:
    """Print the parcels touching the site and the length that borders unregistered ground."""
    covered: list[BaseGeometry] = []
    lines = []
    for feature in around(union, _SETTINGS.neighbour_m):
        idu = feature.properties.idu
        if idu in own:
            continue
        zone = metric(feature).buffer(_SETTINGS.neighbour_m)
        shared = union.boundary.intersection(zone).length
        if shared > _SETTINGS.neighbour_m:
            covered.append(zone)
            lines.append((shared, f"{idu} ({shared:.0f} m, {feature.properties.contenance} m2)"))
    free = union.boundary.difference(unary_union(covered)).length if covered else union.length
    names = ", ".join(text for _, text in sorted(lines, reverse=True)) or "none"
    say(f"neighbour parcels: {names}", f"frontage on unregistered ground: {free:.0f} m")


def run_near(args: argparse.Namespace) -> None:
    """List the parcels within a radius of a WGS84 point, nearest first."""
    point = transform(_TO_METRIC, shapely.Point(args.lon, args.lat))
    ranked = sorted(
        ((metric(f).distance(point), f) for f in around(point, args.radius)),
        key=lambda pair: (pair[0], pair[1].properties.idu),
    )
    say(f"{len(ranked)} parcel(s) within {args.radius:.0f} m (0.0 = point inside the parcel)")
    for distance, feature in ranked[: _SETTINGS.max_listed]:
        props = feature.properties
        say(f"{props.idu}: {distance:.1f} m, contenance={props.contenance} m2")


def build_parser() -> argparse.ArgumentParser:
    """Build the command line."""
    parser = argparse.ArgumentParser(description="Surveyor oracle (BAN + cadastre)")
    sub = parser.add_subparsers(dest="command", required=True)
    rand = sub.add_parser("random")
    rand.add_argument("--seed", type=int, default=0)
    rand.add_argument("--n", type=int, default=_SETTINGS.random_count)
    rand.add_argument("--sector", choices=["Moulon", "Chevry", "Vallee"])
    rand.set_defaults(run=run_random)
    ban = sub.add_parser("ban")
    ban.add_argument("query")
    ban.set_defaults(run=run_ban)
    parcel = sub.add_parser("parcel")
    parcel.add_argument("ids", nargs="+")
    parcel.add_argument("--save")
    parcel.set_defaults(run=run_parcel)
    near = sub.add_parser("near")
    near.add_argument("lon", type=float)
    near.add_argument("lat", type=float)
    near.add_argument("radius", type=float, nargs="?", default=_SETTINGS.near_radius_m)
    near.set_defaults(run=run_near)
    return parser


def main(argv: list[str]) -> int:
    """Run a command."""
    args = build_parser().parse_args(argv)
    args.run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
