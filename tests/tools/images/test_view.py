import pymupdf

from agent.tools.images.view import view_image_tool, zoom_tool


def decode(store, block):
    assert block["type"] == "image"
    assert block["mime_type"] == "image/png"
    assert "base64" not in block
    return pymupdf.Pixmap(store.read(block["url"]))


def test_view_image_returns_caption_and_overview(images, store, invoke):
    reply = invoke(view_image_tool(pages=images, store=store), doc="plan", page=1)
    caption, image = reply.content
    assert caption["text"].startswith(
        "Overview of plan p.1: 400x200 px in overview coordinates; the full page is 1200x600 px."
    )
    pixmap = decode(store, image)
    assert (pixmap.width, pixmap.height) == (440, 240)


def test_view_image_errors_are_returned_to_the_model(images, store, invoke):
    tool = view_image_tool(pages=images, store=store)
    reply = invoke(tool, doc="plan", page=2)
    assert reply.status == "error"
    assert "plan has 1 pages (1 to 1); page 2 does not exist" in reply.content
    assert "known documents: plan" in invoke(tool, doc="oap", page=1).content


def test_zoom_enlarges_and_keeps_overview_coordinates(images, store, invoke):
    reply = invoke(zoom_tool(pages=images, store=store), doc="plan", page=1, region=[0, 0, 100, 50])
    caption, image = reply.content
    assert caption["text"].startswith(
        "Zoom on plan p.1, region [0, 0, 100, 50] in overview coordinates, enlarged 4.0x over "
        "the overview. This is the page's full resolution or more."
    )
    pixmap = decode(store, image)
    assert pixmap.width > 400


def test_zoom_below_full_resolution_says_nothing_about_it(images, store, invoke):
    reply = invoke(
        zoom_tool(pages=images, store=store), doc="plan", page=1, region=[0, 0, 400, 200]
    )
    assert "enlarged 1.0x" in reply.content[0]["text"]
    assert "full resolution" not in reply.content[0]["text"]


def test_zoom_rejects_bad_regions(images, store, invoke):
    tool = zoom_tool(pages=images, store=store)
    outside = invoke(tool, doc="plan", page=1, region=[0, 0, 500, 50])
    assert outside.status == "error"
    assert "region [0, 0, 500, 50] exceeds it" in outside.content
    empty = invoke(tool, doc="plan", page=1, region=[50, 0, 10, 50])
    assert empty.status == "error"
    assert "is not a box" in empty.content
    short = invoke(tool, doc="plan", page=1, region=[0, 0, 10])
    assert short.status == "error"


def test_descriptions_explain_coordinates(images, store):
    view = view_image_tool(pages=images, store=store)
    zoom = zoom_tool(pages=images, store=store)
    assert view.name == "view_image"
    assert zoom.name == "zoom"
    assert "rulers" in view.description
    assert "read_pages" in view.description
    assert "overview coordinates" in zoom.args["region"]["description"]
