import os
import tempfile
from pathlib import Path


def publish(path: Path, body: bytes) -> None:
    """Write a file atomically, so concurrent readers never see a partial body.

    A failed replacement propagates to the caller; an existing destination does not prove
    that the requested body was saved.

    Args:
        path: The file to publish.
        body: Its complete content.

    Raises:
        OSError: If writing or replacing the destination fails.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(body)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
