"""Tests for the missionaries module."""

import string
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from random import choices

import pytest
from mimesis import Generic

from mboard.database import Database
from mboard.google_photos import GooglePhotosClient
from mboard.missionaries import Missionaries, Missionary

# ruff: noqa: N815 (Google uses camelCase for many of its API fields)


generic = Generic()


def randstr() -> str:
    return "".join(choices(string.ascii_lowercase, k=8))  # noqa: S311


class FakeGooglePhotosClient(GooglePhotosClient):
    """A fake Google Photos client for testing purposes."""

    def __init__(
        self,
        token: dict,
        update_token: Callable,
        client_id: str = "",
        client_secret: str = "",
    ) -> None:
        super().__init__(token, update_token, client_id, client_secret)
        self.albums = []
        self.media_items = {}
        self.get_albums_called = False
        self.downloads = []

    async def get_albums(self) -> list[dict]:
        """Return a list of fake Google Photos albums."""
        self.get_albums_called = True
        return [asdict(album) for album in self.albums]

    async def get_media_items(self, album_id: str) -> list[dict]:
        """Return a list of fake Google Photos media items."""
        return [asdict(mi) for mi in self.media_items[album_id]]

    async def download(self, media_item_base_url: str) -> bytes:
        """Return fake image data."""
        self.downloads.append(media_item_base_url)
        return b"Image data for " + media_item_base_url.encode("utf-8")


@dataclass
class Album:
    """A fake Google Photos album for testing purposes."""

    id: str = field(default_factory=randstr)
    title: str = field(default="Missionary Board")
    productUrl: str = field(default_factory=generic.internet.url)
    isWriteable: bool = field(default=True)
    mediaItemsCount: str = field(default=str(0))
    coverPhotoBaseUrl: str = field(default_factory=generic.internet.url)
    coverPhotoMediaItemId: str = field(default_factory=randstr)


def media_metadata() -> dict:
    return {
        "creationTime": "2021-01-01T00:00:00Z",
        "width": "800",
        "height": "600",
    }


@dataclass
class MediaItem:
    """A fake Google Photos media item for testing purposes."""

    id: str = field(default_factory=randstr)
    description: str = field(default_factory=generic.text.text)
    productUrl: str = field(default_factory=generic.internet.url)
    baseUrl: str = field(default_factory=generic.internet.url)
    mimeType: str = field(default="image/jpeg")
    mediaMetadata: dict = field(default_factory=media_metadata)
    filename: str = field(default_factory=generic.file.file_name)


@pytest.mark.asyncio
async def test_refresh_skipped_if_not_needed(tmp_path: Path, db: Database) -> None:
    db["last_refresh"] = datetime.now(tz=UTC)
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert not client.get_albums_called


@pytest.mark.asyncio
async def test_refresh_gets_new_missionary_data(tmp_path: Path, db: Database) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem(
        filename="abc.jpg", mediaMetadata={"width": "1", "height": "1"}
    )
    client.media_items = {album.id: [media_item]}
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert client.get_albums_called
    missionaries_items, next_offset = missionaries.list_range(0, 1)
    assert missionaries_items
    assert next_offset == 0
    assert (tmp_path / "abc_1x1.jpg").exists()


@pytest.mark.asyncio
async def test_refresh_updates_missionary_data(tmp_path: Path, db: Database) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    db["missionaries"] = [Missionary(name="Sister Jones")]
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem(description="Sister Kate Jones")
    client.media_items = {album.id: [media_item]}
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert db["missionaries"][0].name == "Sister Kate Jones"


@pytest.mark.asyncio
async def test_refresh_does_not_download_already_cached_image(
    tmp_path: Path,
    db: Database,
) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem(
        filename="cached.jpg",
        mediaMetadata={"width": "5", "height": "9"},
    )
    client.media_items = {album.id: [media_item]}
    (tmp_path / "cached_5x9.jpg").write_bytes(b"Image data")
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert media_item.baseUrl not in client.downloads


@pytest.mark.asyncio
async def test_refresh_downloads_resized_image(tmp_path: Path, db: Database) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem(
        filename="cached.jpg", mediaMetadata={"width": "5", "height": "9"}
    )
    client.media_items = {album.id: [media_item]}
    (tmp_path / "cached_8x10.jpg").write_bytes(b"Image data")
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert media_item.baseUrl in client.downloads


@pytest.mark.asyncio
async def test_refresh_cleans_up_old_images(tmp_path: Path, db: Database) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    media_item = MediaItem()
    client.media_items = {album.id: [media_item]}
    (tmp_path / "old.jpg").write_bytes(b"Image data")
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()

    assert not (tmp_path / "old.jpg").exists()


