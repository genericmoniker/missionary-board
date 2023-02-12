from mboard.login_page import _password_hasher


def test_prompt_for_initial_admin_password(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Please set up a password" in response.content


def test_error_on_empty_initial_admin_passwords(client):
    response = client.post("/login", data={"password": "", "password_conf": ""})
    assert response.status_code == 200
    assert b"Please set up a password" in response.content
    assert b"Password is required" in response.content
    assert b"Password confirmation is required" in response.content


def test_error_on_mismatched_passwords(client):
    response = client.post("/login", data={"password": "foo", "password_conf": "bar"})
    assert response.status_code == 200
    assert b"Please set up a password" in response.content
    assert b"Passwords do not match" in response.content


def test_successful_setup_of_admin_password(client, db):
    response = client.post("/login", data={"password": "foo", "password_conf": "foo"})
    assert response.status_code == 200
    assert b"password set successfully" in response.content
    assert b"Please set up a password" not in response.content
    assert b"Username" in response.content
    assert b"Password" in response.content


def test_prompt_for_admin_password(client, db):
    db["admin_password_hash"] = "some hash"
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Please set up a password" not in response.content
    assert b"Username" in response.content
    assert b"Password" in response.content


def test_successful_login(client, db):
    db["admin_password_hash"] = _password_hasher.hash("foo")
    response = client.post(
        "/login", data={"username": "admin", "password": "foo"}, follow_redirects=False
    )
    assert 300 < response.status_code < 400  # expect a redirect


def test_error_on_empty_username(client, db):
    db["admin_password_hash"] = "some hash"
    response = client.post("/login", data={"password": "foo"})
    assert response.status_code == 200
    assert b"Please set up a password" not in response.content
    assert b"Username" in response.content
    assert b"Password" in response.content
    assert b"Username is required" in response.content


def test_error_on_empty_password(client, db):
    db["admin_password_hash"] = "some hash"
    response = client.post("/login", data={"username": "admin"})
    assert response.status_code == 200
    assert b"Please set up a password" not in response.content
    assert b"Username" in response.content
    assert b"Password" in response.content
    assert b"Password is required" in response.content


def test_error_on_incorrect_username(client, db):
    db["admin_password_hash"] = _password_hasher.hash("foo")
    response = client.post("/login", data={"username": "hacker", "password": "foo"})
    assert response.status_code == 200
    assert b"Please set up a password" not in response.content
    assert b"Username" in response.content
    assert b"Password" in response.content
    assert b"Invalid username or password" in response.content


def test_error_on_incorrect_password(client, db):
    db["admin_password_hash"] = _password_hasher.hash("foo")
    response = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert response.status_code == 200
    assert b"Please set up a password" not in response.content
    assert b"Username" in response.content
    assert b"Password" in response.content
    assert b"Invalid username or password" in response.content
