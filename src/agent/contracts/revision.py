from pydantic import Field, JsonValue

from agent.contracts.base import Contract


class Edit(Contract):
    """One change to a rejected submission: set a value at a path, or remove it."""

    path: str = Field(min_length=1)
    """Dotted path in the rejected draft, as listed in the rejection reply: field names and
    0-based list indices, e.g. `notes.1.citations.3.quote`."""
    value: JsonValue = None
    """New value at the path (any JSON). It replaces the current value, adds a missing field, or
    appends when the index is the list's length. Omit it when removing."""
    remove: bool = False
    """True to delete the field or list item at the path."""

    @property
    def sets(self) -> bool:
        """Whether the edit carries a value (``null`` included) rather than only a removal."""
        return "value" in self.model_fields_set and not (self.remove and self.value is None)


class Revision(Contract):
    """Corrections to a rejected submission, sent instead of the complete result."""

    edits: tuple[Edit, ...]
    """The changes; every path refers to the draft as rejected, not as shifted by other edits.
    Empty to check the draft again unchanged, once what it lacked was delivered elsewhere."""
