"""Missionaries repository."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lcr_session.session import LcrSession
from lcr_session.urls import ChurchUrl
from mboard.database import Database

REFRESH_INTERVAL = timedelta(minutes=2)

logger = logging.getLogger(__name__)


@dataclass
class Missionary:
    """Missionary data."""

    name: str
    sort_name: str
    image_path: str = ""
    image_base_url: str = ""
    details: list[str] = field(default_factory=list)


class Missionaries:
    """Missionaries repository/cache."""

    def __init__(self, db: Database, image_dir: Path, lcr_session: LcrSession) -> None:
        """Initialize the missionary repository."""
        self.db = db
        self.image_dir = image_dir
        self.lcr_session = lcr_session

    @staticmethod
    def clear(db: Database) -> None:
        """Clear the missionaries from the database."""
        db.pop("missionaries", None)
        db.pop("last_refresh", None)
        db.pop("refresh_error", None)

    async def refresh(self) -> None:
        """Refresh the cache of missionaries from LCR."""
        if not self._needs_refresh():
            return

        try:
            await self._sync_missionaries()
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {e}"
            last_refresh = self.db.get("last_refresh")
            last_refresh = str(last_refresh) if last_refresh else "(never)"
            logger.error(  # noqa: TRY400
                "Error synchronizing missionaries: %s. Last sync was %s",
                error,
                last_refresh,
            )
            self.db["refresh_error"] = error
        else:
            self.db.pop("refresh_error", None)
            self.db["last_refresh"] = datetime.now(tz=UTC)

    def list_range(
        self,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[list[Missionary], int]:
        """List the missionaries.

        Returns a tuple of the list of missionaries and the offset of the next
        range of results.
        """
        try:
            missionaries = self.db.get("missionaries", [])
        except (TypeError, ValueError):
            return [], 0
        next_offset = offset + limit if offset + limit < len(missionaries) else 0
        return missionaries[offset : offset + limit], next_offset

    def get_refresh_error(self) -> str:
        """Get the error that occurred during the last refresh.

        Return an empty string if there was no error.
        """
        return self.db.get("refresh_error", "")

    def _needs_refresh(self) -> bool:
        now = datetime.now(tz=UTC)
        last_refresh = self.db.get("last_refresh", datetime.min).replace(
            tzinfo=UTC,
        )
        return now - last_refresh > REFRESH_INTERVAL

    async def _sync_missionaries(self) -> None:
        url = ChurchUrl(
            "lcr", "api/orgs/full-time-missionaries?lang=eng&unitNumber={parent_unit}"
        )
        missionaries_data = await self.lcr_session.get_json(url)
        missionaries = [self._parse_lcr_data(item) for item in missionaries_data]
        self.db["missionaries"] = sorted(missionaries, key=lambda m: m.sort_name)

    def _parse_lcr_data(self, item: dict) -> Missionary:
        """Parse missionary data from LCR API response."""
        sort_name = item.get("missionaryName")
        if not sort_name:
            # Some missionaries have no name, so we skip them.
            logger.warning("Placeholder for missionary with no name: %s", item)
            return Missionary(name="", sort_name="")
        display_name = sort_name.split(", ")[::-1]
        display_name = " ".join(display_name)
        gender = item.get("member", {}).get("gender")
        if gender == "FEMALE":
            display_name = f"Sister {display_name}"
        elif gender == "MALE":
            display_name = f"Elder {display_name}"

        # Dates look like "20230814"
        start = ""
        start_date_iso = item.get("startDate")
        if start_date_iso:
            start_date = datetime.strptime(start_date_iso, "%Y%m%d").astimezone()
            start = start_date.strftime("%b %Y")  # "Aug 2023"
        end = ""
        end_date_iso = item.get("endDate")
        if end_date_iso:
            end_date = datetime.strptime(end_date_iso, "%Y%m%d").astimezone()
            end = end_date.strftime("%b %Y")
        dates_serving = f"{start} - {end}" if start and end else ""

        return Missionary(
            name=display_name,
            sort_name=sort_name,
            details=[
                item.get("missionName", ""),
                dates_serving,
                item.get("missionaryHomeUnitName", ""),
            ],
        )

    @staticmethod
    def _format_image_path(item: dict) -> str:
        full_filename = Path(item["filename"])
        filename = full_filename.stem
        extension = full_filename.suffix
        # Include the dimensions in the name to re-download if the image is cropped.
        width = item["mediaMetadata"]["width"]
        height = item["mediaMetadata"]["height"]
        return f"{filename}_{width}x{height}{extension}"

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
