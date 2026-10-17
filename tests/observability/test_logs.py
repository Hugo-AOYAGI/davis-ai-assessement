import logging
from collections.abc import Iterator

import pytest

from agent.observability.logs import get_logger, log_to_file, setup_logging


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


def test_log_to_file_replaces_previous_file(agent_logger: logging.Logger, tmp_path):
    setup_logging("INFO")
    log_to_file(tmp_path / "first.log")
    log_to_file(tmp_path / "second.log")
    get_logger("agent.test").info("hello")
    files = [
        h
        for h in agent_logger.handlers
        if isinstance(h, logging.FileHandler) and str(tmp_path) in h.baseFilename
    ]
    assert len(files) == 1
    for handler in files:
        handler.flush()
        handler.close()
        agent_logger.removeHandler(handler)
    assert "hello" in (tmp_path / "second.log").read_text(encoding="utf-8")
    assert "hello" not in (tmp_path / "first.log").read_text(encoding="utf-8")
