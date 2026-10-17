import json

import pytest

from agent.contracts.inputs.clarification import Answer, ClarificationReply, ClarificationRequest
from agent.tools.interaction.exchange import (
    describe_reply,
    interrupt_payload,
    read_reply,
)

REQUEST = ClarificationRequest.model_validate(
    {
        "questions": [
            {
                "id": "units",
                "text": "How many housing units?",
                "kind": "program_fact",
                "why": "Parking depends on it.",
            },
            {
                "id": "use",
                "text": "Is the residence housing or a public-interest facility?",
                "kind": "interpretation",
                "why": "It decides which rules apply.",
                "options": ["housing", "facility"],
                "recommended": "housing",
            },
        ]
    }
)


def reply(**answers):
    return ClarificationReply(
        answers=tuple(Answer(question_id=qid, text=text) for qid, text in answers.items())
    )


def test_payload_is_hitl_request_plus_contract():
    payload = interrupt_payload(REQUEST)
    assert json.loads(json.dumps(payload)) == payload
    [action] = payload["action_requests"]
    assert action["name"] == "ask_user"
    assert action["args"] == {"units": "", "use": "housing"}
    assert payload["review_configs"] == [
        {"action_name": "ask_user", "allowed_decisions": ["approve", "edit", "reject"]}
    ]
    assert ClarificationRequest.model_validate(payload["clarification"]) == REQUEST


def test_payload_description_lists_questions():
    description = interrupt_payload(REQUEST)["action_requests"][0]["description"]
    assert "**units** (program fact): How many housing units?" in description
    assert "Why: It decides which rules apply." in description
    assert "Options: housing / facility" in description
    assert "Recommended: housing" in description


@pytest.mark.parametrize(
    ("resume", "expected"),
    [
        ({"answers": [{"question_id": "units", "text": "40"}]}, reply(units="40")),
        ({"decisions": [{"type": "approve"}]}, reply(use="housing")),
        (
            {
                "decisions": [
                    {
                        "type": "edit",
                        "edited_action": {"name": "ask_user", "args": {"units": 40, "use": " "}},
                    }
                ]
            },
            reply(units="40"),
        ),
        (
            {"decisions": [{"type": "reject", "message": " 40 units, housing "}]},
            "40 units, housing",
        ),
        ({"decisions": [{"type": "respond", "message": "40"}]}, "40"),
        ({"decisions": [{"type": "reject"}]}, reply()),
        ("  40 units  ", "40 units"),
        ("", reply()),
    ],
)
def test_read_reply_accepted_shapes(resume, expected):
    assert read_reply(REQUEST, resume) == expected


@pytest.mark.parametrize(
    "resume",
    [
        None,
        42,
        {"answers": [{"question_id": "units"}]},
        {"decisions": []},
        {"decisions": [{"type": "maybe"}]},
        {"decisions": [{"type": "edit", "edited_action": {"args": "40"}}]},
        {"other": 1},
    ],
)
def test_read_reply_unreadable(resume):
    assert read_reply(REQUEST, resume) is None


def test_describe_answers_and_unanswered():
    text = describe_reply(REQUEST, reply(use="facility"))
    assert "The user answered:\n- use: facility" in text
    assert "resolved_by: user" in text
    assert "Left unanswered by the user: units." in text
    assert "resolved_by: agent" in text


def test_describe_all_answered():
    text = describe_reply(REQUEST, reply(units="40", use="housing"))
    assert "- units: 40\n- use: housing" in text
    assert "unanswered" not in text


def test_describe_free_text():
    text = describe_reply(REQUEST, "40 units, housing")
    assert "free text" in text
    assert "40 units, housing" in text
    assert "resolved_by: user" in text


def test_describe_unreadable():
    text = describe_reply(REQUEST, None)
    assert "could not be read" in text
    assert "resolved_by: agent" in text
