import json

import pytest

from agent.tools.geo.parcels import describe_parcels_tool, find_parcels_tool

LON, LAT = 2.165254, 48.709836
PLOT, STRIP = "91272000CR0247", "91272000CR0249"
WEST, EAST = "91272000CR0227", "91272000CR0256"


def schema_properties(tool) -> set[str]:
    return set(tool.args)


def describe(surveyor, *ids: str):
    reply = describe_parcels_tool(surveyor).invoke(
        {"ids": list(ids), "longitude": LON, "latitude": LAT}
    )
    return json.loads(reply)


def test_find_parcels(surveyor):
    tool = find_parcels_tool(surveyor, radius_m=50)
    assert tool.name == "find_parcels"
    assert schema_properties(tool) == {"longitude", "latitude"}
    rows = json.loads(tool.invoke({"longitude": LON, "latitude": LAT}))
    assert [row["id"] for row in rows[:2]] == [STRIP, PLOT]
    strip, plot = rows[0], rows[1]
    assert strip["mean_width_m"] <= 1
    assert plot == {
        "id": PLOT,
        "contenance_m2": 5960,
        "distance_m": 2.5,
        "contains_point": False,
        "mean_width_m": 38.7,
        "touches": [WEST, STRIP],
    }


def test_find_parcels_service_error_is_a_message(broken_surveyor):
    reply = find_parcels_tool(broken_surveyor, radius_m=50).invoke(
        {"longitude": LON, "latitude": LAT}
    )
    assert reply.startswith("find_parcels failed:")


def test_describe_parcels_schema(surveyor):
    tool = describe_parcels_tool(surveyor)
    assert tool.name == "describe_parcels"
    assert schema_properties(tool) == {"ids", "longitude", "latitude"}
    assert "public_land" in tool.description


def test_describe_the_strip_is_a_misfit(surveyor):
    rows = describe(surveyor, STRIP)
    assert rows["parcels"][0]["contenance_m2"] == 116
    assert rows["parcels"][0]["mean_width_m"] < 1
    assert rows["distance_m"] == pytest.approx(1.8, abs=0.1)


def test_describe_the_plot(surveyor):
    rows = describe(surveyor, PLOT)
    assert rows["one_piece"] is True
    assert rows["area_m2"] == pytest.approx(5952, abs=2)
    assert rows["distance_m"] == 2.5
    assert rows["edges"]["public_land"] == {"count": 0, "length_m": 0}
    assert rows["edges"]["parcel"]["length_m"] == pytest.approx(308, abs=2)
    assert [n["id"] for n in rows["neighbours"]] == [STRIP, EAST, WEST]
    assert set(rows["neighbours"][0]) == {"id", "contenance_m2", "shared_length_m", "mean_width_m"}
    assert "polygon" not in json.dumps(rows)


def test_describe_plot_and_strip(surveyor):
    rows = describe(surveyor, PLOT, STRIP)
    assert [p["touches"] for p in rows["parcels"]] == [[STRIP], [PLOT]]
    assert rows["edges"]["public_land"]["length_m"] == pytest.approx(91, abs=2)


def test_describe_disjoint(surveyor):
    rows = describe(surveyor, PLOT, "91272000CR0215")
    assert rows["one_piece"] is False
    assert len(rows["part_areas_m2"]) == 2
    assert "edges" not in rows


@pytest.mark.parametrize(
    ("ids", "message"),
    [(["91272000CR9999"], "not in the cadastre"), (["CR0247"], "14 characters")],
)
def test_describe_errors_are_messages(surveyor, ids, message):
    reply = describe_parcels_tool(surveyor).invoke({"ids": ids, "longitude": LON, "latitude": LAT})
    assert reply.startswith("describe_parcels failed:")
    assert message in reply
