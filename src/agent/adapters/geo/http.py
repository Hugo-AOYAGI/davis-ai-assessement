import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import httpx
from pydantic import JsonValue, TypeAdapter, ValidationError

from agent.observability.logs import get_logger

_LOGGER = get_logger(__name__)
_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_BODY_EXCERPT_CHARS = 300


class GeoServiceError(Exception):
    """A geographic web service could not be reached or answered with an unusable payload."""


class CachedHttp:
    """JSON GET client backed by an on-disk cache, one file per distinct request."""

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
            GeoServiceError: On network error, timeout, non-2xx status or non-JSON body.
        """
        path = self._cache_dir / f"{_cache_key(url, params)}.json"
        if path.is_file():
            _LOGGER.debug("cache hit %s %s", url, path.name)
            return _JSON.validate_json(path.read_bytes())
        _LOGGER.debug("cache miss %s %s", url, path.name)
        value = self._fetch(url, params)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return value

    def _fetch(self, url: str, params: Mapping[str, str]) -> JsonValue:
        """Perform the request and decode its body.

        Args:
            url: Service endpoint.
            params: Query parameters.

        Returns:
            The decoded JSON body.

        Raises:
            GeoServiceError: On any transport, status or decoding failure.
        """
        try:
            with httpx.Client(timeout=self._timeout_s, transport=self._transport) as client:
                response = client.get(url, params=dict(params))
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            status = error.response
            excerpt = status.text[:_BODY_EXCERPT_CHARS]
            msg = f"{url} answered HTTP {status.status_code} {status.reason_phrase}: {excerpt}"
            raise GeoServiceError(msg) from error
        except httpx.HTTPError as error:
            msg = f"{url} unreachable ({type(error).__name__}: {error}); retry later"
            raise GeoServiceError(msg) from error
        try:
            return _JSON.validate_json(response.content)
        except ValidationError as error:
            msg = f"{url} answered a non-JSON body (HTTP {response.status_code})"
            raise GeoServiceError(msg) from error


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
