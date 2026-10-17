import httpx
import pytest

from agent.adapters.geo.http import CachedHttp, GeoServiceError

URL = "https://example.test/search"


def test_cache_hit_performs_no_second_request(tmp_path, replay_transport):
    http = CachedHttp(tmp_path, timeout_s=5, transport=replay_transport)
    first = http.get_json(URL, {"q": "4 rue Joliot Curie", "limit": "5"})
    second = http.get_json(URL, {"limit": "5", "q": "4 rue Joliot Curie"})
    assert first == second
    assert len(replay_transport.requests) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_cached_response_survives_a_new_client(tmp_path, replay_transport, guard_transport):
    params = {"q": "4 rue Joliot Curie", "limit": "5"}
    expected = CachedHttp(tmp_path, timeout_s=5, transport=replay_transport).get_json(URL, params)
    replayed = CachedHttp(tmp_path, timeout_s=5, transport=guard_transport).get_json(URL, params)
    assert replayed == expected
    assert guard_transport.requests == []


def test_cache_dir_is_created_lazily(tmp_path, replay_transport):
    cache_dir = tmp_path / "nested" / "cache"
    CachedHttp(cache_dir, timeout_s=5, transport=replay_transport).get_json(URL, {"q": "x"})
    assert cache_dir.is_dir()


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
    with pytest.raises(GeoServiceError, match=fragment) as raised:
        http.get_json(URL, {"q": "x"})
    assert URL in str(raised.value)
    assert not (tmp_path / "cache").exists()
