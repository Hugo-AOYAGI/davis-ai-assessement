"""Validated source features and reproducible spatial-oracle output."""

from pydantic import AliasChoices, ConfigDict, Field, JsonValue

from agent.contracts.base import Contract


class ParcelProperties(Contract):
    """The cadastral attributes needed by the independent oracle."""

    model_config = ConfigDict(frozen=True, extra="ignore")
    idu: str = Field(validation_alias=AliasChoices("idu", "id"))
    contenance: float | None = None


class ParcelFeature(Contract):
    """A cadastral GeoJSON feature, with geometry kept in its source CRS."""

    model_config = ConfigDict(frozen=True, extra="ignore")
    properties: ParcelProperties
    geometry: dict[str, JsonValue]


class ParcelCollection(Contract):
    """The relevant part of an API Carto FeatureCollection."""

    model_config = ConfigDict(frozen=True, extra="ignore")
    features: tuple[ParcelFeature, ...]


class Intersection(Contract):
    """One source feature's independently calculated relationship to a parcel."""

    record: int
    attributes: dict[str, str]
    intersection_area_m2: float
    intersection_fraction: float
    intersection_length_m: float
    distance_m: float
    bounds_l93: tuple[float, float, float, float]


class OracleSnapshot(Contract):
    """Computable snapshot fields; source files also retain visual-review provenance."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    parcel_id: str
    parcel_area_m2: float
    gpu_version: str
    crs: str
    sha256: dict[str, str]
    layers: dict[str, tuple[Intersection, ...]]


class Registration(Contract):
    """The source registration used for visual diagnostic crops, never expected values."""

    model_config = ConfigDict(frozen=True, extra="ignore")
    matrix: tuple[float, float, float, float, float, float]
    origin_x: float
    origin_y: float
    normalized_width: int
