from collections.abc import Mapping

from agent.adapters.images.pages import PageImages, RegionError
from agent.contracts.findings.zone import ZoneFindings
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import Finalizer, SubmissionRejected


def zone_finalizer(*, images: PageImages) -> Finalizer[ZoneFindings, ZoneFindings]:
    """Build the ``submit_zone`` finalizer: the submitted region must lie on its page.

    Args:
        images: The page images the region is checked against.

    Returns:
        The finalizer, for ``submit_tool(..., finalize=...)``; it stores the submission
        unchanged.
    """

    def finalize(submission: ZoneFindings, _artifacts: Mapping[str, ArtifactData]) -> ZoneFindings:
        """Refuse a region that is not on an existing page overview."""
        try:
            images.check(submission.region)
        except RegionError as error:
            raise SubmissionRejected([f"region: {error}"]) from error
        return submission

    return finalize
