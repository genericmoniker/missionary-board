"""Set up the application.

Much of this is (as always) setting up OAuth2 authentication.
"""

import logging

import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from lcr_session.session import LcrSession
from mboard.database import Database
from mboard.login_required import login_required
from mboard.missionaries import Missionaries
from mboard.paths import COOKIE_FILE
from mboard.templates import templates

logger = logging.getLogger(__name__)


@login_required
async def setup(request: Request) -> Response:
    if request.method == "GET":
        return _setup_get(request, request.app.state.db)
    return await _setup_post(request, request.app.state.db)


def _setup_get(request: Request, db: Database) -> Response:
    """Handle a GET request to the setup page."""
    context = {
        "request": request,
        "username": db.get("church_username", ""),
        "has_password": bool(db.get("church_password")),
        "setup_error": db.get("setup_error", ""),
        "setup_error_description": db.get("setup_error_description", ""),
    }

    # If there was an error, clear it so it doesn't show up again.
    db["setup_error"] = ""
    db["setup_error_description"] = ""

    return templates.TemplateResponse(request, "setup.html", context)


async def _setup_post(request: Request, db: Database) -> Response:
    """Handle a POST request to the setup page."""
    setup_url = request.url_for("setup")
    form_data = await request.form()

    # We're either clearing credentials or setting new ones, so delete existing cookies.
    COOKIE_FILE.unlink(missing_ok=True)

    # Handle the "disconnect" button.
    if form_data.get("action") == "disconnect":
        db["church_username"] = ""
        db["church_password"] = ""
        Missionaries.clear(db)
        return RedirectResponse(setup_url, status_code=303)

    church_username = str(form_data.get("username", "")).strip()
    church_password = str(form_data.get("password", "")).strip()
    if not church_username or not church_password:
        db["setup_error"] = "Username and password are required."
        db["setup_error_description"] = "Please enter your username and password."
        return RedirectResponse(setup_url, status_code=303)

    if not await _check_credentials(church_username, church_password):
        db["setup_error"] = "Credentials didn't work."
        db["setup_error_description"] = "Please check your username and password."
        return RedirectResponse(setup_url, status_code=303)

    db["church_username"] = church_username
    db["church_password"] = church_password

    return RedirectResponse(setup_url, status_code=303)


async def _check_credentials(username: str, password: str) -> bool:
    session = LcrSession(username, password, cookie_jar_file=COOKIE_FILE)
    try:
        await session.get_user_details()
        return True
    except httpx.HTTPStatusError as e:
        logger.warning("Error checking credentials: %s", e)
        if e.response.status_code in (401, 403):
            return False
        raise
