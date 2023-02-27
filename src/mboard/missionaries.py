"""Missionaries repository."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

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
        self, db: Database, image_dir: Path, client: GooglePhotosClient
    ) -> None:
        self.db = db
        self.image_dir = image_dir
        self.client = client

    async def refresh(self) -> None:
        if not self._needs_refresh():
            return

        await self._sync_missionaries()
        self.db["last_refresh"] = datetime.now()

    def list(self, offset: int = 0, limit: int = 10):
        missionaries = self.db.get("missionaries", [])
        return missionaries[offset : offset + limit]

    def _needs_refresh(self):
        return (
            datetime.now() - self.db.get("last_refresh", datetime.min)
            > REFRESH_INTERVAL
        )

    async def _sync_missionaries(self):
        album = await self._find_album()
        missionaries = await self._load_missionaries(album)
        current_image_paths = await self._cache_images(missionaries)
        self._clean_up_old_images(current_image_paths)
        self.db["missionaries"] = missionaries

    async def _find_album(self) -> dict:
        albums = await self.client.get_albums()
        for album in albums:
            if album["title"] == "Missionary Board":
                return album
        raise Exception("'Missionary Board' album not found")

    async def _load_missionaries(self, album: dict) -> List[Missionary]:
        media_items = await self.client.get_media_items(album["id"])
        missionaries = [self._parse_media_item(item) for item in media_items]
        # Maybe sort by last name?
        return missionaries

    def _parse_media_item(self, item) -> Missionary:
        data = {
            "image_path": item["filename"],
            "image_base_url": item["baseUrl"],
            "name": "",
            "details": [],
        }
        description = item.get("description", "")
        lines = description.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if not data["name"]:
                data["name"] = line
                continue
            data["details"].append(line)
        return Missionary(**data)

    async def _cache_images(self, missionaries: List[Missionary]) -> set:
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
