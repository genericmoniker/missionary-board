"""Main page for the slideshow."""

import logging
from functools import partial

from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from mboard.database import Database
from mboard.google_photos import GooglePhotosClient
from mboard.missionaries import Missionaries
from mboard.paths import PHOTOS_DIR
from mboard.templates import templates

logger = logging.getLogger(__name__)


PAGE_SIZE = 6


async def slides(request: Request) -> Response:
    db = request.app.state.db
    if not db.get("token"):
        logger.info("No access token available. Redirecting to setup page.")
        return RedirectResponse(request.url_for("setup"))

    offset = int(request.query_params.get("offset", 0))
    limit = int(request.query_params.get("limit", PAGE_SIZE))
    update_token = partial(_update_token, db)
    client = GooglePhotosClient(
        db["token"],
        update_token,
        db["client_id"],
        db["client_secret"],
    )
    missionaries_repo = Missionaries(db, PHOTOS_DIR, client)
    missionaries, offset = missionaries_repo.list_range(offset, limit)
    context = {
        "request": request,
        "next_url": f"{request.url_for('slides')}?offset={offset}&limit={PAGE_SIZE}",
        "missionaries": missionaries,
        "refresh_error": missionaries_repo.get_refresh_error(),
    }

    task = BackgroundTask(missionaries_repo.refresh)

    return templates.TemplateResponse(request, "slide.html", context, background=task)


async def _update_token(
    db: Database,
    token: dict,
    **kwargs: dict,  # noqa: ARG001
) -> None:
    """Update the token in the database when refreshed.

    The documentation is pretty sparse for this callback function. See
    https://docs.authlib.org/en/latest/client/httpx.html#auto-update-token

    The `token` parameter is a dictionary with the potentially new access token and
    refresh token.

    It can be called with `refresh_token` and/or `access_token` parameters too, which
    are the same values as in `token`, so I'm not sure what the point is. I just made
    the signature accept **kwargs.
    """
    # Save the new token in the database.
    db["token"] = token

    # Partially redact the tokens in the logs.
    log_token = dict(token)
    log_token["access_token"] = token["access_token"][:15] + "..."
    log_token["refresh_token"] = token["refresh_token"][:15] + "..."
    logger.info("Photos token updated: %s", log_token)

    # Find out what happens if the refresh token is expired too.
    # Docs say they last for 6 months (but can be revoked, etc.):
    # https://developers.google.com/identity/protocols/oauth2#expiration
    # I think the call to the OAuth2Client will raise OAuth2Error.
