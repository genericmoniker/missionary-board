"""Login page, including setup of the admin password."""

import argon2
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from mboard.database import Database
from mboard.templates import templates

_password_hasher = argon2.PasswordHasher()


async def login(request: Request) -> Response:
    if request.method == "GET":
        return _login_get(request, request.app.state.db)
    return await _login_post(request, request.app.state.db)


def _login_get(request: Request, db: Database) -> Response:
    context = {
        "request": request,
        "admin_password_established": _admin_password_established(db),
    }
    return templates.TemplateResponse(request, "login.html", context)


async def _login_post(request: Request, db: Database) -> Response:
    form_data = await request.form()
    context = {
        "request": request,
        "admin_password_established": _admin_password_established(db),
    }
    if not _admin_password_established(db):
        _establish_admin_password(form_data, db, context)
        return templates.TemplateResponse(request, "login.html", context)

    if not _login(form_data, db, context):
        return templates.TemplateResponse(request, "login.html", context)

    request.session["user"] = "admin"

    # The only interesting page requiring authentication is the setup page.
    return RedirectResponse(request.url_for("setup"), status_code=303)


def _establish_admin_password(form_data: FormData, db: Database, context: dict) -> None:
    password = str(form_data.get("password", "")).strip()
    password_conf = str(form_data.get("password_conf", "")).strip()
    has_error = _validate_admin_password_input(context, password, password_conf)
    if not has_error:
        # Hash the password and store it in the database.
        db["admin_password_hash"] = _password_hasher.hash(password)
        context["admin_password_established"] = True
        context["success_message"] = (
            "Admin password set successfully. You can now log in."
        )


def _validate_admin_password_input(
    context: dict,
    password: str,
    password_conf: str,
) -> bool:
    has_error = False
    if not password:
        context["password_error"] = "Password is required."
        has_error = True
    if password != password_conf:
        context["password_conf_error"] = "Passwords do not match."
        has_error = True
    if not password_conf:
        context["password_conf_error"] = "Password confirmation is required."
        has_error = True
    return has_error


def _login(form_data: FormData, db: Database, context: dict) -> bool:
    """Log in the user.

    Return True if login was successful, False otherwise.
    """
    username = str(form_data.get("username", "")).strip()
    password = str(form_data.get("password", "")).strip()
    has_error = _validate_login_input(context, username, password)
    if has_error:
        return False

    # Check the username and password against the database.
    password_hash = db["admin_password_hash"]
    try:
        _password_hasher.verify(password_hash, password)
    except argon2.exceptions.VerifyMismatchError:
        context["login_error"] = "Invalid username or password."
        return False

    # We want to always check the hash, even if the username is wrong, to avoid
    # timing attacks.
    if username != "admin":
        context["login_error"] = "Invalid username or password."
        return False

    # Check if the password needs to be rehashed.
    if _password_hasher.check_needs_rehash(password_hash):
        db["admin_password_hash"] = _password_hasher.hash(password)

    # Login successful.
    return True


def _validate_login_input(context: dict, username: str, password: str) -> bool:
    has_error = False
    if not username:
        context["username_error"] = "Username is required."
        has_error = True
    if not password:
        context["password_error"] = "Password is required."
        has_error = True
    return has_error


def _admin_password_established(db: Database) -> bool:
    return bool(db.get("admin_password_hash"))
