"""Missionary Board main module."""

from logging import getLogger
from pathlib import Path

from starlette.applications import Starlette

# from starlette.middleware import Middleware
# from starlette.middleware.authentication import AuthenticationMiddleware
# from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from mboard.database import Database
from mboard.login_page import login
from mboard.setup_page import authorize, setup
from mboard.templates import templates

_logger = getLogger(__name__)


async def homepage(request):  # pylint: disable=unused-argument
    return PlainTextResponse("Hello, world!")


async def slides(request):
    return templates.TemplateResponse("slide.html", {"request": request})


def create_app():
    db = Database()

    middleware = [
        # Middleware(SessionMiddleware, ),
        # Middleware(AuthenticationMiddleware, ),
    ]

    static_dir = Path(__file__).parent.parent.parent / "static"

    routes = [
        Mount("/static", StaticFiles(directory=static_dir), name="static"),
        Route("/login", login, methods=["GET", "POST"]),
        Route("/logout", setup),  # Need to implement logout.
        Route("/setup", setup, methods=["GET", "POST"]),
        Route("/authorize", authorize),
        Route("/slides", slides),
        Route("/", homepage),
    ]

    starlette = Starlette(debug=True, routes=routes, middleware=middleware)
    starlette.state.db = db
    return starlette


app = create_app()
