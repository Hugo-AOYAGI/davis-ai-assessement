"""Read polygon and polyline shapefiles using the standard library and shapely."""

import struct
from itertools import pairwise
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

_POLYLINE = 3
_POLYGON = 5
_HEADER = 100
_DBF_FIELDS_END = 0x0D


def _signed_area(ring: list[tuple[float, float]]) -> float:
    """Shoelace area, negative for the clockwise rings the format uses as exteriors."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairwise(ring)) / 2


def _record(content: bytes) -> BaseGeometry | None:
    """Decode the content of one polygon or polyline record."""
    (shape_type,) = struct.unpack_from("<i", content, 0)
    if shape_type == 0:
        return None
    if shape_type not in {_POLYLINE, _POLYGON}:
        msg = f"unsupported shape type {shape_type}"
        raise ValueError(msg)
    num_parts, num_points = struct.unpack_from("<ii", content, 36)
    parts = [*struct.unpack_from(f"<{num_parts}i", content, 44), num_points]
    offset = 44 + 4 * num_parts
    coords = struct.unpack_from(f"<{2 * num_points}d", content, offset)
    points = list(zip(coords[0::2], coords[1::2], strict=True))
    rings = [points[a:b] for a, b in pairwise(parts)]
    if shape_type == _POLYLINE:
        lines = [LineString(ring) for ring in rings]
        return MultiLineString(lines) if len(lines) > 1 else lines[0]
    shells: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    for ring in rings:
        (shells if _signed_area(ring) < 0 else holes).append(ring)
    polygons = [Polygon(shell) for shell in shells]
    for hole in holes:
        inside = Polygon(hole).representative_point()
        for index, polygon in enumerate(polygons):
            if polygon.contains(inside):
                polygons[index] = Polygon(polygon.exterior, [*polygon.interiors, hole])
                break
    return MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]


def read_shapes(shp: Path) -> list[tuple[BaseGeometry | None, dict[str, str]]]:
    """Return ``(geometry, attributes)`` for each record of a polygon or polyline shapefile."""
    data = shp.read_bytes()
    geometries: list[BaseGeometry | None] = []
    position = _HEADER
    while position < len(data):
        (length_words,) = struct.unpack_from(">i", data, position + 4)
        content = data[position + 8 : position + 8 + 2 * length_words]
        geometries.append(_record(content))
        position += 8 + 2 * length_words
    rows = _read_dbf(shp.with_suffix(".dbf"))
    return list(zip(geometries, rows, strict=True))


def _read_dbf(path: Path) -> list[dict[str, str]]:
    """Read every non-deleted record of a dBase file as strings."""
    data = path.read_bytes()
    count, header_size, record_size = struct.unpack_from("<IHH", data, 4)
    fields: list[tuple[str, int]] = []
    position = 32
    while data[position] != _DBF_FIELDS_END:
        name = data[position : position + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, data[position + 16]))
        position += 32
    rows: list[dict[str, str]] = []
    for index in range(count):
        start = header_size + index * record_size
        record = data[start : start + record_size]
        offset = 1
        row: dict[str, str] = {}
        for name, size in fields:
            row[name] = record[offset : offset + size].decode("utf-8", "replace").strip()
            offset += size
        rows.append(row)
    return rows
