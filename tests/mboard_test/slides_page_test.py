"""Tests for the slides page."""

from datetime import datetime
from unittest import mock

import httpx

from mboard.database import Database
from mboard.missionaries import Missionary
from mboard.slides_page import NAMES_PAGE_SIZE, PHOTOS_PAGE_SIZE


def test_redirect_to_setup_if_no_token(client: httpx.Client) -> None:
    response = client.get("/", follow_redirects=False)
    assert 300 <= response.status_code < 400  # noqa: PLR2004
    assert response.next_request
    assert response.next_request.url.path == "/setup"


def test_show_slides_if_credentials(client: httpx.Client, db: Database) -> None:
    db["last_refresh"] = datetime.max
    db["church_username"] = "foo"
    db["church_password"] = "bar"
    db["missionaries"] = [Missionary(name="Sister Jones", image_path="p1.jpg")]
    response = client.get("/")
    assert response.status_code == 200  # noqa: PLR2004
    assert b"Sister Jones" in response.content


def test_photos_and_names_pagination(client: httpx.Client, db: Database) -> None:
    db["last_refresh"] = datetime.max
    db["church_username"] = "foo"
    db["church_password"] = "bar"

    photos = [
        Missionary(id=i, name=f"WithPhoto{i}", image_path=f"{i}.jpg")
        for i in range(PHOTOS_PAGE_SIZE * 2)
    ]
    id_offset = PHOTOS_PAGE_SIZE * 2
    names = [
        Missionary(id=i + id_offset, name=f"WithoutPhoto{i}")
        for i in range(NAMES_PAGE_SIZE * 2)
    ]
    missionaries = photos + names
    db["missionaries"] = missionaries

    # Skip the photo refresh so that image_path is not cleared.
    with mock.patch("mboard.missionaries.Missionaries._photo_only_refresh"):
        response = client.get("/")

        response = client.get("/")
        assert "WithPhoto0" in response.text
        next_url = extract_next_url(response)

        response = client.get(next_url)
        assert f"WithPhoto{PHOTOS_PAGE_SIZE}" in response.text
        next_url = extract_next_url(response)

        response = client.get(next_url)
        assert "WithoutPhoto0" in response.text
        next_url = extract_next_url(response)

        response = client.get(next_url)
        assert f"WithoutPhoto{NAMES_PAGE_SIZE}" in response.text
        next_url = extract_next_url(response)

        # Wrap back around to the first page.
        response = client.get(next_url)
        assert "WithPhoto0" in response.text


def extract_next_url(response: httpx.Response) -> str:
    """Extract the next URL from the response."""
    assert response.status_code == 200  # noqa: PLR2004
    prefix = '"30; url='
    assert prefix in response.text
    start = response.text.index(prefix) + len(prefix)
    end = response.text.index('">', start)
    next_url = response.text[start:end]
    return next_url.replace("&amp;", "&")
