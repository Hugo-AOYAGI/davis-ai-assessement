import json
from pathlib import Path

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from omegaconf import DictConfig, OmegaConf
from pydantic import JsonValue

from agent.agents.config import load_config
from agent.agents.subagents import build_tools
from agent.contracts.findings.site import SiteContext
from agent.tools.submit.artifacts import Artifacts

SITE_JSON = Path(__file__).parent / "fixtures" / "site.json"


@pytest.fixture(scope="session")
def map_cfg() -> DictConfig:
    return load_config(["subagents=[zoning_map_reader]"])


@pytest.fixture(scope="session")
def plan_block(map_cfg) -> dict[str, JsonValue]:
    block = OmegaConf.to_container(map_cfg.corpus.zoning_map, resolve=True)
    assert isinstance(block, dict)
    return {str(key): value for key, value in block.items()}


@pytest.fixture(scope="session")
def map_tools(map_cfg) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in build_tools(map_cfg.subagents.zoning_map_reader.tools)}


@pytest.fixture(scope="session")
def site_data():
    return json.loads(SITE_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def site(site_data) -> SiteContext:
    return SiteContext.model_validate(site_data)


def call_tool(
    tool: BaseTool, args: dict[str, JsonValue], artifacts: Artifacts | None
) -> ToolMessage:
    state = {"messages": [], **({"artifacts": artifacts} if artifacts is not None else {})}
    runtime = ToolRuntime(
        state=state,
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="1",
        store=None,
    )
    result = tool.invoke(
        {"type": "tool_call", "id": "1", "name": tool.name, "args": {**args, "runtime": runtime}}
    )
    assert isinstance(result, ToolMessage)
    return result


@pytest.fixture
def invoke():
    return call_tool
