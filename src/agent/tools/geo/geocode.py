from langchain_core.tools import BaseTool, tool

from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.http import ServiceError
from agent.tools.geo.render import address_rows, to_json


def geocode_tool(geocoder: AddressGeocoder, max_results: int) -> BaseTool:
    """Build the ``geocode`` tool.

    Args:
        geocoder: Address geocoder client.
        max_results: Maximum number of candidates returned to the model.

    Returns:
        The tool.
    """

    @tool("geocode", parse_docstring=True)
    def geocode(query: str) -> str:
        """Locate an address with the French national address geocoder (Base Adresse Nationale).

        Returns a JSON list of candidates, best first, each with: `label` (the normalised
        address: pass it unchanged as `address` to submit_parcel), `score` (match confidence,
        0 to 1), `kind` (`housenumber`, `street`, `locality` or `municipality`; only a
        `housenumber` match locates a plot), `longitude` and `latitude` (WGS84 address point,
        usually on the street at the entrance, not inside a parcel; pass them to find_parcels
        and describe_parcels), `city`, `postcode` and `citycode` (INSEE code of the
        municipality).

        Args:
            query: The address as written in the request, e.g.
                "4 rue Joliot Curie, 91190 Gif-sur-Yvette".
        """
        try:
            candidates = geocoder.search(query, limit=max_results)
        except ServiceError as error:
            return f"geocode failed: {error}"
        if not candidates:
            return (
                f"No address matches {query!r}. Check the spelling, add the postcode and town, "
                "or report that the address cannot be located."
            )
        return to_json(address_rows(candidates))

    return geocode
