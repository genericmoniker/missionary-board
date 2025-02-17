"""Set up the application.

Much of this is (as always) setting up OAuth2 authentication.
"""

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from mboard import google_photos
from mboard.database import Database
from mboard.login_required import login_required
from mboard.templates import templates


@login_required
async def setup(request: Request) -> Response:
    if request.method == "GET":
        return _setup_get(request, request.app.state.db)
    return await _setup_post(request, request.app.state.db)


async def authorize(request: Request) -> RedirectResponse:
    """Route for the OAuth2 callback that Google will call."""
    db = request.app.state.db
    code = request.query_params.get("code")
    if code:
        token = await google_photos.authorize(
            client_id=db["client_id"],
            client_secret=db["client_secret"],
            state=db["state_secret"],
            redirect_uri="http://localhost:8000/authorize",
            authorization_code=code,
        )
        db["token"] = token
        return RedirectResponse(request.url_for("slides"))

    # Redirect back to the setup page, showing an error.
    error = request.query_params.get("error", "Error")
    error_description = request.query_params.get(
        "error_description",
        "Sorry, something unexpected happened.",
    )
    db["setup_error"] = error
    db["setup_error_description"] = error_description
    return RedirectResponse(request.url_for("setup"))


def _setup_get(request: Request, db: Database) -> Response:
    context = {
        "request": request,
        "client_id": db.get("client_id", ""),
        "client_secret": db.get("client_secret", ""),
        "setup_error": db.get("setup_error", ""),
        "setup_error_description": db.get("setup_error_description", ""),
    }

    # If there was an error, clear it so it doesn't show up again.
    db["setup_error"] = ""
    db["setup_error_description"] = ""

    return templates.TemplateResponse(request, "setup.html", context)


async def _setup_post(request: Request, db: Database) -> Response:
    form_data = await request.form()
    client_id = str(form_data.get("client_id", "")).strip()
    client_secret = str(form_data.get("client_secret", "")).strip()
    context = {
        "request": request,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    has_error = _validate_auth_input(context, client_id, client_secret)
    if has_error:
        return templates.TemplateResponse(request, "setup.html", context)

    db["client_id"] = client_id
    db["client_secret"] = client_secret
    redirect_url = str(request.url_for("authorize"))
    auth_url, state = google_photos.setup_auth(client_id, client_secret, redirect_url)
    db["state_secret"] = state

    # Redirect to the authorization URL. Note that this is a 303 redirect, which is a
    # POST-redirect-GET. If it were to remain a POST, it would also include client_id
    # and client_secret from our form in the POST body, and Google would complain that
    # we were sending them in both the POST body and the URL: "Access blocked:
    # Authorization Error OAuth 2 parameters can only have a single value: client_id"
    return RedirectResponse(auth_url, status_code=303)


def _validate_auth_input(context: dict, client_id: str, client_secret: str) -> bool:
    has_error = False
    if not client_id:
        context["client_id_error"] = "Client ID is required."
        has_error = True
    if not client_secret:
        context["client_secret_error"] = "Client Secret is required."
        has_error = True
    return has_error
