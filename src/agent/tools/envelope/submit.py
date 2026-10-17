"""The ``submit_envelope`` finalizer: the architect's submission computed on the site."""

from collections.abc import Mapping

from agent.contracts.envelope import EnvelopeStudy, EnvelopeSubmission
from agent.runtime.geometry.envelope.study import EnvelopeSettings
from agent.tools.envelope.compute import GeometrySettings, read_site, site_envelope
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import Finalizer, SubmissionRejected


def envelope_finalizer(
    *, site: str, geometry: GeometrySettings, settings: EnvelopeSettings
) -> Finalizer[EnvelopeSubmission, EnvelopeStudy]:
    """Build the ``submit_envelope`` finalizer, which stores the computed ``EnvelopeStudy``.

    Args:
        site: Artifact key of the site, e.g. ``site``.
        geometry: Edge labelling knobs.
        settings: Envelope computation knobs.

    Returns:
        The finalizer, for ``submit_tool(..., finalize=...)``. It rejects the submission when no
        site has been delivered or when the envelope cannot be computed.
    """

    def finalize(
        submission: EnvelopeSubmission, artifacts: Mapping[str, ArtifactData]
    ) -> EnvelopeStudy:
        """Label the site's edges and compute the bounds and the proposal."""
        found = read_site(artifacts, site)
        try:
            computed = site_envelope(
                found,
                submission.rules,
                submission.layout,
                geometry=geometry,
                settings=settings,
                open_points=submission.open_points,
            )
        except ValueError as error:
            raise SubmissionRejected([f"(whole result): {error}"]) from error
        return computed.study

    return finalize
