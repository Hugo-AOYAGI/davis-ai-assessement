import httpx
import pytest

from agent.adapters.http import CachedHttp, ServiceError

URL = "https://example.test/search"
PNG = b"\x89PNG\r\n\x1a\nfake"


class Recording(httpx.MockTransport):
    def __init__(self, response: httpx.Response) -> None:
        self.requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return response

        super().__init__(handler)


@pytest.fixture
def json_transport() -> Recording:
    return Recording(httpx.Response(200, json={"features": [1, 2]}))


@pytest.fixture
def png_transport() -> Recording:
    return Recording(httpx.Response(200, content=PNG, headers={"content-type": "image/png"}))


@pytest.fixture
def guard_transport() -> Recording:
    return Recording(httpx.Response(599))


def test_cache_hit_performs_no_second_request(tmp_path, json_transport):
    http = CachedHttp(tmp_path, timeout_s=5, transport=json_transport)
    first = http.get_json(URL, {"q": "4 rue Joliot Curie", "limit": "5"})
    second = http.get_json(URL, {"limit": "5", "q": "4 rue Joliot Curie"})
    assert first == second == {"features": [1, 2]}
    assert len(json_transport.requests) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_cached_response_survives_a_new_client(tmp_path, json_transport, guard_transport):
    params = {"q": "4 rue Joliot Curie", "limit": "5"}
    expected = CachedHttp(tmp_path, timeout_s=5, transport=json_transport).get_json(URL, params)
    replayed = CachedHttp(tmp_path, timeout_s=5, transport=guard_transport).get_json(URL, params)
    assert replayed == expected
    assert guard_transport.requests == []


def test_cache_dir_is_created_lazily(tmp_path, json_transport):
    cache_dir = tmp_path / "nested" / "cache"
    CachedHttp(cache_dir, timeout_s=5, transport=json_transport).get_json(URL, {"q": "x"})
    assert cache_dir.is_dir()


def test_bytes_are_cached_with_their_extension(tmp_path, png_transport, guard_transport):
    params = {"LAYERS": "x"}
    first = CachedHttp(tmp_path, 5, png_transport).get_bytes(URL, params, "image/png")
    second = CachedHttp(tmp_path, 5, guard_transport).get_bytes(URL, params, "image/png")
    assert first == second == PNG
    assert len(list(tmp_path.glob("*.png"))) == 1
    assert guard_transport.requests == []


def test_bytes_of_another_media_type_raise_and_cache_nothing(tmp_path):
    body = b"<ServiceExceptionReport>Layer unknown</ServiceExceptionReport>"
    response = httpx.Response(200, content=body, headers={"content-type": "text/xml"})
    http = CachedHttp(tmp_path / "cache", 5, Recording(response))
    with pytest.raises(ServiceError, match=r"text/xml instead of image/png.*Layer unknown"):
        http.get_bytes(URL, {"LAYERS": "x"}, "image/png")
    assert not (tmp_path / "cache").exists()


def failing(error: Exception | None, status: int = 200, body: bytes = b"{}"):
    def handler(request: httpx.Request) -> httpx.Response:
        if error is not None:
            raise error
        return httpx.Response(status, content=body)

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    ("transport", "fragment"),
    [
        (failing(None, status=500, body=b"boom"), "HTTP 500"),
        (failing(httpx.ReadTimeout("too slow")), "ReadTimeout"),
        (failing(httpx.ConnectError("refused")), "ConnectError"),
        (failing(None, body=b"<html>not json</html>"), "non-JSON"),
    ],
    ids=["status-500", "timeout", "connect", "not-json"],
)
def test_failures_raise_and_cache_nothing(tmp_path, transport, fragment):
    http = CachedHttp(tmp_path / "cache", timeout_s=5, transport=transport)
    with pytest.raises(ServiceError, match=fragment) as raised:
        http.get_json(URL, {"q": "x"})
    assert URL in str(raised.value)
    assert not (tmp_path / "cache").exists()
