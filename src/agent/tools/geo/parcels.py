from langchain_core.tools import BaseTool, tool

from agent.adapters.geo.records import SiteError
from agent.adapters.geo.survey import SiteSurveyor
from agent.adapters.http import ServiceError
from agent.tools.geo.render import description_rows, metres, parcel_rows, to_json


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

        Returns a JSON list of parcels, each with: `id` (cadastral id), `contenance_m2` (legal
        area recorded in the cadastre), `distance_m` (from the address point; 0 when the parcel
        contains it), `contains_point`, `mean_width_m` (twice the area over the perimeter: about
        a metre or less flags a thin strip, not a building plot) and `touches` (ids of the
        listed parcels adjacent to it).

        Args:
            longitude: WGS84 longitude of the address point, as returned by geocode.
            latitude: WGS84 latitude of the address point, as returned by geocode.
        """
        try:
            candidates = surveyor.candidates(longitude, latitude, radius_m)
        except ServiceError as error:
            return f"find_parcels failed: {error}"
        if not candidates:
            return (
                f"No parcel within {metres(radius_m)} m of ({longitude}, {latitude}). Check that "
                "the point comes from geocode (longitude first)."
            )
        return to_json(parcel_rows(candidates))

    return find_parcels


def describe_parcels_tool(surveyor: SiteSurveyor) -> BaseTool:
    """Build the ``describe_parcels`` tool.

    Args:
        surveyor: Site surveyor, which queries the cadastre.

    Returns:
        The tool.
    """

    @tool("describe_parcels", parse_docstring=True)
    def describe_parcels(ids: list[str], longitude: float, latitude: float) -> str:
        """Describe one parcel or a group of parcels, to judge whether they form the site.

        Returns JSON with: `parcels` (per parcel: `id`, `contenance_m2`, `mean_width_m` (about
        a metre or less flags a strip), `distance_m` from the address point, `touches`: the
        other given ids adjacent to it); `one_piece` (whether the parcels form one connected
        site; if not, `part_areas_m2` lists the separate parts). When one piece: `area_m2` of
        the union, `distance_m` from the address point to it, `edges` (per kind of land across
        the edge, `parcel` or `public_land` (no parcel number: usually a road): `count` and
        `length_m`) and `neighbours` (parcels around it, longest shared limit first: `id`,
        `contenance_m2`, `shared_length_m`, `mean_width_m`). A thin neighbour strip between
        the parcels and the street turns the street side into `parcel` edges.

        Args:
            ids: Cadastral ids from find_parcels, e.g. ["91272000CR0247"].
            longitude: WGS84 longitude of the address point, as returned by geocode.
            latitude: WGS84 latitude of the address point, as returned by geocode.
        """
        try:
            description = surveyor.describe(longitude, latitude, ids)
        except (SiteError, ServiceError) as error:
            return f"describe_parcels failed: {error}"
        return to_json(description_rows(description))

    return describe_parcels
