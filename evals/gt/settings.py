"""Typed settings for independent ground-truth authoring commands."""

from functools import cache
from pathlib import Path

import yaml

from agent.contracts.base import Contract

ROOT = Path(__file__).resolve().parents[2]


class Sectors(Contract):
    """Approximate geographic sectors used only to select varied addresses."""

    moulon_min_lon: float
    moulon_min_lat: float
    chevry_max_lon: float
    chevry_max_lat: float


class RasterSettings(Contract):
    """Diagnostic crop and overlay rendering controls."""

    min_crop_half_px: float
    crop_extent_ratio: float
    nearby_m: float
    render_scale: float
    zone_line_width: float
    parcel_line_width: float


class PageSettings(Contract):
    """Console output limits for document evidence inspection."""

    snippet_chars: int
    search_limit: int
    max_chars: int
    boilerplate: tuple[str, ...]


class GroundTruthSettings(Contract):
    """Service endpoints, archived sources and independent oracle tolerances."""

    ban_url: str
    carto_url: str
    commune_code: str
    commune_name: str
    ban_cache: Path
    timeout_s: float
    neighbour_m: float
    max_listed: int
    carto_limit: int
    random_count: int
    near_radius_m: float
    geographic_crs: str
    metric_crs: str
    sectors: Sectors
    gpu_archive: Path
    gpu_version: str
    shape_template: str
    reference_parcel: Path
    zone_layers: tuple[str, ...]
    min_zone_area_m2: float
    min_linear_length_m: float
    plan_pdf: Path
    raster: RasterSettings
    pages: PageSettings


@cache
def settings() -> GroundTruthSettings:
    """Load benchmark-authoring settings separately from the agent's spatial logic."""
    return GroundTruthSettings.model_validate(
        yaml.safe_load((ROOT / "conf/ground_truth/default.yaml").read_text(encoding="utf-8"))
    )
