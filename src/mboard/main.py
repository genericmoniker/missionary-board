"""Missionary Board main module."""

from logging import getLogger
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

logger = getLogger(__name__)


def homepage(request):  # pylint: disable=unused-argument
    return PlainTextResponse("Hello, world!")


def startup():
    logger.info("Ready to go")


def create_app():
    static_dir = Path(__file__).parent.parent.parent / "static"

    routes = [
        Mount("/static", StaticFiles(directory=static_dir)),
        Route("/", homepage),
    ]

    return Starlette(debug=True, routes=routes, on_startup=[startup])


app = create_app()
