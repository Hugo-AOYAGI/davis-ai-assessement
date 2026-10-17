import json
from typing import Annotated

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool, ToolException

from agent.tools.submit.artifacts import ArtifactsState

DESCRIPTION = """Read an artifact delivered by a sub-agent (or by submit_study), as JSON.

A sub-agent's reply to `task` is only a summary. Its artifact holds the full typed findings,
with citations that were already verified against the documents: read it before using the
findings, and reuse those citations verbatim in the study rather than retyping them.

The artifact name is the one in the sub-agent's submit tool: `submit_site` stores `site`,
`submit_regulation_findings` stores `regulation_findings`, and so on. An unknown name returns
the list of artifacts delivered so far."""


def read_artifact_tool() -> BaseTool:
    """Build the ``read_artifact`` tool, which returns one artifact of the state as JSON.

    Returns:
        A tool replying with the artifact's JSON, or with the names of the available artifacts.
    """

    def read(
        name: Annotated[str, "Artifact name, e.g. `site` or `regulation_findings`."],
        runtime: ToolRuntime[None, ArtifactsState],
    ) -> str:
        """Return the artifact stored under ``name``."""
        artifacts = runtime.state.get("artifacts") or {}
        if name not in artifacts:
            available = ", ".join(sorted(artifacts))
            listing = (
                f"Available artifacts: {available}."
                if available
                else "No artifact has been delivered yet: delegate to a sub-agent first."
            )
            msg = f"No artifact named {name!r}. {listing}"
            raise ToolException(msg)
        return json.dumps(artifacts[name], ensure_ascii=False)

    return StructuredTool.from_function(
        func=read,
        name="read_artifact",
        description=DESCRIPTION,
        handle_tool_error=True,
    )
