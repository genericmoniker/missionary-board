"""Main page for the slideshow."""
from functools import partial

from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import RedirectResponse

from mboard.database import Database
from mboard.google_photos import GooglePhotosClient
from mboard.missionaries import Missionaries
from mboard.paths import PHOTOS_DIR
from mboard.templates import templates

PAGE_SIZE = 6


async def slides(request: Request):
    db = request.app.state.db
    if not db.get("token"):
        return RedirectResponse(request.url_for("setup"))

    offset = int(request.query_params.get("offset", 0))
    limit = int(request.query_params.get("limit", PAGE_SIZE))
    update_token = partial(_update_token, db)
    client = GooglePhotosClient(
        db["token"], update_token, db["client_id"], db["client_secret"]
    )
    missionaries_repo = Missionaries(db, PHOTOS_DIR, client)
    missionaries = missionaries_repo.list(offset, limit)
    context = {
        "request": request,
        "next_offset": offset + limit if len(missionaries) == limit else 0,
        "next_limit": PAGE_SIZE,
        "missionaries": missionaries,
    }

    task = BackgroundTask(missionaries_repo.refresh)

    return templates.TemplateResponse("slide.html", context, background=task)


async def _update_token(
    db: Database,
    token: dict,
    access_token: str | None = None,  # pylint: disable=unused-argument
    refresh_token: str | None = None,  # pylint: disable=unused-argument
):
    """Callback to update the token in the database when refreshed."""
    db["token"] = token
    # Find out what happens if the refresh token is expired too.
    # Docs say they last for 6 months (but can be revoked, etc.):
    # https://developers.google.com/identity/protocols/oauth2#expiration
    # I think the call to the OAuth2Client will raise OAuth2Error.
