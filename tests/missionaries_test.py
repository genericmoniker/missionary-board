from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Callable
import pytest
from mimesis import Generic
from mboard.database import Database
from mboard.google_photos import GooglePhotosClient
from mboard.missionaries import Missionaries, Missionary


generic = Generic()


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
        self.media_items = {}
        self.get_albums_called = False
        self.downloads = []

    async def get_albums(self):
        self.get_albums_called = True
        return [asdict(album) for album in self.albums]

    async def get_media_items(self, album_id: str):
        return [asdict(mi) for mi in self.media_items[album_id]]

    async def download(self, media_item_base_url: str):
        self.downloads.append(media_item_base_url)
        return b"Image data for " + media_item_base_url.encode("utf-8")


@dataclass
class Album:
    id: str = field(default_factory=generic.random.randstr)
    title: str = field(default="Missionary Board")
    productUrl: str = field(default_factory=generic.internet.url)
    isWriteable: bool = field(default=True)
    mediaItemsCount: str = field(default=str(0))
    coverPhotoBaseUrl: str = field(default_factory=generic.internet.url)
    coverPhotoMediaItemId: str = field(default_factory=generic.random.randstr)


@dataclass
class MediaItem:
    id: str = field(default_factory=generic.random.randstr)
    description: str = field(default_factory=generic.text.text)
    productUrl: str = field(default_factory=generic.internet.url)
    baseUrl: str = field(default_factory=generic.internet.url)
    mimeType: str = field(default="image/jpeg")
    mediaMetadata: dict = field(default_factory=dict)
    filename: str = field(default_factory=generic.file.file_name)


@pytest.mark.asyncio
async def test_refresh_skipped_if_not_needed(tmp_path):
    db = Database(":memory:")
    db["last_refresh"] = datetime.now()
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert not client.get_albums_called


@pytest.mark.asyncio
async def test_refresh_gets_new_missionary_data(tmp_path):
    db = Database(":memory:")
    db["last_refresh"] = datetime.min
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem()
    client.media_items = {album.id: [media_item]}
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert client.get_albums_called
    assert missionaries.list(0, 1)
    assert (tmp_path / media_item.filename).exists()


@pytest.mark.asyncio
async def test_refresh_updates_missionary_data(tmp_path):
    db = Database(":memory:")
    db["last_refresh"] = datetime.min
    db["missionaries"] = [Missionary(name="Sister Jones")]
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem(description="name: Sister Kate Jones")
    client.media_items = {album.id: [media_item]}
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert db["missionaries"][0].name == "Sister Kate Jones"


@pytest.mark.asyncio
async def test_refresh_does_not_download_already_cached_image(tmp_path):
    db = Database(":memory:")
    db["last_refresh"] = datetime.min
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem()
    client.media_items = {album.id: [media_item]}
    (tmp_path / media_item.filename).write_bytes(b"Image data")
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert media_item.baseUrl not in client.downloads


@pytest.mark.asyncio
async def test_refresh_cleans_up_old_images(tmp_path):
    db = Database(":memory:")
    db["last_refresh"] = datetime.min
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem()
    client.media_items = {album.id: [media_item]}
    (tmp_path / "old.jpg").write_bytes(b"Image data")
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert not (tmp_path / "old.jpg").exists()


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


@pytest.mark.parametrize(
    "description", ["", " ", "To be: or not to be", "name:", "foo:", "foo"]
)
def test_missionary_data_silently_empty_if_not_specified(tmp_path, description):
    db = Database(":memory:")
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    media_item = MediaItem(
        id="123",
        description=description,
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
