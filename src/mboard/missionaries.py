"""Missionaries repository."""

import logging
from dataclasses import asdict, dataclass
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

    def __eq__(self, other: object) -> bool:
        """Check if two missionaries are equal based on their IDs."""
        if not isinstance(other, Missionary):
            return NotImplemented
        return self.id == other.id


class Missionaries:
    """Missionaries repository/cache."""

    def __init__(self, db: Database, photos_dir: Path, lcr_session: LcrSession) -> None:
        """Initialize the missionary repository."""
        self.db = db
        self.photos_dir = photos_dir
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
            self._photo_only_refresh()
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

    def _photo_only_refresh(self) -> None:
        """Refresh only the photos of the missionaries.

        This is used when the missionaries are already in the database, but we want to
        update their photos.
        """
        missionaries = self.db.get("missionaries", [])
        for missionary in missionaries:
            image_path = self._find_photo(missionary.id)
            if image_path != missionary.image_path:
                logger.info("Photo found for %s (%s)", missionary.id, missionary.name)
                missionary.image_path = image_path
        self.db["missionaries"] = missionaries

    async def _sync_missionaries(self) -> None:
        url = ChurchUrl(
            "lcr", "api/orgs/full-time-missionaries?lang=eng&unitNumber={parent_unit}"
        )
        missionaries_data = await self.lcr_session.get_json(url)
        logger.info("LCR missionaries: %d", len(missionaries_data))
        missionaries = [
            self._create_missionary(missionary_data)
            for missionary_data in missionaries_data
            if self._filter(missionary_data)
        ]
        total = len(missionaries)
        missionaries = self._merge_couple_missionaries(missionaries)
        potential_photos = len(missionaries)
        missionaries = sorted(missionaries, key=lambda m: m.sort_name)
        with_photo = [m for m in missionaries if m.image_path]
        without_photo = [m for m in missionaries if not m.image_path]
        for missionary in without_photo:
            logger.info("No photo: %s (%s)", missionary.id, missionary.name)
        photo_percent = (
            len(with_photo) / potential_photos * 100 if potential_photos else 0
        )
        self.db["missionaries"] = missionaries
        logger.info("Missionary count: %d (%.0f%% with photo)", total, photo_percent)

    def _create_missionary(self, missionary_data: dict) -> Missionary:
        """Create a missionary data from LCR API response and photos."""
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
                senior = False  # Default to False if no birth date is available.

        # Look for a photo.
        missionary_id = missionary_data.get("missionaryIndividualId", 0)
        image_path = self._find_photo(missionary_id)

        return Missionary(
            id=missionary_id,
            name=display_name,
            sort_name=sort_name,
            gender=gender,
            senior=senior,
            mission=missionary_data.get("missionName", ""),
            dates_serving=dates_serving,
            home_unit=missionary_data.get("missionaryHomeUnitName", ""),
            image_path=image_path,
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
                        # If this is the Elder, update the name to include the Sister.
                        elder = self._omit_last_name(missionary.name)
                        missionary.name = f"{elder} & {companion.name}"
                    else:
                        # If the Sister, save the name and copy the Elder's data.
                        elder = self._omit_last_name(companion.name)
                        name = f"{elder} & {missionary.name}"
                        for key, value in asdict(companion).items():
                            setattr(missionary, key, value)
                        missionary.name = name
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

    def _find_photo(self, missionary_id: int) -> str:
        """Find a photo for the missionary with the given id.

        The filename should start with the missionary ID and may optionally be followed
        by anything else, such as their name, to make managing the photos easier.

        Returns the filename of the photo if found, otherwise an empty string.
        """
        try:
            photo = next(self.photos_dir.glob(f"{missionary_id}*"))
            return photo.name
        except StopIteration:
            return ""
