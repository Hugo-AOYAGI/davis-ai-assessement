from collections.abc import Mapping

from agent.adapters.geo.records import SiteError, edge_totals
from agent.adapters.geo.survey import SiteSurveyor
from agent.adapters.http import ServiceError
from agent.contracts.findings.site import ParcelChoice, Site
from agent.tools.geo.render import edge_rows, metres, to_json
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import Finalizer, SubmissionRejected


def parcel_finalizer(surveyor: SiteSurveyor) -> Finalizer[ParcelChoice, Site]:
    """Build the ``submit_parcel`` finalizer, which builds the site from the parcel choice.

    Args:
        surveyor: Site surveyor.

    Returns:
        A finalizer storing a ``Site``, or rejecting the choice with a message the model can act
        on (wrong label, unknown id, disjoint parcels, service failure).
    """

    def finalize(choice: ParcelChoice, _artifacts: Mapping[str, ArtifactData]) -> Site:
        """Build the site; turn fixable and service errors into a rejection."""
        try:
            return surveyor.site(choice)
        except SiteError as error:
            raise SubmissionRejected([str(error)]) from error
        except ServiceError as error:
            msg = f"a geographic service failed ({error}); submit the same choice again"
            raise SubmissionRejected([msg]) from error

    return finalize


def summarize_site(site: Site) -> str:
    """Summarise a stored site for the orchestrator, without coordinates.

    Args:
        site: The site built from the choice.

    Returns:
        JSON with the address, the area, the parcels, the edge totals per kind of land across
        them, and the parcels across ``parcel`` edges.
    """
    across = sorted({pid for edge in site.edges for pid in edge.neighbours})
    return to_json(
        {
            "address": site.address,
            "area_m2": metres(site.area_m2),
            "parcels": [{"id": p.id, "contenance_m2": p.area_m2} for p in site.parcels],
            "edges": edge_rows(edge_totals(site.edges)),
            "neighbours": list(across),
        }
    )
