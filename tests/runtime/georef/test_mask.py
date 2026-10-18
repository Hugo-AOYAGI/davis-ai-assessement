import numpy as np
import pytest

from agent.runtime.georef.mask import colour_region, downscale, largest_component, outline


def test_downscale_averages_blocks_and_drops_partial_edges():
    rgb = np.zeros((5, 7, 3), dtype=np.uint8)
    rgb[:2, :2] = 200

    small = downscale(rgb, 2)

    assert small.shape == (2, 3, 3)
    assert small[0, 0] == pytest.approx([200, 200, 200])
    assert small[1, 1] == pytest.approx([0, 0, 0])


def test_colour_region_keeps_the_largest_fill_through_lines_and_drops_white():
    rgb = np.full((80, 100, 3), 255.0)
    rgb[10:60, 10:70] = (248, 104, 8)
    rgb[30, 10:70] = (0, 0, 0)
    rgb[70:75, 85:95] = (120, 184, 248)
    rgb[20:23, 80:98] = (40, 40, 40)

    mask = colour_region(
        rgb, min_saturation=30, close_px=3, close_iterations=1, open_px=3, open_iterations=1
    )

    assert mask[10:60, 10:70].mean() > 0.98
    assert not mask[70:75, 85:95].any()
    assert not mask[20:23, 80:98].any()


def test_largest_component_and_outline():
    mask = np.zeros((10, 10), dtype=bool)
    mask[1:5, 1:5] = True
    mask[7:9, 7:9] = True

    kept = largest_component(mask)

    assert kept.sum() == 16
    assert outline(kept).sum() == 12


def test_zero_opening_iterations_preserves_a_thin_region():
    rgb = np.full((12, 12, 3), 255.0)
    rgb[4:6, 2:10] = (240, 80, 20)
    result = colour_region(
        rgb, min_saturation=30, close_px=1, close_iterations=1, open_px=3, open_iterations=0
    )
    assert result.sum() == 16
