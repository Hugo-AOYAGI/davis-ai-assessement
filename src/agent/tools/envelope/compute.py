"""From the ``site`` artifact to the envelope: one path for the preview, the submit and the gate."""

from collections.abc import Mapping, Sequence
from typing import NamedTuple

from pydantic import NonNegativeFloat

from agent.contracts.base import Contract
from agent.contracts.envelope import EnvelopeRules, EnvelopeStudy, Layout
from agent.contracts.findings.notes import OpenPoint
from agent.contracts.findings.site import Site
from agent.contracts.geometry import Boundary
from agent.runtime.geometry.edges import label_edges
from agent.runtime.geometry.envelope.study import EnvelopeSettings, compute_envelope_study
from agent.tools.submit.artifacts import ArtifactData, read_artifact
from agent.tools.submit.factory import SubmissionRejected


class GeometrySettings(Contract):
    """Knobs of the edge labelling."""

    snap_tolerance_m: NonNegativeFloat
    """Edges shorter than this never split a limit."""
    collinear_angle_deg: NonNegativeFloat
    """Largest direction change between parcel edges of one limit."""


class SiteEnvelope(NamedTuple):
    """The site's labelled edges and the envelope computed on them."""

    boundaries: tuple[Boundary, ...]
    study: EnvelopeStudy


def site_envelope(  # noqa: PLR0913 - the architect's submission, plus the knobs
    site: Site,
    rules: EnvelopeRules,
    layout: Layout,
    *,
    geometry: GeometrySettings,
    settings: EnvelopeSettings,
    open_points: Sequence[OpenPoint] = (),
) -> SiteEnvelope:
    """Label the site's edges road / side / rear and compute the envelope on them.

    ``preview_envelope``, ``submit_envelope`` and ``submit_study`` all go through here, so the
    figures the architect sees are the ones the gate recomputes.

    Args:
        site: The surveyed site.
        rules: The envelope rules.
        layout: The layout of the buildings; it must agree with ``rules`` (``layout_errors``).
        geometry: Edge labelling knobs.
        settings: Envelope computation knobs.
        open_points: The architect's open points, stored as they are.

    Returns:
        The labelled edges and the envelope study.

    Raises:
        ValueError: If a building of the layout has no maximum height in the rules.
    """
    boundaries = label_edges(
        site.edges,
        snap_tolerance_m=geometry.snap_tolerance_m,
        collinear_angle_deg=geometry.collinear_angle_deg,
    )
    study = compute_envelope_study(
        site.polygon, boundaries, rules, layout, settings=settings, open_points=open_points
    )
    return SiteEnvelope(boundaries, study)


def read_site(artifacts: Mapping[str, ArtifactData] | None, key: str) -> Site:
    """Read the site the envelope is computed on.

    Args:
        artifacts: The ``artifacts`` value of the graph state.
        key: Artifact key of the site, e.g. ``site``.

    Returns:
        The site.

    Raises:
        SubmissionRejected: If no site has been delivered.
    """
    site = read_artifact(artifacts, key, Site)
    if site is None:
        raise SubmissionRejected(
            [
                f"no `{key}` artifact in state: the site must be surveyed before the envelope. "
                "Reply that the site is missing and stop."
            ]
        )
    return site
