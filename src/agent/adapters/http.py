import hashlib
import json
import mimetypes
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

import httpx
from pydantic import JsonValue, TypeAdapter, ValidationError

from agent.observability.logs import get_logger

_LOGGER = get_logger(__name__)
_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_BODY_EXCERPT_CHARS = 300


class ServiceError(Exception):
    """A web service could not be reached or answered with an unusable payload."""


class CachedHttp:
    """GET client backed by an on-disk cache, one file per distinct request."""

    def __init__(
        self, cache_dir: Path, timeout_s: float, transport: httpx.BaseTransport | None = None
    ) -> None:
        """Create the client.

        Args:
            cache_dir: Directory holding cached responses, created on the first write.
            timeout_s: Network timeout for each request, in seconds.
            transport: Optional httpx transport, used by tests to replay recorded responses.
        """
        self._cache_dir = cache_dir
        self._timeout_s = timeout_s
        self._transport = transport

    def get_json(self, url: str, params: Mapping[str, str]) -> JsonValue:
        """Return the JSON body of ``GET url?params``, from the cache when available.

        Only successful responses are cached.

        Args:
            url: Service endpoint, without query string.
            params: Query parameters.

        Returns:
            The decoded JSON body.

        Raises:
            ServiceError: On network error, timeout, non-2xx status or non-JSON body.
        """
        path = self._path(url, params, ".json")
        if path.is_file():
            _LOGGER.debug("cache hit %s %s", url, path.name)
            return _JSON.validate_json(path.read_bytes())
        response = self._fetch(url, params)
        try:
            value = _JSON.validate_json(response.content)
        except ValidationError as error:
            msg = f"{url} answered a non-JSON body (HTTP {response.status_code})"
            raise ServiceError(msg) from error
        self._store(path, response.content)
        return value

    def get_bytes(self, url: str, params: Mapping[str, str], media_type: str) -> bytes:
        """Return the body of ``GET url?params``, from the cache when available.

        Only successful responses of the expected media type are cached.

        Args:
            url: Service endpoint, without query string.
            params: Query parameters.
            media_type: Expected ``Content-Type``, e.g. ``image/png``.

        Returns:
            The raw body.

        Raises:
            ServiceError: On network error, timeout, non-2xx status or another media type.
        """
        path = self._path(url, params, mimetypes.guess_extension(media_type) or "")
        if path.is_file():
            _LOGGER.debug("cache hit %s %s", url, path.name)
            return path.read_bytes()
        response = self._fetch(url, params)
        received = response.headers.get("content-type", "")
        if not received.startswith(media_type):
            excerpt = response.text[:_BODY_EXCERPT_CHARS] if received.startswith("text") else ""
            msg = (
                f"{url} answered {received or 'no content type'} instead of {media_type} {excerpt}"
            )
            raise ServiceError(msg.strip())
        self._store(path, response.content)
        return response.content

    def _path(self, url: str, params: Mapping[str, str], suffix: str) -> Path:
        """Return the cache file of a request."""
        return self._cache_dir / f"{_cache_key(url, params)}{suffix}"

    def _store(self, path: Path, body: bytes) -> None:
        """Publish a complete response atomically so concurrent readers see no partial body."""
        _LOGGER.debug("cache store %s", path.name)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=self._cache_dir, suffix=".tmp")
        temporary = Path(name)
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(body)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _fetch(self, url: str, params: Mapping[str, str]) -> httpx.Response:
        """Perform the request.

        Args:
            url: Service endpoint.
            params: Query parameters.

        Returns:
            The successful response.

        Raises:
            ServiceError: On any transport or status failure.
        """
        try:
            with httpx.Client(timeout=self._timeout_s, transport=self._transport) as client:
                response = client.get(url, params=dict(params))
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            status = error.response
            excerpt = status.text[:_BODY_EXCERPT_CHARS]
            msg = f"{url} answered HTTP {status.status_code} {status.reason_phrase}: {excerpt}"
            raise ServiceError(msg) from error
        except httpx.HTTPError as error:
            msg = f"{url} unreachable ({type(error).__name__}: {error}); retry later"
            raise ServiceError(msg) from error
        return response


def _cache_key(url: str, params: Mapping[str, str]) -> str:
    """Return a stable hash of a request.

    Args:
        url: Service endpoint.
        params: Query parameters, order-insensitive.

    Returns:
        Hex SHA-256 digest.
    """
    canonical = json.dumps([url, sorted(params.items())], ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
