"""Judge answers kept on disk, so scoring an output again costs nothing."""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

_SUFFIX = ".json"
_FAN_OUT = 2
"""Leading hex digits of a key naming its sub-directory, to keep directories small."""


def answer_key(parts: Sequence[str]) -> str:
    """Hash what decides an answer (model, prompts, inputs) into a cache key.

    Args:
        parts: The strings that decide the answer, in a fixed order.

    Returns:
        A SHA-256 hex digest; any change in any part gives another key.
    """
    return hashlib.sha256(json.dumps(list(parts), ensure_ascii=False).encode()).hexdigest()


class AnswerCache:
    """One JSON file per answer under a directory, named by its key."""

    def __init__(self, directory: Path) -> None:
        """Keep answers under ``directory``, created on the first write.

        Args:
            directory: The cache directory (``eval.judge.cache_dir``).
        """
        self._directory = directory

    def get(self, key: str) -> str | None:
        """Read a cached answer.

        Args:
            key: From ``answer_key``.

        Returns:
            The answer's JSON text, or ``None`` when it is not cached.
        """
        path = self._path(key)
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def put(self, key: str, answer: str) -> None:
        """Store an answer, replacing any previous one.

        Args:
            key: From ``answer_key``.
            answer: The answer's JSON text.
        """
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(answer, encoding="utf-8")

    def _path(self, key: str) -> Path:
        """File of a key."""
        return self._directory / key[:_FAN_OUT] / f"{key}{_SUFFIX}"
