from langchain_core.tools import BaseTool, StructuredTool
from pydantic import JsonValue

from agent.adapters.raster.render import render_crop
from agent.tools.map.blocks import ContentBlock, image_block, text_block
from agent.tools.map.plan import open_plan

_NATIVE = 1.0
"""Legend panels are shown at most at native resolution: enlarging adds no detail."""


def view_legend_tool(plan: dict[str, JsonValue], max_output_px: int) -> BaseTool:
    """Build the ``view_legend`` tool, showing the legend panels of the zoning plan.

    Args:
        plan: The ``corpus.zoning_map`` config block.
        max_output_px: Long edge of each returned image.

    Returns:
        The tool.
    """
    zoning = open_plan(plan)

    def view_legend() -> list[ContentBlock]:
        """Show the legend of the zoning plan.

        Returns one image per legend panel of the plan: the zones with their colours and codes,
        and the symbols, hatching and line styles of the plan overlays (limits, protected
        elements, risk areas, perimeters, reserved sites...). Use it to identify what you see on
        view_map crops and to report each feature under its exact legend label.
        """
        boxes = zoning.settings.legend
        images = [
            image_block(
                render_crop(zoning.image, box, max_output_px=max_output_px, max_upscale=_NATIVE)
            )
            for box in boxes
        ]
        references = "; ".join(f"plan px {box.as_list()}" for box in boxes)
        caption = (
            f"Legend of the zoning plan `{zoning.settings.doc}`, page {zoning.settings.page}: "
            f"{len(boxes)} panels follow ({references})."
        )
        return [text_block(caption), *images]

    return StructuredTool.from_function(view_legend, name="view_legend")
