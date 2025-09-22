"""Missionary Board main module."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from logging import getLogger
from secrets import token_hex

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from mboard.database import Database
from mboard.login_page import login
from mboard.logout_page import logout
from mboard.paths import PHOTOS_DIR, ROOT_DIR
from mboard.setup_page import setup
from mboard.slides_page import slides

_logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """Handle app startup and shutdown events."""
    _logger.info("Application starting up...")

    yield  # This is where the app runs

    _logger.info("Application shutting down...")

    if hasattr(app.state, "missionaries") and app.state.missionaries:
        _logger.info("Shutting down missionaries repository...")
        try:
            await app.state.missionaries.close()
        except Exception:
            _logger.exception("Error shutting down missionaries repository")

    if hasattr(app.state, "db"):
        _logger.info("Closing database connection...")
        try:
            app.state.db.close()
        except OSError:
            _logger.exception("Error closing database")

    _logger.info("Application shutdown complete.")


def create_app() -> Starlette:
    db = Database()

    secret_key = db.get("secret_key")
    if not secret_key:
        _logger.info("Generating new secret key")
        secret_key = token_hex()
        db["secret_key"] = secret_key

    max_session_age = int(timedelta(minutes=30).total_seconds())

    middleware = [
        Middleware(
            SessionMiddleware,
            secret_key=secret_key,
            max_age=max_session_age,
            same_site="strict",
        ),
    ]

    static_dir = ROOT_DIR / "static"
    photos_dir = PHOTOS_DIR

    routes = [
        Mount("/static", StaticFiles(directory=static_dir), name="static"),
        Mount("/photos", StaticFiles(directory=photos_dir), name="photos"),
        Route("/ready", ready, methods=["GET", "HEAD"]),
        Route("/login", login, methods=["GET", "POST"]),
        Route("/logout", logout, methods=["POST"]),
        Route("/setup", setup, methods=["GET", "POST"]),
        Route("/", slides),
    ]

    starlette = Starlette(
        debug=True, routes=routes, middleware=middleware, lifespan=lifespan
    )
    starlette.state.db = db
    starlette.state.missionaries = None
    return starlette


async def ready(request: Request) -> PlainTextResponse:  # noqa: ARG001
    return PlainTextResponse("OK")


app = create_app()
