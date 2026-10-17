from langchain_core.tools import BaseTool, tool

from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.geo.http import GeoServiceError
from agent.tools.geo.render import address_rows, to_json


def geocode_tool(geocoder: AddressGeocoder, max_results: int) -> BaseTool:
    """Build the ``geocode_address`` tool.

    Args:
        geocoder: Address geocoder client.
        max_results: Maximum number of candidates returned to the model.

    Returns:
        The tool.
    """

    @tool("geocode_address", parse_docstring=True)
    def geocode_address(query: str) -> str:
        """Locate an address with the French national address geocoder (Base Adresse Nationale).

        Returns a JSON list of candidates, best first, each with: `label` (the normalised
        address: pass it unchanged as `address` to preview_site and submit_site), `score` (match
        confidence, 0 to 1), `kind` (`housenumber`, `street`, `locality` or `municipality`; only
        a `housenumber` match locates a plot), `longitude` and `latitude` (WGS84 address point,
        usually on the street at the entrance; pass them to find_parcels), `city`, `postcode` and
        `citycode` (INSEE code of the municipality).

        Args:
            query: The address as written in the request, e.g.
                "4 rue Joliot Curie, 91190 Gif-sur-Yvette".
        """
        try:
            candidates = geocoder.search(query, limit=max_results)
        except GeoServiceError as error:
            return f"geocode_address failed: {error}"
        if not candidates:
            return (
                f"No address matches {query!r}. Check the spelling, add the postcode and town, "
                "or report that the address cannot be located."
            )
        return to_json(address_rows(candidates))

    return geocode_address
