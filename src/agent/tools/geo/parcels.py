from langchain_core.tools import BaseTool, tool

from agent.adapters.geo.http import GeoServiceError
from agent.adapters.geo.survey import SiteSurveyor
from agent.tools.geo.render import metres, parcel_rows, to_json


def find_parcels_tool(surveyor: SiteSurveyor, radius_m: float) -> BaseTool:
    """Build the ``find_parcels`` tool.

    Args:
        surveyor: Site surveyor, which queries the cadastre.
        radius_m: Search radius around the point, in metres.

    Returns:
        The tool.
    """

    @tool("find_parcels", parse_docstring=True)
    def find_parcels(longitude: float, latitude: float) -> str:
        """List the cadastral parcels around an address point, nearest first.

        Returns a JSON list of parcels, each with: `id` (cadastral id to pass in `parcel_ids`),
        `contenance_m2` (legal area recorded in the cadastre), `distance_m` (from the address
        point; 0 when the parcel contains it), `contains_point`, `mean_width_m` (twice the area
        over the perimeter: about a metre or less flags a thin strip, not a building plot) and
        `touches` (ids of the listed parcels adjacent to it).

        Args:
            longitude: WGS84 longitude of the address point, as returned by geocode_address.
            latitude: WGS84 latitude of the address point, as returned by geocode_address.
        """
        try:
            candidates = surveyor.candidates(longitude, latitude, radius_m)
        except GeoServiceError as error:
            return f"find_parcels failed: {error}"
        if not candidates:
            return (
                f"No parcel within {metres(radius_m)} m of ({longitude}, {latitude}). Check that "
                "the point comes from geocode_address (longitude first)."
            )
        return to_json(parcel_rows(candidates))

    return find_parcels
