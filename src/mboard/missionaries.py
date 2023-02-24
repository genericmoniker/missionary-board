"""Missionaries repository."""
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    ward: str = ""
    mission: str = ""
    start: str = ""
    end: str = ""


class Missionaries:
    """Missionaries repository/cache."""

    def __init__(
        self, db: Database, image_dir: Path, client: GooglePhotosClient
    ) -> None:
        self.db = db
        self.image_dir = image_dir
        self.client = client

    async def refresh(self):
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
        albums = await self.client.get_albums()
        for album in albums:
            if album["title"] == "Missionary Board":
                break
        else:
            raise Exception("Missionary Board album not found")

        media_items = await self.client.get_media_items(album["id"])
        missionaries = [self._parse_media_item(item) for item in media_items]
        for missionary in missionaries:
            image_path = self.image_dir / missionary.image_path
            if not image_path.exists():
                image_data = await self.client.download(missionary.image_base_url)
                image_path.write_bytes(image_data)
        # Maybe sort by last name?
        self.db["missionaries"] = missionaries

    def _parse_media_item(self, item):
        data = {
            "image_path": item["filename"],
            "image_base_url": item["baseUrl"],
        }
        description = item.get("description", "").strip()
        lines = description.splitlines()
        for line in lines:
            key, value = line.split(":", 1)
            data[key.lower().strip()] = value.strip()
        return Missionary(**data)
