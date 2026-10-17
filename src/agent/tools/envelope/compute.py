from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import JsonValue, ValidationError

from agent.contracts.findings.site import SiteContext
from agent.contracts.geometry import EnvelopeParameters
from agent.runtime.geometry.envelope import compute_envelope
from agent.tools.submit.artifacts import ArtifactsState, read_artifact

DESCRIPTION = """Preview the building envelope from the envelope parameters, before submitting.

Computes a prism envelope: the site polygon minus the setbacks (each site limit is set back by
the road, side or rear distance matching its type), the maximum footprint (the setback area,
capped by the footprint ratio times the site area), the minimum green area (green ratio times the
site area), and the maximum volume (maximum footprint times maximum height). A limit with a null
value is treated as absent and listed in `assumptions`, as are footprint parts left out and a
green requirement that further limits the footprint.

Pass the envelope parameters as top-level arguments, exactly as you would put them in the study.
The site is read from the state: it must have been delivered by site_locator (submit_site). The
tool stores nothing; submit_study recomputes the envelope itself from the parameters you submit.
Use the result to check that the parameters give a plausible envelope."""


def compute_envelope_tool(site_artifact: str, quad_segs: int, min_area_m2: float) -> BaseTool:
    """Build the ``compute_envelope`` tool, which previews the envelope of the site in state.

    Args:
        site_artifact: Artifact key holding the ``SiteContext``.
        quad_segs: Segments per quarter circle in the round setback buffers.
        min_area_m2: Footprint parts smaller than this are discarded as slivers.

    Returns:
        A tool replying with the ``Envelope`` as JSON, or with an error the model can act on.
    """

    def compute(runtime: ToolRuntime[None, ArtifactsState], **arguments: JsonValue) -> str:
        """Validate the parameters and compute the envelope of the site in state."""
        try:
            parameters = EnvelopeParameters.model_validate(arguments)
        except ValidationError as error:
            lines = "\n".join(f"- {line}" for line in _format_validation(error))
            msg = f"Invalid envelope parameters. Fix these errors and call again:\n{lines}"
            raise ToolException(msg) from error
        site = read_artifact(runtime.state.get("artifacts"), site_artifact, SiteContext)
        if site is None:
            msg = (
                "No site in state. Delegate to site_locator first: it must deliver the site "
                "with submit_site before the envelope can be computed."
            )
            raise ToolException(msg)
        envelope = compute_envelope(site, parameters, quad_segs=quad_segs, min_area_m2=min_area_m2)
        return envelope.model_dump_json()

    return StructuredTool(
        name="compute_envelope",
        description=DESCRIPTION,
        args_schema=EnvelopeParameters.model_json_schema(),
        func=compute,
        handle_tool_error=True,
    )


def _format_validation(error: ValidationError) -> list[str]:
    """Render pydantic errors as ``field.path: message`` lines."""
    return [
        f"{'.'.join(str(part) for part in detail['loc']) or '(all parameters)'}: {detail['msg']}"
        for detail in error.errors(include_url=False)
    ]
