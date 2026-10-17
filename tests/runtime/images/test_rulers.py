import pytest
from pydantic import ValidationError

from agent.runtime.images.rulers import Ruler, nice_step


@pytest.mark.parametrize(
    ("target", "expected"),
    [(0.3, 1), (1, 1), (1.4, 1), (1.6, 2), (4, 5), (8, 10), (100, 100), (140, 100), (180, 200)],
)
def test_nice_step(target, expected):
    assert nice_step(target) == expected


def test_overview_ticks_every_step():
    ticks = Ruler(start=0, scale=1, length=450).ticks(100)
    assert ticks == ((0, 0), (100, 100), (200, 200), (300, 300), (400, 400))


def test_zoom_ticks_are_nice_and_positioned():
    ruler = Ruler(start=33.5, scale=20, length=600)
    ticks = ruler.ticks(100)
    assert [value for _, value in ticks] == [35, 40, 45, 50, 55, 60]
    for position, value in ticks:
        assert position == pytest.approx((value - 33.5) * 20)
        assert 0 <= position < 600


def test_ruler_rejects_bad_values():
    with pytest.raises(ValidationError):
        Ruler(start=0, scale=0, length=10)
    with pytest.raises(ValidationError):
        Ruler(start=0, scale=1, length=0)
