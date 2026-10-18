from pathlib import Path

from agent.adapters.files import publish
from agent.contracts.inputs.georeference import PlanGeoreference


def save_georeference(georeference: PlanGeoreference, path: Path) -> None:
    """Write a plan georeference as indented JSON, atomically.

    Args:
        georeference: The fitted transform and its scores.
        path: Output file; parent directories are created.
    """
    publish(path, georeference.model_dump_json(indent=1).encode("utf-8"))


def load_georeference(path: Path) -> PlanGeoreference:
    """Read a plan georeference written by :func:`save_georeference`.

    Raises:
        FileNotFoundError: When the file does not exist (run the ingest ``georef`` step).
    """
    if not path.is_file():
        msg = (
            f"No plan georeference at {path}. "
            "Build it with `uv run python -m agent.entrypoints.ingest georef`."
        )
        raise FileNotFoundError(msg)
    return PlanGeoreference.model_validate_json(path.read_text(encoding="utf-8"))
