import threading
from collections.abc import Sequence
from pathlib import Path

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig

PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
"""Repository root, holding ``conf/``, ``prompts/`` and ``data/``."""

_CONFIG_DIR = PROJECT_ROOT / "conf"
_CONFIG_NAME = "config"
_HYDRA_VERSION_BASE = "1.3"
_COMPOSE_LOCK = threading.Lock()


def load_config(overrides: Sequence[str] = ()) -> DictConfig:
    """Compose the Hydra config from ``conf/``; the single loader for server, CLI and evals.

    Hydra's compose API sets process-global state, so calls are serialised.

    Args:
        overrides: Hydra override strings, e.g. ``["models.nodes.orchestrator.effort=low"]``.

    Returns:
        The composed config (without the ``hydra`` node).
    """
    with (
        _COMPOSE_LOCK,
        initialize_config_dir(config_dir=str(_CONFIG_DIR), version_base=_HYDRA_VERSION_BASE),
    ):
        return compose(config_name=_CONFIG_NAME, overrides=list(overrides))


def project_path(relative: str) -> Path:
    """Resolve a path given in config relative to the project root.

    Args:
        relative: Path relative to the project root, e.g. ``prompts/orchestrator/system.md``.

    Returns:
        The absolute path.
    """
    return PROJECT_ROOT / relative


def read_prompt(relative: str) -> str:
    """Read a prompt file referenced from config.

    Args:
        relative: Path relative to the project root.

    Returns:
        The file's UTF-8 text.
    """
    return project_path(relative).read_text(encoding="utf-8")
