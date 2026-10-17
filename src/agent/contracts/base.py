from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    """Base for every schema crossing a module boundary: immutable, no unknown keys.

    Field docstrings become JSON-schema descriptions. When a contract is the argument of a
    ``submit_<artifact>`` tool, those descriptions are what the model reads, so write them for it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)
