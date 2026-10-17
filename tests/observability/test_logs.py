import logging
from collections.abc import Iterator

import pytest

from agent.observability.logs import get_logger, setup_logging


@pytest.fixture
def agent_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger("agent")
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield logger
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


def test_setup_is_idempotent(agent_logger: logging.Logger):
    setup_logging("debug")
    setup_logging("INFO")
    own = [h for h in agent_logger.handlers if type(h).__module__ == "agent.observability.logs"]
    assert len(own) == 1
    assert agent_logger.level == logging.INFO
    assert get_logger("agent.llm.costs").getEffectiveLevel() == logging.INFO
