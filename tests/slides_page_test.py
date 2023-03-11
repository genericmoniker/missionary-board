from datetime import datetime
from mboard.missionaries import Missionary


def test_redirect_to_setup_if_no_token(client):
    response = client.get("/", follow_redirects=False)
    assert 300 <= response.status_code < 400
    assert response.next_request.url.path == "/setup"


def test_show_slides_if_token(client, db):
    db["last_refresh"] = datetime.max
    db["token"] = {"access_token": "foo", "refresh_token": "bar"}
    db["client_id"] = "foo"
    db["client_secret"] = "bar"
    db["missionaries"] = [Missionary(name="Sister Jones")]
    response = client.get("/")
    assert response.status_code == 200
    assert b"Sister Jones" in response.content
