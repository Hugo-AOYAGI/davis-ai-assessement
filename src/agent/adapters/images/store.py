import hashlib
import os
import re
import tempfile
from pathlib import Path

_NAME = re.compile(r"[0-9a-f]{64}\.png")
_SUFFIX = ".png"


class ImageStore:
    """Content-addressed PNG files on disk, referenced by relative URLs.

    Each PNG is stored once as ``<directory>/<sha256>.png`` and referenced as
    ``<url_prefix>/<sha256>.png``, the path at which the Agent Server serves it. Only names of
    that exact form are ever resolved, so a reference cannot reach outside ``directory``.
    """

    def __init__(self, *, directory: Path, url_prefix: str) -> None:
        """Set where images are written and how they are referenced.

        Args:
            directory: Folder holding the PNG files, created on first write.
            url_prefix: Path prefix of the references, e.g. ``/images``.
        """
        self._directory = directory
        self._prefix = url_prefix.rstrip("/") + "/"

    @property
    def url_prefix(self) -> str:
        """The path prefix of the references, without a trailing slash."""
        return self._prefix.rstrip("/")

    def put(self, png: bytes) -> str:
        """Store a PNG, unless an identical one is already stored, and return its reference.

        The file is written to a temporary name and then renamed, so a concurrent reader never
        sees a partial image.

        Args:
            png: PNG bytes.

        Returns:
            The reference URL, ``<url_prefix>/<sha256>.png``.
        """
        name = hashlib.sha256(png).hexdigest() + _SUFFIX
        target = self._directory / name
        if not target.is_file():
            self._directory.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=self._directory, suffix=".tmp")
            with os.fdopen(handle, "wb") as file:
                file.write(png)
            Path(temporary).replace(target)
        return self._prefix + name

    def owns(self, url: str) -> bool:
        """Tell whether a URL has the form of a reference made by this store.

        Args:
            url: Any URL.

        Returns:
            ``True`` for ``<url_prefix>/<sha256>.png``, whether or not the file exists.
        """
        return (
            url.startswith(self._prefix) and _NAME.fullmatch(url[len(self._prefix) :]) is not None
        )

    def path(self, name: str) -> Path | None:
        """Return the file of a stored image from its file name.

        Args:
            name: File name, ``<sha256>.png``.

        Returns:
            The file path, or ``None`` if the name is malformed or no such image is stored.
        """
        if _NAME.fullmatch(name) is None:
            return None
        target = self._directory / name
        return target if target.is_file() else None

    def read(self, url: str) -> bytes | None:
        """Return the PNG bytes of a reference made by this store.

        Args:
            url: The reference URL.

        Returns:
            The bytes, or ``None`` if the URL is not one of this store's or the file is gone.
        """
        if not self.owns(url):
            return None
        try:
            return (self._directory / url[len(self._prefix) :]).read_bytes()
        except FileNotFoundError:
            return None
