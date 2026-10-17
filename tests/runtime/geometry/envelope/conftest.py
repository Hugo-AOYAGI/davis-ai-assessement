import pytest

from agent.contracts.envelope import (
    BuildingLimits,
    Distance,
    EnvelopeRules,
    Layout,
    SetbackRule,
)
from agent.contracts.evidence import Citation, Limit, SourceKind
from agent.contracts.geometry import Boundary, BoundaryKind, Polygon
from agent.runtime.geometry.envelope.study import EnvelopeSettings

RECTANGLE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
KINDS = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)
CITATION = Citation(
    doc="plu_reglement", page=325, quote="6 mètres", source_kind=SourceKind.REGULATORY
)
SETTINGS = EnvelopeSettings(level_step_m=1, quad_segs=8, min_area_m2=1, cut_tolerance_m=0.01)


def _distance(min_m=None, ratio=None):
    return Distance(min_m=min_m, height_ratio=ratio, rule="see article", citations=(CITATION,))


def _limit(value):
    return Limit(value=value, rule="see article", citations=() if value is None else (CITATION,))


def _setback(kind, with_windows=None, without_windows=None, *, on_limit=False):
    return SetbackRule(
        kind=kind,
        on_limit_allowed=on_limit,
        with_windows=with_windows,
        without_windows=without_windows,
    )


def _make_rules(  # noqa: PLR0913
    *,
    road=None,
    side=None,
    rear=None,
    heights=(("A", 20), ("B", 20)),
    spacing_with: float | None = 10,
    spacing_without: float | None = 6,
    ratio=None,
    green=None,
):
    return EnvelopeRules(
        setbacks=(
            road or _setback(BoundaryKind.ROAD, _distance(5)),
            side or _setback(BoundaryKind.SIDE, _distance(4)),
            rear or _setback(BoundaryKind.REAR, _distance(4)),
        ),
        buildings=tuple(
            BuildingLimits(building=label, max_height_m=_limit(height), max_storeys=_limit(None))
            for label, height in heights
        ),
        spacing_with_windows=None if spacing_with is None else _distance(spacing_with),
        spacing_without_windows=None if spacing_without is None else _distance(spacing_without),
        max_footprint_ratio=_limit(ratio),
        min_green_ratio=_limit(green),
    )


def _make_layout(**changes):
    values = {
        "cut": "along_long_axis",
        "first_share": 0.5,
        "order": ("A", "B"),
        "facing_windows": True,
        "reasons": "Two equal parts.",
    }
    return Layout.model_validate({**values, **changes})


@pytest.fixture
def polygon():
    return Polygon(crs="EPSG:2154", exterior=RECTANGLE)


@pytest.fixture
def boundaries():
    return tuple(
        Boundary(kind=kind, start=start, end=end)
        for kind, start, end in zip(KINDS, RECTANGLE[:-1], RECTANGLE[1:], strict=True)
    )


@pytest.fixture
def distance():
    return _distance


@pytest.fixture
def setback():
    return _setback


@pytest.fixture
def make_rules():
    return _make_rules


@pytest.fixture
def make_layout():
    return _make_layout


@pytest.fixture
def settings():
    return SETTINGS
