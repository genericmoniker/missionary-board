"""Missionaries repository."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mboard.database import Database
from mboard.google_photos import GooglePhotosClient

REFRESH_INTERVAL = timedelta(minutes=2)


@dataclass
class Missionary:
    """Missionary data."""

    image_path: str = ""
    image_base_url: str = ""
    name: str = ""
    details: list[str] = field(default_factory=list)


class Missionaries:
    """Missionaries repository/cache."""

    def __init__(
        self,
        db: Database,
        image_dir: Path,
        client: GooglePhotosClient,
    ) -> None:
        """Initialize the missionary repository."""
        self.db = db
        self.image_dir = image_dir
        self.client = client

    async def refresh(self) -> None:
        """Refresh the cache of missionaries from the photos album."""
        if not self._needs_refresh():
            return

        await self._sync_missionaries()
        self.db["last_refresh"] = datetime.now(tz=timezone.utc)

    def list_range(
        self,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[list[Missionary], int]:
        """List the missionaries.

        Returns a tuple of the list of missionaries and the offset of the next
        range of results.
        """
        missionaries = self.db.get("missionaries", [])
        next_offset = offset + limit if offset + limit < len(missionaries) else 0
        return missionaries[offset : offset + limit], next_offset

    def _needs_refresh(self) -> bool:
        now = datetime.now(tz=timezone.utc)
        last_refresh = self.db.get("last_refresh", datetime.min).replace(
            tzinfo=timezone.utc,
        )
        return now - last_refresh > REFRESH_INTERVAL

    async def _sync_missionaries(self) -> None:
        album = await self._find_album()
        missionaries = await self._load_missionaries(album)
        current_image_paths = await self._cache_images(missionaries)
        self._clean_up_old_images(current_image_paths)
        self.db["missionaries"] = missionaries

    async def _find_album(self) -> dict:
        albums = await self.client.get_albums()
        board_album_name = "Missionary Board"
        for album in albums:
            if album["title"] == board_album_name:
                return album
        msg = f"'{board_album_name}' album not found"
        raise MissionaryAlbumNotFoundError(msg)

    async def _load_missionaries(self, album: dict) -> list[Missionary]:
        media_items = await self.client.get_media_items(album["id"])
        missionaries = [self._parse_media_item(item) for item in media_items]
        # Maybe sort by last name?
        return missionaries

    def _parse_media_item(self, item: dict) -> Missionary:
        data = {
            "image_path": item["filename"],
            "image_base_url": item["baseUrl"],
            "name": "",
            "details": [],
        }
        description = item.get("description", "")
        lines = description.splitlines()
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if not data["name"]:
                data["name"] = line
                continue
            data["details"].append(line)
        return Missionary(**data)

    async def _cache_images(self, missionaries: list[Missionary]) -> set:
        current_image_paths = set()
        for missionary in missionaries:
            image_path = self.image_dir / missionary.image_path
            current_image_paths.add(image_path)
            if not image_path.exists():
                image_data = await self.client.download(missionary.image_base_url)
                image_path.write_bytes(image_data)
        return current_image_paths

    def _clean_up_old_images(self, current_image_paths: set) -> None:
        for image_path in self.image_dir.iterdir():
            if image_path not in current_image_paths:
                image_path.unlink()


class MissionaryAlbumNotFoundError(Exception):
    """Missionary album not found error."""
