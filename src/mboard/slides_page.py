"""Main page for the slideshow."""

import logging

from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from lcr_session.session import LcrSession
from mboard.missionaries import Missionaries
from mboard.paths import PHOTOS_DIR
from mboard.templates import templates

logger = logging.getLogger(__name__)


PAGE_SIZE = 6


async def slides(request: Request) -> Response:
    db = request.app.state.db
    if not db.get("church_username") or not db.get("church_password"):
        logger.info("No church credentials available. Redirecting to setup page.")
        return RedirectResponse(request.url_for("setup"))

    missionaries_repo = request.app.state.missionaries
    if missionaries_repo is None:
        client = LcrSession(db["church_username"], db["church_password"])
        missionaries_repo = Missionaries(db, PHOTOS_DIR, client)
        request.app.state.missionaries = missionaries_repo

    offset = int(request.query_params.get("offset", 0))
    limit = int(request.query_params.get("limit", PAGE_SIZE))
    missionaries, offset = missionaries_repo.list_range(offset, limit)
    context = {
        "request": request,
        "next_url": f"{request.url_for('slides')}?offset={offset}&limit={PAGE_SIZE}",
        "missionaries": missionaries,
        "refresh_error": missionaries_repo.get_refresh_error(),
    }

    task = BackgroundTask(missionaries_repo.refresh)

    return templates.TemplateResponse(request, "slide.html", context, background=task)
