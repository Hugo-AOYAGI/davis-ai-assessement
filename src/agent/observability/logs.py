import logging
import sys
from typing import TextIO

_ROOT_LOGGER = "agent"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


class _AgentHandler(logging.StreamHandler[TextIO]):
    """Stderr handler marking the one installed by ``setup_logging``."""


def setup_logging(level: str) -> None:
    """Configure the ``agent`` logger hierarchy to write concise lines to stderr.

    Safe to call several times: the handler is installed once, the level is updated each call.

    Args:
        level: Standard logging level name, e.g. ``"INFO"`` or ``"DEBUG"``.
    """
    logger = logging.getLogger(_ROOT_LOGGER)
    logger.setLevel(level.upper())
    if not any(isinstance(handler, _AgentHandler) for handler in logger.handlers):
        handler = _AgentHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger, to be called with ``__name__`` so it sits under the ``agent`` hierarchy.

    Args:
        name: Dotted logger name, normally the calling module's ``__name__``.

    Returns:
        The named logger.
    """
    return logging.getLogger(name)
