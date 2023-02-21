"""Logout page."""
from starlette.requests import Request
from starlette.responses import RedirectResponse


async def logout(request: Request):
    """Log out."""
    request.session.pop("user_id", None)
    return RedirectResponse(request.url_for("login"))
