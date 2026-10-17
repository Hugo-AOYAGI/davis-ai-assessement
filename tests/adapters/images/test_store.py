import hashlib

import pytest

from agent.adapters.images.store import ImageStore

PNG = b"\x89PNG\r\n\x1a\nfake image"
DIGEST = hashlib.sha256(PNG).hexdigest()


@pytest.fixture
def store(tmp_path):
    return ImageStore(directory=tmp_path / "images", url_prefix="/images")


def test_put_is_content_addressed_and_idempotent(store, tmp_path):
    url = store.put(PNG)
    assert url == f"/images/{DIGEST}.png"
    assert store.put(PNG) == url
    assert [path.name for path in (tmp_path / "images").iterdir()] == [f"{DIGEST}.png"]
    assert store.put(b"other") != url


def test_read_returns_the_bytes(store):
    url = store.put(PNG)
    assert store.owns(url)
    assert store.read(url) == PNG
    assert store.path(f"{DIGEST}.png").read_bytes() == PNG


def test_prefix_trailing_slash_is_ignored(tmp_path):
    store = ImageStore(directory=tmp_path, url_prefix="/images/")
    assert store.url_prefix == "/images"
    assert store.put(PNG) == f"/images/{DIGEST}.png"


@pytest.mark.parametrize(
    "url",
    [
        f"/other/{DIGEST}.png",
        f"https://example.com/images/{DIGEST}.png",
        f"/images/{DIGEST}.jpg",
        f"/images/{DIGEST[:-1]}.png",
        f"/images/{DIGEST.upper()}.png",
        f"/images/../{DIGEST}.png",
        f"/images/sub/{DIGEST}.png",
        "/images/../../etc/passwd",
        "",
    ],
)
def test_foreign_and_malformed_urls_are_not_read(store, url):
    store.put(PNG)
    assert not store.owns(url)
    assert store.read(url) is None


@pytest.mark.parametrize(
    "name", [f"../{DIGEST}.png", f"{DIGEST}.png/..", "..", f"{DIGEST}", f"x{DIGEST}.png"]
)
def test_malformed_names_have_no_path(store, name):
    store.put(PNG)
    assert store.path(name) is None


def test_missing_file_reads_as_none(store):
    url = f"/images/{DIGEST}.png"
    assert store.owns(url)
    assert store.read(url) is None
    assert store.path(f"{DIGEST}.png") is None
