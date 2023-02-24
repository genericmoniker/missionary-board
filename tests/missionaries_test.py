from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable
import pytest
from mboard.database import Database
from mboard.google_photos import GooglePhotosClient
from mboard.missionaries import Missionaries


class FakeGooglePhotosClient(GooglePhotosClient):
    def __init__(
        self,
        token: dict,
        update_token: Callable,
        client_id: str = "",
        client_secret: str = "",
    ):
        super().__init__(token, update_token, client_id, client_secret)
        self.albums = []
        self.get_albums_called = False

    async def get_albums(self):
        self.get_albums_called = True
        return self.albums


@dataclass
class Album:
    id: str
    title: str
    productUrl: str
    isWriteable: bool
    mediaItemsCount: str
    coverPhotoBaseUrl: str
    coverPhotoMediaItemId: str


@dataclass
class MediaItem:
    id: str
    description: str
    productUrl: str
    baseUrl: str
    mimeType: str
    mediaMetadata: dict
    filename: str


@pytest.mark.asyncio
async def test_refresh_skipped_if_not_needed(tmp_path):
    db = Database(":memory:")
    db["last_refresh"] = datetime.now()
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert not client.get_albums_called


@pytest.mark.parametrize(
    "media_item_description",
    [
        """
        name: Sister Jones
        mission: China Hong Kong Mission
        ward: 1st Ward
        start: March 2023
        end: September 2024
        """,
        # Key names are case-insensitive:
        """
        Name:Sister Jones
        Mission:China Hong Kong Mission
        Ward:1st Ward
        Start:March 2023
        End:September 2024
        """,
        # Keys can be in any order:
        """
        end: September 2024
        start: March 2023
        ward: 1st Ward
        mission: China Hong Kong Mission
        name: Sister Jones
        """,
    ],
)
def test_missionary_data_parsed_from_media_item(tmp_path, media_item_description):
    db = Database(":memory:")
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    media_item = MediaItem(
        id="123",
        description=media_item_description,
        productUrl="https://photos.google.com/lr/photo/123",
        baseUrl="https://lh3.googleusercontent.com/abc",
        mimeType="image/jpeg",
        mediaMetadata={},
        filename="abc.jpg",
    )
    missionary = missionaries._parse_media_item(asdict(media_item))

    assert missionary.image_path == "abc.jpg"
    assert missionary.image_base_url == "https://lh3.googleusercontent.com/abc"
    assert missionary.name == "Sister Jones"
    assert missionary.ward == "1st Ward"
    assert missionary.mission == "China Hong Kong Mission"
    assert missionary.start == "March 2023"
    assert missionary.end == "September 2024"


def test_missionary_data_silently_empty_if_not_specified(tmp_path):
    db = Database(":memory:")
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    media_item = MediaItem(
        id="123",
        description="",
        productUrl="https://photos.google.com/lr/photo/123",
        baseUrl="https://lh3.googleusercontent.com/abc",
        mimeType="image/jpeg",
        mediaMetadata={},
        filename="abc.jpg",
    )
    missionary = missionaries._parse_media_item(asdict(media_item))

    assert missionary.image_path == "abc.jpg"
    assert missionary.image_base_url == "https://lh3.googleusercontent.com/abc"
    assert missionary.name == ""
    assert missionary.ward == ""
    assert missionary.mission == ""
    assert missionary.start == ""
    assert missionary.end == ""
