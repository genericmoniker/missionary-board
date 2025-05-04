"""Tests for the setup page."""

from unittest import mock

import httpx

from mboard.database import Database
from mboard.login_page import _password_hasher


def test_login_required(client: httpx.Client) -> None:
    response = client.get("/setup", follow_redirects=False)
    assert 300 <= response.status_code < 400  # noqa: PLR2004
    assert "/login" in response.headers["Location"]


def test_error_on_empty_username(client: httpx.Client, db: Database) -> None:
    _login(client, db)
    response = client.post("/setup", data={"username": "", "password": "abc"})
    assert response.status_code == 200  # noqa: PLR2004
    assert "Username and password are required" in response.text


def test_error_on_empty_password(client: httpx.Client, db: Database) -> None:
    _login(client, db)
    response = client.post("/setup", data={"username": "", "password": "abc"})
    assert response.status_code == 200  # noqa: PLR2004
    assert "Username and password are required" in response.text


def test_disconnect(client: httpx.Client, db: Database) -> None:
    db["missionaries"] = ["foo"]
    _login(client, db)
    response = client.post("/setup", data={"action": "disconnect"})
    assert response.status_code == 200  # noqa: PLR2004
    assert not db.get("church_username")
    assert not db.get("church_password")
    assert not db.get("missionaries")


def test_error_on_invalid_credentials(client: httpx.Client, db: Database) -> None:
    _login(client, db)
    with mock.patch("mboard.setup_page.LcrSession", autospec=True) as session:
        session.return_value.get_user_details.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=mock.Mock(),
            response=mock.Mock(status_code=401),
        )
        response = client.post("/setup", data={"username": "foo", "password": "bar"})
    assert response.status_code == 200  # noqa: PLR2004
    assert "supplied credentials" in response.text


def test_successful_setup(client: httpx.Client, db: Database) -> None:
    _login(client, db)
    with mock.patch("mboard.setup_page.LcrSession", autospec=True) as session:
        session.return_value.get_user_details.return_value = None
        response = client.post("/setup", data={"username": "foo", "password": "bar"})
    assert response.status_code == 200  # noqa: PLR2004
    assert db["church_username"] == "foo"
    assert db["church_password"] == "bar"


def _login(client: httpx.Client, db: Database) -> None:
    db["admin_password_hash"] = _password_hasher.hash("foo")
    client.post(
        "/login", data={"username": "admin", "password": "foo"}, follow_redirects=False
    )
