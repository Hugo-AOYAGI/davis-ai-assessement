import httpx
import pymupdf
import pytest

from agent.adapters.geo.imagery import (
    ImageryClient,
    Outline,
    OutlineStyle,
    blank_image,
    draw_outlines,
)
from agent.adapters.http import CachedHttp, ServiceError

URL = "https://data.geopf.fr/wms-r/wms"
LAYERS = {"map": "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", "aerial": "ORTHOIMAGERY.ORTHOPHOTOS"}
BOUNDS = (638500.0, 6845800.0, 638640.0, 6845940.0)
STYLE = OutlineStyle(rgb=(230, 0, 0), width_px=3, font_px=10, label_background_rgb=(255, 255, 255))


def client(http: CachedHttp) -> ImageryClient:
    return ImageryClient(
        url=URL,
        http=http,
        version="1.3.0",
        crs="EPSG:2154",
        media_type="image/png",
        layers=LAYERS,
        source="IGN Géoplateforme WMS",
    )


@pytest.mark.parametrize("kind", ["map", "aerial"])
def test_get_map_sends_a_wms_request(tmp_path, replay_transport, kind):
    image = client(CachedHttp(tmp_path, 5, replay_transport)).get_map(kind, BOUNDS, (64, 64))
    assert pymupdf.Pixmap(image).width == 64
    params = dict(replay_transport.requests[0].url.params)
    assert params == {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": LAYERS[kind],
        "STYLES": "",
        "CRS": "EPSG:2154",
        "BBOX": "638500.0,6845800.0,638640.0,6845940.0",
        "WIDTH": "64",
        "HEIGHT": "64",
        "FORMAT": "image/png",
    }


def test_get_map_is_cached(tmp_path, replay_transport, guard_transport):
    first = client(CachedHttp(tmp_path, 5, replay_transport)).get_map("aerial", BOUNDS, (64, 64))
    second = client(CachedHttp(tmp_path, 5, guard_transport)).get_map("aerial", BOUNDS, (64, 64))
    assert first == second
    assert guard_transport.requests == []


def test_service_exception_is_an_error(tmp_path):
    report = b"<ServiceExceptionReport><ServiceException>Layer NOPE unknown</ServiceException>"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(400, content=report, headers={"content-type": "text/xml"})
    )
    with pytest.raises(ServiceError, match=r"HTTP 400.*Layer NOPE unknown"):
        client(CachedHttp(tmp_path, 5, transport)).get_map("map", BOUNDS, (64, 64))


def test_unknown_kind(tmp_path, guard_transport):
    with pytest.raises(KeyError):
        client(CachedHttp(tmp_path, 5, guard_transport)).get_map("relief", BOUNDS, (64, 64))


def test_draw_outlines_keeps_size_and_paints_the_outline():
    blank = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 80), False)
    blank.set_rect(blank.irect, (255, 255, 255))
    square = ((10.0, 10.0), (60.0, 10.0), (60.0, 60.0), (10.0, 60.0), (10.0, 10.0))
    outline = Outline(label="91272000CR0247", rings=(square,), anchor=(20.0, 40.0))
    drawn = pymupdf.Pixmap(draw_outlines(blank.tobytes("png"), [outline], STYLE))
    assert (drawn.width, drawn.height) == (100, 80)
    red, green, blue = drawn.pixel(35, 10)
    assert red > 200
    assert green < 60
    assert blue < 60
    assert drawn.pixel(80, 70) == (255, 255, 255)


def test_blank_image_is_white():
    blank = pymupdf.Pixmap(blank_image((30, 20)))
    assert (blank.width, blank.height) == (30, 20)
    assert blank.pixel(15, 10) == (255, 255, 255)


def test_filled_outline_with_a_hole_and_its_own_colour():
    outer = ((10.0, 10.0), (90.0, 10.0), (90.0, 70.0), (10.0, 70.0), (10.0, 10.0))
    hole = ((40.0, 30.0), (60.0, 30.0), (60.0, 50.0), (40.0, 50.0), (40.0, 30.0))
    outline = Outline(
        label="", rings=(outer, hole), anchor=(0.0, 0.0), rgb=(0, 0, 255), fill_rgb=(0, 0, 255)
    )
    drawn = pymupdf.Pixmap(draw_outlines(blank_image((100, 80)), [outline], STYLE))
    assert drawn.pixel(20, 40) == (0, 0, 255)
    assert drawn.pixel(50, 40) == (255, 255, 255)
    assert drawn.pixel(95, 75) == (255, 255, 255)


def test_open_outline_is_not_closed():
    corner = ((10.0, 10.0), (90.0, 10.0), (90.0, 70.0))
    outline = Outline(label="", rings=(corner,), anchor=(0.0, 0.0), closed=False)
    drawn = pymupdf.Pixmap(draw_outlines(blank_image((100, 80)), [outline], STYLE))
    assert drawn.pixel(50, 10)[0] > 200
    assert drawn.pixel(50, 40) == (255, 255, 255)
