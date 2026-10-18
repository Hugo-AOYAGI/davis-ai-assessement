from pydantic import BaseModel, JsonValue, ValidationError
from shapely.geometry import Polygon, shape

from agent.adapters.http import CachedHttp, ServiceError
from agent.runtime.geometry.projection import to_crs


class _Feature(BaseModel):
    """GeoJSON feature; its geometry is checked by shapely."""

    geometry: dict[str, JsonValue]


class _Collection(BaseModel):
    """API Carto response."""

    features: list[_Feature]


class CommuneBoundaryClient:
    """Commune outline from the API Carto cadastre module (IGN), commune endpoint.

    The cadastral commune outline is the one parcels are drawn against, so it matches plans
    produced over the cadastre better than generalised administrative outlines.
    """

    def __init__(
        self, url: str, http: CachedHttp, *, crs: str, geographic_crs: str, source: str
    ) -> None:
        """Create the client.

        Args:
            url: Commune endpoint, e.g. ``https://apicarto.ign.fr/api/cadastre/commune``.
            http: Cached HTTP client.
            crs: Metric CRS of the returned polygon, e.g. ``EPSG:2154``.
            geographic_crs: CRS of the service's coordinates (``EPSG:4326``).
            source: Short service name recorded with results.
        """
        self._url = url
        self._http = http
        self._crs = crs
        self._geographic_crs = geographic_crs
        self.source = source

    def outline(self, insee: str) -> Polygon:
        """Return the largest part of a commune's outline, in the metric CRS.

        Args:
            insee: Five-character INSEE commune code, e.g. ``91272``.

        Returns:
            The outline polygon (holes kept).

        Raises:
            ServiceError: If the service fails or answers no usable polygon.
        """
        payload = self._http.get_json(self._url, {"code_insee": insee})
        try:
            features = _Collection.model_validate(payload).features
        except ValidationError as error:
            msg = f"{self._url} answered an unexpected commune payload: {error.errors()[:3]}"
            raise ServiceError(msg) from error
        parts = [part for feature in features for part in _polygons(shape(feature.geometry))]
        if not parts:
            msg = f"{self._url} returned no polygon for commune {insee}"
            raise ServiceError(msg)
        largest = max(parts, key=lambda part: part.area)
        return to_crs(largest, self._geographic_crs, self._crs)


def _polygons(geometry: object) -> list[Polygon]:
    """Polygons of a Polygon or MultiPolygon geometry; nothing for other types."""
    if isinstance(geometry, Polygon):
        return [geometry]
    parts = getattr(geometry, "geoms", ())
    return [part for part in parts if isinstance(part, Polygon)]
