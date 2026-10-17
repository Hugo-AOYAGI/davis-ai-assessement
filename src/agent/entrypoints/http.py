from hydra.utils import instantiate
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Route

from agent.adapters.images.store import ImageStore
from agent.agents.config import load_config

_PNG = "image/png"
_NOT_FOUND = 404
_IMMUTABLE = "public, max-age=31536000, immutable"
"""Files are content-addressed: a URL always names the same bytes."""


def build_app(store: ImageStore) -> Starlette:
    """Build the HTTP routes mounted on the Agent Server (``langgraph.json`` → ``http.app``).

    ``GET <url_prefix>/<id>.png`` returns a stored tool image, so the chat UI can show the
    images that tool replies only reference.

    Args:
        store: The store the image tools write to.

    Returns:
        The Starlette app.
    """

    async def image(request: Request) -> Response:
        """Return a stored PNG, or 404 when the name is malformed or unknown."""
        path = store.path(str(request.path_params["name"]))
        if path is None:
            return Response(status_code=_NOT_FOUND)
        return FileResponse(path, media_type=_PNG, headers={"Cache-Control": _IMMUTABLE})

    return Starlette(routes=[Route(f"{store.url_prefix}/{{name}}", image, methods=["GET"])])


app = build_app(instantiate(load_config().images.store))
