from collections.abc import Mapping, Sequence

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field

from agent.adapters.geo.http import GeoServiceError
from agent.adapters.geo.records import SiteError
from agent.adapters.geo.survey import SiteSurveyor
from agent.contracts.base import Contract
from agent.contracts.findings.site import SiteContext
from agent.tools.geo.render import site_summary, to_json
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import Finalizer, SubmissionRejected

_PREVIEW_DESCRIPTION = """\
Compute the site formed by some parcels, without submitting it, to check your choice.

Returns JSON with: `area_m2` (area of the union of the parcels), `parcels` (id and \
contenance_m2), `boundaries` (for each type `road`, `side` and `rear`: total `length_m` and \
number of `edges`), `nearest_boundary` (type and `distance_m` of the site limit closest to the \
address point; the point lies on the addressed street, so this should be `road`), and \
`neighbours` (adjacent parcels, longest shared limit first: `id`, `contenance_m2`, \
`shared_length_m` along the site, `mean_width_m` (about a metre or less flags a strip) and \
`public` (declared public space)). A limit shared with a non-public neighbour is separating \
(`side` if it meets a road limit, `rear` otherwise); every other limit faces the road. If the \
selection is invalid, the reply says what to fix."""


class ParcelSelection(Contract):
    """Parcels proposed as the site, with the neighbouring parcels declared public space."""

    address: str = Field(min_length=1)
    """The address label exactly as geocode_address returned it."""
    parcel_ids: tuple[str, ...] = Field(min_length=1)
    """Cadastral ids of the parcels forming the site, as returned by find_parcels
    (14 characters, e.g. `91272000CR0247`)."""
    public_parcel_ids: tuple[str, ...] = ()
    """Neighbouring parcels to treat as public space, typically a thin strip or a path between
    the plot and the street: the site's limits along them become road limits. Each must be a
    neighbour of the site and must not be in `parcel_ids`."""


class SiteSelection(ParcelSelection):
    """The site under study, identified by its address and cadastral parcels.

    Geometry, areas, boundary types and source citations are computed from them.
    """

    method: str = Field(min_length=1)
    """One or two sentences on how the site was identified: geocoding, parcel search,
    selection criterion, boundary typing."""
    assumptions: tuple[str, ...] = ()
    """Every choice a reviewer could dispute, one sentence each: the parcel choice and the
    candidates set aside, each parcel declared public space and why, and that boundaries are
    typed from the cadastre alone."""


def site_finalizer(surveyor: SiteSurveyor) -> Finalizer[SiteSelection]:
    """Build the ``submit_site`` finalizer, which computes the site from the selection.

    Args:
        surveyor: Site surveyor.

    Returns:
        A finalizer storing a ``SiteContext``, or rejecting the selection with the surveyor's
        message.
    """

    def finalize(selection: SiteSelection, _artifacts: Mapping[str, ArtifactData]) -> SiteContext:
        """Compute the site; turn fixable and service errors into a rejection."""
        try:
            draft = surveyor.draft(
                selection.address, selection.parcel_ids, selection.public_parcel_ids
            )
        except (SiteError, GeoServiceError) as error:
            raise SubmissionRejected([str(error)]) from error
        return SiteContext(
            address=draft.address.label,
            longitude=draft.address.longitude,
            latitude=draft.address.latitude,
            parcels=draft.parcels,
            polygon=draft.polygon,
            area_m2=draft.area_m2,
            boundaries=draft.boundaries,
            method=selection.method,
            assumptions=selection.assumptions,
            citations=draft.citations,
        )

    return finalize


def preview_site_tool(surveyor: SiteSurveyor) -> BaseTool:
    """Build the ``preview_site`` tool.

    Args:
        surveyor: Site surveyor.

    Returns:
        The tool, whose arguments are those of ``ParcelSelection``.
    """

    def preview_site(
        address: str, parcel_ids: Sequence[str], public_parcel_ids: Sequence[str] = ()
    ) -> str:
        """Compute the site and summarise it, or explain why it cannot be computed."""
        try:
            draft = surveyor.draft(address, parcel_ids, public_parcel_ids)
        except (SiteError, GeoServiceError) as error:
            return f"preview_site failed: {error}"
        return to_json(site_summary(draft))

    return StructuredTool.from_function(
        func=preview_site,
        name="preview_site",
        description=_PREVIEW_DESCRIPTION,
        args_schema=ParcelSelection,
    )