@pytest.mark.asyncio
async def test_missionaries_sorted_by_last_name(tmp_path: Path, db: Database) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    client = FakeGooglePhotosClient({}, lambda *_: None)
    album = Album()
    client.albums = [album]
    client.media_items = {
        album.id: [
            MediaItem(description="Elder Victor Bravo"),
            MediaItem(description="Sister Zoe Anderson"),
            MediaItem(description="Sister Amanda Evans-Clinton"),
            MediaItem(description="Elder Ben Smith"),
            MediaItem(description="Elder Adam Smith"),
            MediaItem(description="Nephi"),
            MediaItem(description="Elder Charlie & Sister Brava Delta"),
            MediaItem(description=""),
        ]
    }
    missionaries = Missionaries(db, tmp_path, client)

    await missionaries.refresh()
    listed_range, _ = missionaries.list_range(0, 10)

    assert listed_range[0].name == ""
    assert listed_range[1].name == "Sister Zoe Anderson"
    assert listed_range[2].name == "Elder Victor Bravo"
    assert listed_range[3].name == "Elder Charlie & Sister Brava Delta"
    assert listed_range[4].name == "Sister Amanda Evans-Clinton"
    assert listed_range[5].name == "Nephi"
    assert listed_range[6].name == "Elder Adam Smith"
    assert listed_range[7].name == "Elder Ben Smith"


@pytest.mark.parametrize(
    "media_item_description",
    [
        # Whitespace variations...
        """
        Sister Jones
        1st Ward
        China Hong Kong Mission
        March 2023 - September 2024
        """,
        """    Sister Jones
        1st Ward
        China Hong Kong Mission
        March 2023 - September 2024
        """,
        "Sister Jones\n1st Ward\nChina Hong Kong Mission\nMarch 2023 - September 2024",
    ],
)
def test_missionary_data_parsed_from_media_item(
    tmp_path: Path, media_item_description: str, db: Database
) -> None:
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    media_item = MediaItem(
        id="123",
        description=media_item_description,
        productUrl="https://photos.google.com/lr/photo/123",
        baseUrl="https://lh3.googleusercontent.com/abc",
        mimeType="image/jpeg",
        mediaMetadata={"width": "5", "height": "9"},
        filename="abc.jpg",
    )
    missionary = missionaries._parse_media_item(asdict(media_item))  # noqa: SLF001

    assert missionary.image_path == "abc_5x9.jpg"
    assert missionary.image_base_url == "https://lh3.googleusercontent.com/abc"
    assert missionary.name == "Sister Jones"
    assert missionary.details == [
        "1st Ward",
        "China Hong Kong Mission",
        "March 2023 - September 2024",
    ]


@pytest.mark.parametrize("description", ["", " ", " \n "])
def test_missionary_data_silently_empty_if_not_specified(
    tmp_path: Path, description: str, db: Database
) -> None:
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    media_item = MediaItem(
        id="123",
        description=description,
        productUrl="https://photos.google.com/lr/photo/123",
        baseUrl="https://lh3.googleusercontent.com/abc",
        mimeType="image/jpeg",
        mediaMetadata={"width": "5", "height": "9"},
        filename="abc.jpg",
    )
    missionary = missionaries._parse_media_item(asdict(media_item))  # noqa: SLF001

    assert missionary.image_path == "abc_5x9.jpg"
    assert missionary.image_base_url == "https://lh3.googleusercontent.com/abc"
    assert missionary.name == ""
    assert missionary.details == []


@pytest.mark.parametrize(
    ("count", "offset", "limit", "expected_next_offset"),
    [
        (0, 0, 1, 0),
        (1, 0, 1, 0),
        (2, 0, 1, 1),
        (2, 1, 1, 0),
        (5, 0, 4, 4),
        (9, 4, 3, 7),
    ],
)
def test_list_returns_the_correct_next_offset(  # noqa: PLR0913
    tmp_path: Path,
    count: int,
    offset: int,
    limit: int,
    expected_next_offset: int,
    db: Database,
) -> None:
    db["missionaries"] = [Missionary(name=f"Sister Jones {i}") for i in range(count)]
    client = FakeGooglePhotosClient({}, lambda *_: None)
    missionaries = Missionaries(db, tmp_path, client)

    missionaries_items, next_offset = missionaries.list_range(offset, limit)

    assert missionaries_items if count else not missionaries_items
    assert next_offset == expected_next_offset
