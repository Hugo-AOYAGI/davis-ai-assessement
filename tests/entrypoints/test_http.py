from starlette.routing import Route
from starlette.testclient import TestClient

from agent.adapters.images.store import ImageStore
from agent.entrypoints.http import app, build_app

PNG = b"\x89PNG\r\n\x1a\nfake image"


def test_stored_image_is_served(tmp_path):
    store = ImageStore(directory=tmp_path, url_prefix="/images")
    url = store.put(PNG)
    response = TestClient(build_app(store)).get(url)
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert "immutable" in response.headers["cache-control"]


def test_unknown_and_invalid_names_are_404(tmp_path):
    client = TestClient(build_app(ImageStore(directory=tmp_path, url_prefix="/images")))
    assert client.get(f"/images/{'0' * 64}.png").status_code == 404
    assert client.get("/images/notanid.png").status_code == 404
    assert client.get("/images/..%2Fsecret.png").status_code == 404


def test_module_app_serves_the_configured_prefix():
    paths = [route.path for route in app.routes if isinstance(route, Route)]
    assert paths == ["/images/{name}"]
