"""Main page for the slideshow."""

import logging

from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from lcr_session.session import LcrSession
from mboard.missionaries import Missionaries, Missionary
from mboard.paths import PHOTOS_DIR
from mboard.templates import templates

logger = logging.getLogger(__name__)


PHOTOS_PAGE_SIZE = 6
NAMES_PAGE_SIZE = 80


async def slides(request: Request) -> Response:
    """Return a slideshow page.

    The page may either be missionaries with photos or a list of missionary names,
    depending on the URL query string parameters.
    """
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
    is_names = request.query_params.get("names", "false").lower() == "true"
    placeholder_photos = db.get("settings", {}).get("placeholder_photos", False)
    if is_names:
        limit = NAMES_PAGE_SIZE
        template = "slide-names.html"

        def filter_(m: Missionary) -> bool:
            return not m.image_path
    else:
        limit = PHOTOS_PAGE_SIZE
        template = "slide-photos.html"

        def filter_(m: Missionary) -> bool:
            return bool(m.image_path or placeholder_photos)

    missionaries, next_offset = missionaries_repo.list_range(offset, limit, filter_)
    if not missionaries:
        template = "slide-empty.html"
        next_url = request.url_for("slides")
    else:
        if next_offset == 0 and not placeholder_photos:
            is_names = not is_names

        next_url = (
            f"{request.url_for('slides')}"
            f"?offset={next_offset}"
            f"&names={str(is_names).lower()}"
        )

    context = {
        "request": request,
        "next_url": next_url,
        "missionaries": missionaries,
        "refresh_error": missionaries_repo.get_refresh_error(),
    }

    task = BackgroundTask(missionaries_repo.refresh)

    return templates.TemplateResponse(request, template, context, background=task)
