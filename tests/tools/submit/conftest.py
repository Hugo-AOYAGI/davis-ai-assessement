import pytest
from langchain_core.tools import BaseTool
from pydantic import JsonValue

from agent.contracts.findings.notes import DocNotes
from agent.tools.submit.factory import submit_tool


@pytest.fixture
def notes_args() -> dict[str, JsonValue]:
    return {
        "label": "oap",
        "topics": ["perimeter"],
        "notes": [
            {
                "topic": "perimeter",
                "text": "The site lies inside the Joliot Curie OAP perimeter.",
                "citations": [
                    {"doc": "oap", "page": 33, "quote": "Joliot Curie", "source_kind": "regulatory"}
                ],
            }
        ],
    }


@pytest.fixture
def bad_notes_args(notes_args: dict[str, JsonValue]) -> dict[str, JsonValue]:
    note: dict[str, JsonValue] = {
        "topic": "perimeter",
        "citations": [{"doc": "oap", "quote": "Joliot Curie", "source_kind": "regulatory"}],
    }
    return {**notes_args, "notes": [note]}


@pytest.fixture
def notes_tool() -> BaseTool:
    return submit_tool(name="submit_notes", artifact="notes.{label}", contract=DocNotes)
