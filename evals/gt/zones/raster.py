"""Render unaltered plan crops and diagnostic parcel/zone overlays for source review.

The global affine registration was fitted to the raster fills of all 152
archived zone polygons on a 12 m grid. Its coefficients and method are retained
in ``registration.json``. It is an approximate visual alignment, not survey
geometry or an oracle for the expected zoning values.
"""

import argparse
from pathlib import Path

import pymupdf
from shapely.geometry import box

from evals.gt.geography.records import ParcelCollection, Registration
from evals.gt.geography.source import metric
from evals.gt.settings import ROOT, settings
from evals.gt.zones.shapes import read_shapes

_SETTINGS = settings()
_REGISTRATION = Registration.model_validate_json(
    Path(__file__).with_name("registration.json").read_bytes()
)
_MATRIX = _REGISTRATION.matrix


def pixel(x: float, y: float) -> tuple[float, float]:
    """Map Lambert-93 coordinates to the plan normalized to 2000 pixels wide."""
    dx, dy = x - _REGISTRATION.origin_x, y - _REGISTRATION.origin_y
    return (
        _MATRIX[0] * dx + _MATRIX[1] * dy + _MATRIX[4],
        _MATRIX[2] * dx + _MATRIX[3] * dy + _MATRIX[5],
    )


def render(item_id: str) -> None:
    """Save the source crop and a labelled diagnostic with full parcel boundaries."""
    target = ROOT / "evals/fixtures/zoning"
    source = ParcelCollection.model_validate_json(
        (target / f"{item_id}.cadastre.json").read_bytes()
    )
    parcel = metric(source.features[0])
    cx, cy = pixel(parcel.centroid.x, parcel.centroid.y)
    extent = max(
        _SETTINGS.raster.min_crop_half_px,
        max(parcel.bounds[2] - parcel.bounds[0], parcel.bounds[3] - parcel.bounds[1])
        * _MATRIX[0]
        * _SETTINGS.raster.crop_extent_ratio,
    )
    clip = pymupdf.Rect(cx - extent, cy - extent, cx + extent, cy + extent)
    source_pdf = ROOT / _SETTINGS.plan_pdf
    plan = pymupdf.open(source_pdf)
    page = plan[0]
    factor = page.rect.width / _REGISTRATION.normalized_width
    pdf_clip = clip * pymupdf.Matrix(factor, factor)
    page.get_pixmap(
        matrix=pymupdf.Matrix(_SETTINGS.raster.render_scale, _SETTINGS.raster.render_scale),
        clip=pdf_clip,
    ).save(target / f"{item_id}.plan.png")
    nearby = box(*parcel.buffer(_SETTINGS.raster.nearby_m).bounds)
    for geometry, _ in read_shapes(
        ROOT / _SETTINGS.gpu_archive / _SETTINGS.shape_template.format(layer="ZONE_URBA")
    ):
        if geometry is None or not geometry.intersects(nearby):
            continue
        for part in geometry.geoms if hasattr(geometry, "geoms") else (geometry,):
            points = [pymupdf.Point(*pixel(x, y)) * factor for x, y in part.exterior.coords]
            page.draw_polyline(
                points, color=(0, 0, 1), width=_SETTINGS.raster.zone_line_width * factor
            )
    for part in parcel.geoms if hasattr(parcel, "geoms") else (parcel,):
        points = [pymupdf.Point(*pixel(x, y)) * factor for x, y in part.exterior.coords]
        page.draw_polyline(
            points, color=(1, 0, 0), width=_SETTINGS.raster.parcel_line_width * factor
        )
    page.insert_text(
        (pdf_clip.x0 + 5, pdf_clip.y0 + 10), item_id, fontsize=8, color=(0, 0, 0), fill=(0, 0, 0)
    )
    page.get_pixmap(
        matrix=pymupdf.Matrix(_SETTINGS.raster.render_scale, _SETTINGS.raster.render_scale),
        clip=pdf_clip,
    ).save(target / f"{item_id}.review.png")
    plan.close()


def main() -> None:
    """Render one item by id, or every saved zoning fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("item_ids", nargs="*")
    args = parser.parse_args()
    item_ids = args.item_ids or [
        path.name.removesuffix(".cadastre.json")
        for path in sorted((ROOT / "evals/fixtures/zoning").glob("*.cadastre.json"))
    ]
    for item_id in item_ids:
        render(item_id)


if __name__ == "__main__":
    main()
