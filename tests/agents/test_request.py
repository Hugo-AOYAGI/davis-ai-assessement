import pytest

from agent.agents.config import read_prompt
from agent.agents.request import case_request
from agent.contracts.inputs.case import Case

TEMPLATE = "Address: $address\nProgram: $program\nFacts:\n$facts"


def make_case(facts=()):
    return Case(address="1 rue X", program="Two buildings", corpus_id="c@1", facts=facts)


def test_facts_one_line_each():
    message = case_request(make_case(("RSE: 120 rooms", "RJA: 80 units")), TEMPLATE, no_facts="-")
    assert message == (
        "Address: 1 rue X\nProgram: Two buildings\nFacts:\n- RSE: 120 rooms\n- RJA: 80 units"
    )


def test_no_facts_text():
    message = case_request(make_case(), TEMPLATE, no_facts="- none given")
    assert message.endswith("Facts:\n- none given")


def test_unknown_placeholder_rejected():
    with pytest.raises(KeyError):
        case_request(make_case(), "$address $unknown", no_facts="-")


def test_project_template_renders():
    message = case_request(
        make_case(), read_prompt("prompts/orchestrator/request.md"), no_facts="- none given"
    )
    assert "1 rue X" in message
    assert "Two buildings" in message
    assert "$" not in message
