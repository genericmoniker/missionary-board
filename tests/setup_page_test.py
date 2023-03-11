from mboard.login_page import _password_hasher


def test_login_required(client):
    response = client.get("/setup", follow_redirects=False)
    assert 300 <= response.status_code < 400
    assert "/login" in response.headers["Location"]


def test_error_on_empty_client_id(client, db):
    _login(client, db)
    response = client.post("/setup", data={"client_id": "", "client_secret": "abc"})
    assert response.status_code == 200
    assert b"Client ID is required" in response.content


def test_error_on_empty_client_secret(client, db):
    _login(client, db)
    response = client.post("/setup", data={"client_id": "abc", "client_secret": ""})
    assert response.status_code == 200
    assert b"Client Secret is required" in response.content


def _login(client, db):
    db["admin_password_hash"] = _password_hasher.hash("foo")
    client.post(
        "/login", data={"username": "admin", "password": "foo"}, follow_redirects=False
    )
