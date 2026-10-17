import json
from typing import Annotated, Literal

from pydantic import BaseModel, Field, JsonValue, ValidationError
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from agent.adapters.http import CachedHttp, ServiceError
from agent.contracts.base import Contract
from agent.contracts.geometry import Point
from agent.observability.logs import get_logger

_LOGGER = get_logger(__name__)
_IDU_LENGTH = 14

type Rings = tuple[tuple[Point, ...], ...]


class CadastralParcel(Contract):
    """One parcel of the French cadastre (PCI, IGN), in WGS84 longitude/latitude."""

    id: str
    """Parcel identifier (``idu``): INSEE 5 + prefix 3 + section 2 + number 4, e.g.
    ``91272000CR0247``."""
    contenance_m2: float | None
    """Legal area recorded in the cadastre, in square metres, when known."""
    polygons: tuple[Rings, ...]
    """MultiPolygon coordinates: polygons, each an exterior ring then holes, rings closed."""


class _PolygonGeometry(BaseModel):
    """GeoJSON Polygon."""

    type: Literal["Polygon"]
    coordinates: Rings


class _MultiPolygonGeometry(BaseModel):
    """GeoJSON MultiPolygon."""

    type: Literal["MultiPolygon"]
    coordinates: tuple[Rings, ...]


class _Properties(BaseModel):
    """Parcel attributes used from API Carto."""

    idu: str
    contenance: float | None = None


class _Feature(BaseModel):
    """One parcel feature."""

    geometry: Annotated[_PolygonGeometry | _MultiPolygonGeometry, Field(discriminator="type")]
    properties: _Properties


class _Collection(BaseModel):
    """API Carto response page."""

    features: list[_Feature]
    number_matched: int | None = Field(default=None, alias="numberMatched")


class CadastreClient:
    """Client of the API Carto cadastre module (IGN), parcel endpoint."""

    def __init__(self, url: str, http: CachedHttp, page_size: int) -> None:
        """Create the client.

        Args:
            url: Parcel endpoint, e.g. ``https://apicarto.ign.fr/api/cadastre/parcelle``.
            http: Cached HTTP client.
            page_size: Features requested per page (``_limit``).
        """
        self._url = url
        self._http = http
        self._page_size = page_size

    def intersecting(self, geometry: BaseGeometry) -> tuple[CadastralParcel, ...]:
        """Return every parcel intersecting a geometry, following pagination.

        Args:
            geometry: Query geometry in WGS84 longitude/latitude.

        Returns:
            The parcels, in the service's order.

        Raises:
            ServiceError: If the service fails or answers an unexpected payload.
        """
        geom = json.dumps(mapping(geometry), separators=(",", ":"))
        features: list[_Feature] = []
        while True:
            params = {"geom": geom, "_limit": str(self._page_size), "_start": str(len(features))}
            page = _parse(self._url, self._http.get_json(self._url, params))
            features.extend(page.features)
            if not _has_more(page, len(features), self._page_size):
                break
        _LOGGER.debug("%d parcel(s) intersect the query geometry", len(features))
        return tuple(_parcel(feature) for feature in features)

    def by_id(self, parcel_id: str) -> CadastralParcel | None:
        """Return the parcel with a given identifier.

        Args:
            parcel_id: 14-character ``idu``, e.g. ``91272000CR0247`` (one-letter sections
                are zero-padded, e.g. ``0C``).

        Returns:
            The parcel, or ``None`` when the cadastre has no such parcel.

        Raises:
            ValueError: If ``parcel_id`` is not 14 characters long.
            ServiceError: If the service fails or answers an unexpected payload.
        """
        if len(parcel_id) != _IDU_LENGTH:
            msg = (
                f"parcel id {parcel_id!r} must be 14 characters: INSEE code (5), prefix (3), "
                "section (2, zero-padded) and number (4, zero-padded), e.g. 91272000CR0247"
            )
            raise ValueError(msg)
        params = {
            "code_insee": parcel_id[:5],
            "com_abs": parcel_id[5:8],
            "section": parcel_id[8:10],
            "numero": parcel_id[10:],
        }
        page = _parse(self._url, self._http.get_json(self._url, params))
        matches = [_parcel(f) for f in page.features if f.properties.idu == parcel_id]
        return matches[0] if matches else None


def _has_more(page: _Collection, fetched: int, page_size: int) -> bool:
    """Tell whether another page must be requested.

    Args:
        page: Last page received.
        fetched: Features received so far, all pages included.
        page_size: Requested page size.

    Returns:
        ``True`` when the service reports more matches than received.
    """
    if not page.features:
        return False
    if page.number_matched is None:
        if len(page.features) >= page_size:
            _LOGGER.warning("cadastre page full without numberMatched: results may be truncated")
        return False
    return fetched < page.number_matched


def _parse(url: str, payload: JsonValue) -> _Collection:
    """Validate an API Carto response page.

    Args:
        url: Service endpoint, for the error message.
        payload: Decoded response body.

    Returns:
        The parsed page.

    Raises:
        ServiceError: If the payload is not a FeatureCollection of (multi)polygons.
    """
    try:
        return _Collection.model_validate(payload)
    except ValidationError as error:
        msg = f"{url} answered an unexpected cadastre payload: {error.errors()[:3]}"
        raise ServiceError(msg) from error


def _parcel(feature: _Feature) -> CadastralParcel:
    """Convert a parsed feature into a parcel, normalising Polygon to MultiPolygon.

    Args:
        feature: Parsed parcel feature.

    Returns:
        The parcel.
    """
    geometry = feature.geometry
    polygons = (
        (geometry.coordinates,) if isinstance(geometry, _PolygonGeometry) else geometry.coordinates
    )
    return CadastralParcel(
        id=feature.properties.idu,
        contenance_m2=feature.properties.contenance,
        polygons=polygons,
    )
