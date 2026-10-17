import pytest
from langchain_core.tools import BaseTool
from pydantic import JsonValue

from agent.contracts.findings.oap import OAPFindings
from agent.tools.submit.factory import submit_tool


@pytest.fixture
def oap_args() -> dict[str, JsonValue]:
    return {
        "applicable": True,
        "name": "Joliot Curie",
        "rationale": "The site lies inside the OAP perimeter.",
        "citations": [
            {"doc": "oap", "page": 33, "quote": "Joliot Curie", "source_kind": "regulatory"}
        ],
    }


@pytest.fixture
def bad_oap_args(oap_args: dict[str, JsonValue]) -> dict[str, JsonValue]:
    citation = {"doc": "oap", "quote": "Joliot Curie", "source_kind": "regulatory"}
    return {**{k: v for k, v in oap_args.items() if k != "rationale"}, "citations": [citation]}


@pytest.fixture
def oap_tool() -> BaseTool:
    return submit_tool("oap_findings", OAPFindings)
