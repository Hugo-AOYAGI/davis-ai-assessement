from typing import Literal

from pydantic import BaseModel, Field, JsonValue, ValidationError

from agent.adapters.geo.http import CachedHttp, GeoServiceError
from agent.contracts.base import Contract
from agent.contracts.geometry import Point
from agent.observability.logs import get_logger

_LOGGER = get_logger(__name__)


class AddressCandidate(Contract):
    """One geocoder match for a free-text address."""

    label: str
    """Normalised full address, e.g. ``4 Rue Joliot-curie 91190 Gif-sur-Yvette``."""
    score: float
    """Match confidence in [0, 1]."""
    kind: str
    """Match granularity: ``housenumber``, ``street``, ``locality`` or ``municipality``."""
    longitude: float
    """WGS84 longitude of the matched point."""
    latitude: float
    """WGS84 latitude of the matched point."""
    city: str
    """Municipality name."""
    postcode: str
    """Postal code; empty when the service gives none."""
    citycode: str
    """INSEE code of the municipality, e.g. ``91272``."""
    ban_id: str
    """Base Adresse Nationale key of the match, e.g. ``91272_1599_00004``."""


class _PointGeometry(BaseModel):
    """GeoJSON point as returned by the geocoder."""

    type: Literal["Point"]
    coordinates: Point


class _Properties(BaseModel):
    """Feature properties used from the geocoder response."""

    label: str
    score: float
    type: str
    city: str
    postcode: str = ""
    citycode: str
    id: str


class _Feature(BaseModel):
    """One geocoder feature."""

    geometry: _PointGeometry
    properties: _Properties


class _Collection(BaseModel):
    """Geocoder response body."""

    features: list[_Feature] = Field(default_factory=list)


class AddressGeocoder:
    """Client of the Géoplateforme address geocoder (Base Adresse Nationale)."""

    def __init__(self, url: str, http: CachedHttp) -> None:
        """Create the client.

        Args:
            url: Search endpoint, e.g. ``https://data.geopf.fr/geocodage/search``.
            http: Cached HTTP client.
        """
        self._url = url
        self._http = http

    def search(self, query: str, limit: int) -> tuple[AddressCandidate, ...]:
        """Return the best matches for a free-text address, best first.

        Args:
            query: Address as written by the user.
            limit: Maximum number of candidates.

        Returns:
            Candidates in the service's ranking order; empty when nothing matches.

        Raises:
            GeoServiceError: If the service fails or answers an unexpected payload.
        """
        payload = self._http.get_json(self._url, {"q": query, "limit": str(limit)})
        candidates = tuple(_candidate(feature) for feature in _parse(self._url, payload).features)
        _LOGGER.debug("geocoded %r: %d candidate(s)", query, len(candidates))
        return candidates


def _parse(url: str, payload: JsonValue) -> _Collection:
    """Validate the geocoder response shape.

    Args:
        url: Service endpoint, for the error message.
        payload: Decoded response body.

    Returns:
        The parsed collection.

    Raises:
        GeoServiceError: If the payload is not a FeatureCollection of points.
    """
    try:
        return _Collection.model_validate(payload)
    except ValidationError as error:
        msg = f"{url} answered an unexpected geocoding payload: {error.errors()[:3]}"
        raise GeoServiceError(msg) from error


def _candidate(feature: _Feature) -> AddressCandidate:
    """Convert a parsed feature into a candidate.

    Args:
        feature: Parsed geocoder feature.

    Returns:
        The candidate.
    """
    props = feature.properties
    longitude, latitude = feature.geometry.coordinates
    return AddressCandidate(
        label=props.label,
        score=props.score,
        kind=props.type,
        longitude=longitude,
        latitude=latitude,
        city=props.city,
        postcode=props.postcode,
        citycode=props.citycode,
        ban_id=props.id,
    )
