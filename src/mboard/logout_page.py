"""Logout page."""

from starlette.requests import Request
from starlette.responses import RedirectResponse


async def logout(request: Request) -> RedirectResponse:
    """Log out."""
    request.session.pop("user", None)
    return RedirectResponse(request.url_for("login"), status_code=303)
