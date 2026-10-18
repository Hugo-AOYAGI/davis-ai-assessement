"""Independent BAN and cadastral access, projection and source inspection."""

import csv
import gzip
import json
import unicodedata

import httpx
import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from evals.gt.geography.records import ParcelCollection, ParcelFeature
from evals.gt.settings import ROOT, settings

_SETTINGS = settings()
CACHE = ROOT / _SETTINGS.ban_cache
_TO_METRIC = Transformer.from_crs(_SETTINGS.geographic_crs, _SETTINGS.metric_crs, always_xy=True)
_TO_GEO = Transformer.from_crs(_SETTINGS.metric_crs, _SETTINGS.geographic_crs, always_xy=True)


def transform(projection: Transformer, geometry: BaseGeometry) -> BaseGeometry:
    """Reproject a geometry with a pyproj transformer."""
    result = shapely.transform(
        geometry, lambda xy: np.column_stack(projection.transform(xy[:, 0], xy[:, 1]))
    )
    if not isinstance(result, BaseGeometry):
        msg = "reprojection did not return a geometry"
        raise TypeError(msg)
    return result


def fold(text: str) -> str:
    """Lower-case a text and strip accents, hyphens and double spaces."""
    plain = unicodedata.normalize("NFKD", text.replace("-", " ")).encode("ascii", "ignore")
    return " ".join(plain.decode().lower().split())


def load_ban() -> list[dict[str, str]]:
    """Return the BAN rows of the commune, downloading the department export once."""
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_bytes(_download_ban())
    with gzip.open(CACHE, "rt", encoding="utf-8") as handle:
        rows = csv.DictReader(handle, delimiter=";")
        return [row for row in rows if row["code_insee"] == _SETTINGS.commune_code]


def sector(lon: float, lat: float) -> str:
    """Name the PLU sector a point falls in, roughly (selection aid, not an oracle value)."""
    if lon >= _SETTINGS.sectors.moulon_min_lon and lat >= _SETTINGS.sectors.moulon_min_lat:
        return "Moulon"
    if lon < _SETTINGS.sectors.chevry_max_lon and lat < _SETTINGS.sectors.chevry_max_lat:
        return "Chevry"
    return "Vallee"


def describe(row: dict[str, str]) -> str:
    """One line for a BAN row."""
    lon, lat = float(row["lon"]), float(row["lat"])
    street = (
        f"{row['numero']}{row['rep'] or ''} {row['nom_voie']}, "
        f"{row['code_postal']} {_SETTINGS.commune_name}"
    )
    cad, place = row["cad_parcelles"], f"{sector(lon, lat)} | {lon:.5f},{lat:.5f}"
    return f"{row['id']} | {street} | cad={cad} | {place}"


def carto(params: dict[str, str]) -> list[ParcelFeature]:
    """Query API Carto and return the parcel features."""
    reply = httpx.get(_SETTINGS.carto_url, params=params, timeout=_SETTINGS.timeout_s)
    reply.raise_for_status()
    return list(ParcelCollection.model_validate_json(reply.content).features)


def by_id(idu: str) -> ParcelFeature | None:
    """Return the cadastre feature of a parcel id, or None."""
    params = {
        "code_insee": idu[:5],
        "com_abs": idu[5:8],
        "section": idu[8:10],
        "numero": idu[10:],
    }
    found = [f for f in carto(params) if f.properties.idu == idu]
    return found[0] if found else None


def metric(feature: ParcelFeature) -> BaseGeometry:
    """Return a feature's geometry in Lambert-93."""
    return transform(_TO_METRIC, shape(feature.geometry))


def around(geometry: BaseGeometry, radius_m: float) -> list[ParcelFeature]:
    """Return the cadastre features within ``radius_m`` of a Lambert-93 geometry."""
    area = transform(_TO_GEO, geometry.buffer(radius_m))
    geom = json.dumps(mapping(area), separators=(",", ":"))
    return carto({"geom": geom, "_limit": str(_SETTINGS.carto_limit)})


def _download_ban() -> bytes:
    """Download a successful BAN export without caching HTTP error pages."""
    reply = httpx.get(_SETTINGS.ban_url, timeout=_SETTINGS.timeout_s, follow_redirects=True)
    reply.raise_for_status()
    return reply.content
