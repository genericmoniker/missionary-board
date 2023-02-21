"""Missionary Board main module."""

from logging import getLogger

from starlette.applications import Starlette

# from starlette.middleware import Middleware
# from starlette.middleware.authentication import AuthenticationMiddleware
# from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from mboard.database import Database
from mboard.login_page import login
from mboard.logout_page import logout
from mboard.paths import PHOTOS_DIR, ROOT_DIR
from mboard.setup_page import authorize, setup
from mboard.slides_page import slides

_logger = getLogger(__name__)


async def homepage(request):  # pylint: disable=unused-argument
    return PlainTextResponse("Hello, world!")


def create_app():
    db = Database()

    middleware = [
        # Middleware(SessionMiddleware, ),
        # Middleware(AuthenticationMiddleware, ),
    ]

    static_dir = ROOT_DIR / "static"
    photos_dir = PHOTOS_DIR

    routes = [
        Mount("/static", StaticFiles(directory=static_dir), name="static"),
        Mount("/photos", StaticFiles(directory=photos_dir), name="photos"),
        Route("/login", login, methods=["GET", "POST"]),
        Route("/logout", logout, methods=["POST"]),
        Route("/setup", setup, methods=["GET", "POST"]),
        Route("/authorize", authorize),
        Route("/slides", slides),
        Route("/", homepage),
    ]

    starlette = Starlette(debug=True, routes=routes, middleware=middleware)
    starlette.state.db = db
    return starlette


app = create_app()
