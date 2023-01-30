"""Set up the application.

Not to be confused with a setuptools setup.py file.

Much of this is (as always) setting up OAuth2 authentication. See example code at:
https://github.com/omarryhan/aiogoogle/blob/master/examples/auth/oauth2.py

To enable the Google Photos API, go to:
https://console.cloud.google.com/apis/library/photoslibrary.googleapis.com

To manage credentials (client ID and secret), go to:
https://console.cloud.google.com/apis/credentials
"""
from aiogoogle import Aiogoogle
from aiogoogle.auth.utils import create_secret
from starlette.requests import Request
from starlette.responses import RedirectResponse

from mboard.database import Database
from mboard.templates import templates


async def setup(request: Request):
    if request.method == "GET":
        return _setup_get(request, request.app.state.db)
    return await _setup_post(request, request.app.state.db)


async def authorize(request: Request):
    db = request.app.state.db
    code = request.query_params.get("code")
    if code:
        # Verify the state value and get the full credentials.
        if request.query_params.get("state") == db.pop("state_secret"):
            client_creds = _get_client_creds(request, db)
            aiogoogle = Aiogoogle(client_creds=client_creds)
            full_user_creds = await aiogoogle.oauth2.build_user_creds(
                grant=code, client_creds=client_creds
            )
            db["user_creds"] = full_user_creds
            # Success -- onward!
            return RedirectResponse(request.url_for("slides"))

    # Redirect back to the setup page, showing an error.
    error = request.query_params.get("error", "Error")
    error_description = request.query_params.get(
        "error_description", "Sorry, something unexpected happened."
    )
    db["setup_error"] = error
    db["setup_error_description"] = error_description
    return RedirectResponse(request.url_for("setup"))


def _setup_get(request: Request, db: Database):
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

    return templates.TemplateResponse("setup.html", context)


async def _setup_post(request: Request, db: Database):
    data = await request.form()
    client_id = str(data.get("client_id", "")).strip()
    client_secret = str(data.get("client_secret", "")).strip()
    if not client_id or not client_secret:
        context = {
            "request": request,
            "client_id": client_id,
            "client_secret": client_secret,
            "client_id_error": "Client ID is required" if not client_id else "",
            "client_secret_error": "Client Secret is required"
            if not client_secret
            else "",
        }
        return templates.TemplateResponse("setup.html", context)

    db["client_id"] = client_id
    db["client_secret"] = client_secret
    auth_url = _get_authorization_url(request, db)
    return RedirectResponse(auth_url)


def _get_authorization_url(request: Request, db: Database):
    state = create_secret()
    db["state_secret"] = state
    client_creds = _get_client_creds(request, db)
    aiogoogle = Aiogoogle(client_creds=client_creds)
    return aiogoogle.oauth2.authorization_url(
        client_creds=client_creds,
        state=state,
        access_type="offline",
        include_granted_scopes=True,
        prompt="select_account",
    )


def _get_client_creds(request: Request, db: Database):
    return {
        "client_id": db["client_id"],
        "client_secret": db["client_secret"],
        "scopes": ["https://www.googleapis.com/auth/photoslibrary.readonly"],
        "redirect_uri": str(request.base_url) + "auth",
    }
