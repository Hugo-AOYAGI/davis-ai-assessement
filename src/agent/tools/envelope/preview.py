"""The ``preview_envelope`` tool: the architect tries rules and a layout before submitting."""

from collections.abc import Sequence

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import JsonValue, ValidationError

from agent.adapters.geo.imagery import ImageryClient, blank_image, draw_outlines
from agent.adapters.http import ServiceError
from agent.adapters.images.store import ImageStore
from agent.contracts.envelope import EnvelopeDraft
from agent.runtime.geometry.envelope.study import EnvelopeSettings
from agent.runtime.geometry.envelope.summary import describe_envelope
from agent.tools.envelope.compute import GeometrySettings, read_site, site_envelope
from agent.tools.envelope.plan import (
    PlanSettings,
    describe_limits,
    plan_bounds,
    plan_caption,
    plan_outlines,
)
from agent.tools.images.blocks import ContentBlock, image_block, text_block
from agent.tools.submit.artifacts import ArtifactsState
from agent.tools.submit.factory import SubmissionRejected

NAME = "preview_envelope"
DESCRIPTION = """Try your envelope rules and layout on the site, without delivering anything.

Pass `rules` and `layout` exactly as you would pass them to submit_envelope. Code labels the
site's limits road / side / rear and computes the two bounds (`largest`, `windows`) and your
proposal. The reply gives the site's limits by kind; for each bound and for the proposal, the
ground footprint after setbacks and, per building, its ground area, height and volume; whether
the buildings fit with the required spacing; the warnings and the assumptions. Then a plan of the
proposal, north up, over the map of the site: the limits coloured by kind, the setback strip,
each building's ground part filled and labelled with its name and height, and the gap between
buildings measured. Look at the plan and the figures, adjust the layout and preview again; only
submit_envelope delivers. Invalid arguments come back as `field.path: message` lines: fix them
and call again."""


def preview_envelope_tool(
    *,
    site: str,
    geometry: GeometrySettings,
    settings: EnvelopeSettings,
    imagery: ImageryClient,
    plan: PlanSettings,
    store: ImageStore,
) -> BaseTool:
    """Build the ``preview_envelope`` tool: the envelope computed and drawn, nothing stored.

    Args:
        site: Artifact key of the site, e.g. ``site``.
        geometry: Edge labelling knobs, as the gate's.
        settings: Envelope computation knobs, as the gate's.
        imagery: WMS client of the map drawn under the plan.
        plan: Framing and colours of the plan.
        store: Where preview images are stored.

    Returns:
        The tool, whose argument schema is ``EnvelopeDraft``.

    Raises:
        ValueError: If the imagery has no layer for the plan's kind.
    """
    if plan.kind not in imagery.layers:
        msg = f"{NAME}: imagery has no layer for kind {plan.kind!r}"
        raise ValueError(msg)

    def preview(
        runtime: ToolRuntime[None, ArtifactsState], **arguments: JsonValue
    ) -> list[ContentBlock]:
        """Compute the envelope of the draft and draw the proposal."""
        try:
            draft = EnvelopeDraft.model_validate(arguments)
            found = read_site(runtime.state.get("artifacts"), site)
            computed = site_envelope(
                found, draft.rules, draft.layout, geometry=geometry, settings=settings
            )
        except ValidationError as error:
            raise _rejected(_validation_lines(error)) from error
        except SubmissionRejected as rejection:
            raise _rejected(rejection.errors) from rejection
        except ValueError as error:
            raise _rejected([f"(whole result): {error}"]) from error
        bounds = plan_bounds(found.polygon, plan)
        size = (plan.image_px, plan.image_px)
        try:
            image, failure = imagery.get_map(plan.kind, bounds, size), None
        except ServiceError as error:
            image, failure = blank_image(size), str(error)
        png = draw_outlines(image, plan_outlines(computed, found.polygon, bounds, plan), plan.style)
        summary = f"{describe_limits(computed.boundaries)}\n\n{describe_envelope(computed.study)}"
        return [
            text_block(f"Preview only, nothing was stored.\n\n{summary}"),
            text_block(plan_caption(bounds, plan, failure)),
            image_block(store, png),
        ]

    return StructuredTool(
        name=NAME,
        description=DESCRIPTION,
        args_schema=EnvelopeDraft.model_json_schema(),
        func=preview,
        handle_tool_error=True,
    )


def _validation_lines(error: ValidationError) -> list[str]:
    """Render pydantic errors as ``field.path: message`` lines, as the submit tools do."""
    return [
        f"{'.'.join(str(part) for part in detail['loc']) or '(whole result)'}: {detail['msg']}"
        for detail in error.errors(include_url=False)
    ]


def _rejected(errors: Sequence[str]) -> ToolException:
    """Build the error the model reads when the draft cannot be previewed."""
    lines = "\n".join(f"- {line}" for line in errors)
    return ToolException(f"{NAME} rejected. Fix these errors and preview again:\n{lines}")
