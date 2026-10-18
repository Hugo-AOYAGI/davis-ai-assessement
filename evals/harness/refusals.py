"""Expected clean refusals for surveyor inputs that cannot identify a site."""

import json
import re
from collections.abc import Sequence
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from pydantic import Field, field_validator

from agent.contracts.base import Contract


class ExpectedRefusal(Contract):
    """A source-checked negative case, with an explicit explanation and lookup trace."""

    reason_pattern: str = Field(min_length=1)
    """Regular expression matched against the final assistant explanation."""
    required_tools: tuple[Literal["geocode"], ...] = Field(default=("geocode",), min_length=1)
    """Lookups that must have completed successfully before the refusal."""

    @field_validator("reason_pattern")
    @classmethod
    def _valid_pattern(cls, value: str) -> str:
        """Reject malformed patterns before a paid experiment starts."""
        try:
            re.compile(value)
        except re.error as error:
            raise ValueError(str(error)) from error
        return value


def refusal_checks(
    expected: ExpectedRefusal,
    messages: Sequence[BaseMessage],
    *,
    has_output: bool,
    error: str | None,
) -> dict[str, bool]:
    """Require a clean, explained refusal after real lookups, never a crash or silence."""
    calls = {
        call["id"]: call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    replies = {
        calls.get(message.tool_call_id): message
        for message in messages
        if isinstance(message, ToolMessage)
    }
    completed = {
        name
        for name, message in replies.items()
        if message.status != "error" and _geocode_reply(message.text)
    }
    final = messages[-1] if messages else None
    explained = (
        isinstance(final, AIMessage)
        and not final.tool_calls
        and re.search(expected.reason_pattern, final.text) is not None
    )
    return {
        "no_artifact": not has_output,
        "no_runtime_error": error is None,
        "lookups_completed": set(expected.required_tools) <= completed,
        "no_parcel_submission": not any(
            name in {"submit_parcel", "revise_parcel"} for name in calls.values()
        ),
        "explained": explained,
    }


def _geocode_reply(text: str) -> bool:
    """Recognise completed geocoder replies, excluding service failures returned as text."""
    if text.startswith("No address matches "):
        return True
    try:
        candidates = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(candidates, list) and all(
        isinstance(candidate, dict)
        and {"label", "kind", "longitude", "latitude"} <= candidate.keys()
        for candidate in candidates
    )
