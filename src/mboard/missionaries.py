"""Missionaries repository."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lcr_session.session import LcrSession
from lcr_session.urls import ChurchUrl
from mboard.database import Database

REFRESH_INTERVAL = timedelta(minutes=2)
SENIOR_AGE = 40

logger = logging.getLogger(__name__)


@dataclass
class Missionary:
    """Missionary data."""

    id: int = 0
    name: str = ""
    sort_name: str = ""
    gender: str = ""
    senior: bool = False
    mission: str = ""
    dates_serving: str = ""
    home_unit: str = ""
    image_path: str = ""
    image_base_url: str = ""

    def __eq__(self, other: object) -> bool:
        """Check if two missionaries are equal based on their IDs."""
        if not isinstance(other, Missionary):
            return NotImplemented
        return self.id == other.id


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
        logger.info("LCR missionaries: %d", len(missionaries_data))
        missionaries = [
            self._parse_lcr_data(missionary_data)
            for missionary_data in missionaries_data
            if self._filter(missionary_data)
        ]
        missionaries = self._merge_couple_missionaries(missionaries)
        missionaries = sorted(missionaries, key=lambda m: m.sort_name)
        self.db["missionaries"] = missionaries
        logger.info("Saved missionaries: %d", len(missionaries))

    def _parse_lcr_data(self, missionary_data: dict) -> Missionary:
        """Parse missionary data from LCR API response."""
        sort_name = missionary_data.get("missionaryName", "")
        display_name = sort_name.split(", ")[::-1]
        display_name = " ".join(display_name)
        gender = missionary_data.get("member", {}).get("gender")
        if gender == "FEMALE":
            display_name = f"Sister {display_name}"
        elif gender == "MALE":
            display_name = f"Elder {display_name}"

        # Dates look like "20230814"
        start = ""
        start_date_iso = missionary_data.get("startDate")
        if start_date_iso:
            start_date = datetime.strptime(start_date_iso, "%Y%m%d").astimezone()
            start = start_date.strftime("%b %Y")  # "Aug 2023"
        end = ""
        end_date_iso = missionary_data.get("endDate")
        if end_date_iso:
            end_date = datetime.strptime(end_date_iso, "%Y%m%d").astimezone()
            end = end_date.strftime("%b %Y")
        dates_serving = f"{start} - {end}" if start and end else ""

        # Sometimes "seniorMissionary" is not set, fall back to an age check.
        senior = missionary_data.get("seniorMissionary")
        if not senior:
            birth_date = missionary_data.get("member", {}).get("birthDate")
            if birth_date:
                # Birth date is in the format "YYYYMMDD"
                birth_date = datetime.strptime(birth_date, "%Y%m%d").astimezone()
                age = (datetime.now(UTC) - birth_date).days // 365
                senior = age > SENIOR_AGE
            else:
                senior = False  # Default to False if no birth date is available

        return Missionary(
            id=missionary_data.get("missionaryIndividualId", 0),
            name=display_name,
            sort_name=sort_name,
            gender=gender,
            senior=senior,
            mission=missionary_data.get("missionName", ""),
            dates_serving=dates_serving,
            home_unit=missionary_data.get("missionaryHomeUnitName", ""),
        )

    def _filter(self, missionary_data: dict) -> bool:
        """Filter missionaries to include."""
        # We expect missionaries to have a name, but just for safety, check for it now
        # because we count on it later.
        if not missionary_data.get("missionaryName"):
            return False
        # Filter out missionaries who are not currently serving.
        return missionary_data.get("status") == "SERVING"

    def _merge_couple_missionaries(
        self, missionaries: list[Missionary]
    ) -> list[Missionary]:
        """Merge couple missionaries into one entry."""
        result_missionaries = []
        merged_ids = set()
        for missionary in missionaries:
            if missionary.id in merged_ids:
                continue
            if missionary.senior:
                companion = next(
                    (
                        m
                        for m in missionaries
                        if m.senior
                        and m != missionary
                        and m.gender != missionary.gender
                        and m.mission == missionary.mission
                        and m.home_unit == missionary.home_unit
                        and m.dates_serving == missionary.dates_serving
                    ),
                    None,
                )
                if companion:
                    merged_ids.add(companion.id)
                    if missionary.gender == "MALE":
                        elder = self._omit_last_name(missionary.name)
                        missionary.name = f"{elder} & {companion.name}"
                    else:
                        elder = self._omit_last_name(companion.name)
                        missionary.name = f"{elder} & {missionary.name}"
                        missionary.sort_name = companion.sort_name
                    logger.info("Merged couple: %s", missionary.name)
            result_missionaries.append(missionary)
        return result_missionaries

    @staticmethod
    def _omit_last_name(name: str) -> str:
        """Omit the last name from a display name.

        Elder John Smith -> Elder John
        """
        split_name = name.split()
        return " ".join(split_name[:-1])

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
