"""Smoke-check the Agent Server: start ``langgraph dev``, wait for health, run one message.

Usage: ``uv run python scripts/smoke_server.py [--port 2025]``. Costs one short orchestrator
call. The server output is kept in a log file whose path is logged.
"""

import argparse
import contextlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import IO

import httpx
from pydantic import BaseModel, JsonValue

from agent.agents.config import PROJECT_ROOT
from agent.observability.logs import get_logger, setup_logging

logger = get_logger("agent.scripts.smoke_server")


class Options(BaseModel):
    """Command-line options."""

    port: int
    assistant: str
    message: str
    startup_timeout: float
    run_timeout: float
    poll_interval: float
    log_tail: int
    log_level: str


def parse_options(argv: Sequence[str] | None = None) -> Options:
    """Parse the command line.

    Args:
        argv: Arguments, ``sys.argv[1:]`` when ``None``.

    Returns:
        The options.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2025, help="port for langgraph dev")
    parser.add_argument("--assistant", default="agent", help="graph id in langgraph.json")
    parser.add_argument("--message", default="Reply with the single word: pong.")
    parser.add_argument("--startup-timeout", type=float, default=180.0, help="seconds")
    parser.add_argument("--run-timeout", type=float, default=300.0, help="seconds")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="seconds")
    parser.add_argument("--log-tail", type=int, default=40, help="server lines shown on error")
    parser.add_argument("--log-level", default="INFO")
    return Options.model_validate(vars(parser.parse_args(argv)))


def start_server(port: int, log: IO[bytes]) -> subprocess.Popen[bytes]:
    """Start ``langgraph dev`` in its own process group, writing its output to ``log``.

    Args:
        port: Port to serve on.
        log: Binary file receiving stdout and stderr.

    Returns:
        The server process.

    Raises:
        FileNotFoundError: If ``uv`` is not on the PATH.
    """
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv not found on PATH"
        raise FileNotFoundError(msg)
    command = [uv, "run", "langgraph", "dev", "--no-browser", "--no-reload", "--port", str(port)]
    if sys.platform == "win32":
        return subprocess.Popen(  # noqa: S603
            command,
            cwd=PROJECT_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(  # noqa: S603
        command, cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
    )


def stop_server(process: subprocess.Popen[bytes]) -> None:
    """Kill the server and every process it spawned.

    Args:
        process: The process returned by ``start_server``.
    """
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        taskkill = shutil.which("taskkill") or "taskkill"
        subprocess.run(  # noqa: S603
            [taskkill, "/T", "/F", "/PID", str(process.pid)], capture_output=True, check=False
        )
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()
    logger.info("server stopped")


def wait_ready(client: httpx.Client, process: subprocess.Popen[bytes], options: Options) -> None:
    """Poll ``GET /ok`` until the server answers.

    Args:
        client: HTTP client bound to the server URL.
        process: The server process, checked for an early exit.
        options: Timeouts and poll interval.

    Raises:
        RuntimeError: If the server exits or is not ready before the startup timeout.
    """
    deadline = time.monotonic() + options.startup_timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            msg = f"server exited with code {process.returncode} before becoming ready"
            raise RuntimeError(msg)
        with contextlib.suppress(httpx.TransportError):
            if client.get("/ok").json() == {"ok": True}:
                return
        time.sleep(options.poll_interval)
    msg = f"server not ready after {options.startup_timeout:.0f}s"
    raise RuntimeError(msg)


def message_text(message: dict[str, JsonValue]) -> str:
    """Extract the text of a serialised message (string or content blocks).

    Args:
        message: A message as returned by the server.

    Returns:
        The concatenated text.
    """
    content = message.get("content")
    if isinstance(content, str):
        return content
    blocks = content if isinstance(content, list) else []
    return "".join(
        str(block.get("text", ""))
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    )


def run_message(client: httpx.Client, options: Options) -> str:
    """Create a thread, run one message to completion and return the final AI reply.

    Args:
        client: HTTP client bound to the server URL.
        options: Assistant, message and run timeout.

    Returns:
        The text of the last message.

    Raises:
        RuntimeError: If the last message is not a non-empty AI reply.
    """
    thread_id = client.post("/threads", json={}).raise_for_status().json()["thread_id"]
    payload = {
        "assistant_id": options.assistant,
        "input": {"messages": [{"role": "user", "content": options.message}]},
    }
    response = client.post(
        f"/threads/{thread_id}/runs/wait", json=payload, timeout=options.run_timeout
    )
    last = response.raise_for_status().json()["messages"][-1]
    text = message_text(last)
    if last.get("type") != "ai" or not text.strip():
        msg = f"expected a non-empty AI reply, got {last!r}"
        raise RuntimeError(msg)
    return text


def log_tail(path: Path, lines: int) -> None:
    """Log the last lines of the server output.

    Args:
        path: Server log file.
        lines: Number of lines to show.
    """
    tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    logger.error("server output (last %d lines):\n%s", len(tail), "\n".join(tail))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the smoke check.

    Args:
        argv: Arguments, ``sys.argv[1:]`` when ``None``.

    Returns:
        0 on success, 1 on failure.
    """
    options = parse_options(argv)
    setup_logging(options.log_level)
    log_fd, log_name = tempfile.mkstemp(prefix="langgraph-dev-", suffix=".log")
    log_path = Path(log_name)
    logger.info("server output: %s", log_path)
    with os.fdopen(log_fd, "wb") as log:
        process = start_server(options.port, log)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{options.port}") as client:
                wait_ready(client, process, options)
                logger.info("server ready on port %d", options.port)
                reply = run_message(client, options)
        except (RuntimeError, httpx.HTTPError) as error:
            logger.error("smoke check failed: %s", error)
            log_tail(log_path, options.log_tail)
            return 1
        finally:
            stop_server(process)
    logger.info("smoke check passed, reply: %r", reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
