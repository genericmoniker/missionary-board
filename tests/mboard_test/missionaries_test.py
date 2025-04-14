"""Tests for the missionaries module."""

# ruff: noqa: FBT003 SLF001 PLR2004
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from lcr_session.session import LcrSession
from lcr_session.urls import ChurchUrl
from mboard.database import Database
from mboard.missionaries import Missionaries, Missionary


class FakeLcrSession(LcrSession):
    """A fake LCR session for testing - minimal version with just what's needed."""

    def __init__(self) -> None:
        """Initialize with minimal setup."""
        self.missionaries_data = []
        self.get_json_called = False

    async def get_json(self, url: str | ChurchUrl, **kwargs) -> Any:  # noqa: ANN401, ARG002
        """Mock the get_json method to return our test missionary data."""
        self.get_json_called = True
        return self.missionaries_data


@pytest.fixture
def lcr_json_data() -> list[dict]:
    """Load the test missionaries data from the JSON file."""
    json_path = Path(__file__).parent / "lcr.json"
    with json_path.open() as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_refresh_skipped_if_not_needed(tmp_path: Path, db: Database) -> None:
    db["last_refresh"] = datetime.now(tz=UTC)
    lcr_client = FakeLcrSession()
    missionaries = Missionaries(db, tmp_path, lcr_client)

    await missionaries.refresh()

    assert not lcr_client.get_json_called


@pytest.mark.asyncio
async def test_refresh_gets_new_missionary_data(
    tmp_path: Path, db: Database, lcr_json_data: list[dict]
) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    lcr_client = FakeLcrSession()
    lcr_client.missionaries_data = lcr_json_data
    missionaries = Missionaries(db, tmp_path, lcr_client)

    await missionaries.refresh()

    assert lcr_client.get_json_called
    missionaries_items, next_offset = missionaries.list_range(0, 4)
    assert missionaries_items
    assert len(missionaries_items) == 3  # 2 young missionaries and 1 senior couple
    assert next_offset == 0


@pytest.mark.asyncio
async def test_refresh_updates_missionary_data(
    tmp_path: Path, db: Database, lcr_json_data: list[dict]
) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    db["missionaries"] = [Missionary(name="Sister Jones", sort_name="Jones, Sister")]
    lcr_client = FakeLcrSession()
    lcr_client.missionaries_data = lcr_json_data
    missionaries = Missionaries(db, tmp_path, lcr_client)

    await missionaries.refresh()

    assert len(db["missionaries"]) == 3  # 2 young missionaries and 1 senior couple
    assert (
        "Wilson" in db["missionaries"][0].name
        or "Johnson" in db["missionaries"][0].name
        or "Thompson" in db["missionaries"][0].name
    )


@pytest.mark.asyncio
async def test_missionaries_sorted_by_name(
    tmp_path: Path, db: Database, lcr_json_data: list[dict]
) -> None:
    db["last_refresh"] = datetime.min.replace(tzinfo=UTC)
    lcr_client = FakeLcrSession()
    lcr_client.missionaries_data = lcr_json_data
    missionaries = Missionaries(db, tmp_path, lcr_client)

    await missionaries.refresh()
    listed_range, _ = missionaries.list_range(0, 10)

    assert listed_range[0].sort_name == "Johnson, Emily"
    assert listed_range[1].sort_name == "Thompson, Robert"
    assert listed_range[2].sort_name == "Wilson, Thomas"


def test_parse_lcr_data(
    tmp_path: Path, db: Database, lcr_json_data: list[dict]
) -> None:
    missionaries = Missionaries(db, tmp_path, FakeLcrSession())

    data = lcr_json_data[0]  # Thomas Wilson
    missionary = missionaries._parse_lcr_data(data)
    assert missionary.id == 87654321098
    assert missionary.name == "Elder Thomas Wilson"
    assert missionary.sort_name == "Wilson, Thomas"
    assert missionary.gender == "MALE"
    assert missionary.senior is False
    assert missionary.mission == "Guatemala Guatemala City East"
    assert missionary.home_unit == "Sego Lily Ward"

    data = lcr_json_data[1]  # Emily Johnson
    missionary = missionaries._parse_lcr_data(data)
    assert missionary.id == 76543210987
    assert missionary.name == "Sister Emily Johnson"
    assert missionary.sort_name == "Johnson, Emily"
    assert missionary.gender == "FEMALE"
    assert missionary.senior is False
    assert missionary.mission == "Brazil Rio de Janeiro South"
    assert missionary.home_unit == "Sego Lily Ward"

    data = lcr_json_data[2]  # Robert Thompson
    missionary = missionaries._parse_lcr_data(data)
    assert missionary.id == 12345678910
    assert missionary.name == "Elder Robert Thompson"
    assert missionary.sort_name == "Thompson, Robert"
    assert missionary.gender == "MALE"
    assert missionary.senior is True
    assert missionary.mission == "Philippines Cebu"
    assert missionary.home_unit == "Maple Grove Ward"


def test_parse_missing_senior_value(
    tmp_path: Path, db: Database, lcr_json_data: list[dict]
) -> None:
    """If seniorMissionary value is missing, fall back to an age check."""
    missionaries = Missionaries(db, tmp_path, FakeLcrSession())

    data = lcr_json_data[1]  # young Emily Johnson
    data["seniorMissionary"] = None
    missionary = missionaries._parse_lcr_data(data)
    assert missionary.senior is False

    data = lcr_json_data[2]  # senior Robert Thompson
    data["seniorMissionary"] = None
    missionary = missionaries._parse_lcr_data(data)
    assert missionary.senior is True


@pytest.mark.parametrize(
    ("missionaries_data", "expected_names"),
    [
        # Male missionary's sort name is first
        (
            [
                Missionary(
                    id=0,
                    name="Elder A Ng",
                    sort_name="Ng, A",
                    gender="MALE",
                    senior=True,
                    mission="Mission",
                    home_unit="Unit",
                ),
                Missionary(
                    id=1,
                    name="Sister B Ng",
                    sort_name="Ng, B",
                    gender="FEMALE",
                    senior=True,
                    mission="Mission",
                    home_unit="Unit",
                ),
            ],
            "Elder A Ng & Sister B Ng",
        ),
        # Male missionary's sort name is second
        (
            [
                Missionary(
                    id=1,
                    name="Elder B Ng",
                    sort_name="Ng, B",
                    gender="MALE",
                    senior=True,
                    mission="Mission",
                    home_unit="Unit",
                ),
                Missionary(
                    id=0,
                    name="Sister A Ng",
                    sort_name="Ng, A",
                    gender="FEMALE",
                    senior=True,
                    mission="Mission",
                    home_unit="Unit",
                ),
            ],
            "Elder B Ng & Sister A Ng",
        ),
    ],
)
def test_merge_couple(
    tmp_path: Path,
    db: Database,
    missionaries_data: list[Missionary],
    expected_names: str,
) -> None:
    """Couples are merged into one entry, with the Elder's name first."""
    missionaries = Missionaries(db, tmp_path, FakeLcrSession())

    result = missionaries._merge_couple_missionaries(missionaries_data)

    assert len(result) == 1
    assert result[0].name == expected_names


@pytest.mark.parametrize(
    "missionaries_data",
    [
        # Siblings different missions
        [
            Missionary(
                id=0,
                name="Elder A Ng",
                sort_name="Ng, A",
                gender="MALE",
                senior=True,
                mission="Mission1",
                home_unit="Unit",
                dates_serving="Mar 2025 - Sep 2026",
            ),
            Missionary(
                id=1,
                name="Sister B Ng",
                sort_name="Ng, B",
                gender="FEMALE",
                senior=True,
                mission="Mission2",
                home_unit="Unit",
                dates_serving="Mar 2025 - Sep 2026",
            ),
        ],
        # Siblings different wards
        [
            Missionary(
                id=0,
                name="Elder A Ng",
                sort_name="Ng, A",
                gender="MALE",
                senior=True,
                mission="Mission",
                home_unit="Unit1",
                dates_serving="Mar 2025 - Mar 2027",
            ),
            Missionary(
                id=1,
                name="Sister B Ng",
                sort_name="Ng, B",
                gender="FEMALE",
                senior=True,
                mission="Mission",
                home_unit="Unit2",
                dates_serving="Mar 2025 - Sep 2026",
            ),
        ],
        # Twins called to the same mission
        [
            Missionary(
                id=0,
                name="Sister A Ng",
                sort_name="Ng, A",
                gender="FEMALE",
                senior=True,
                mission="Mission",
                home_unit="Unit",
                dates_serving="Mar 2025 - Sep 2026",
            ),
            Missionary(
                id=1,
                name="Sister B Ng",
                sort_name="Ng, B",
                gender="FEMALE",
                senior=True,
                mission="Mission",
                home_unit="Unit",
                dates_serving="Mar 2025 - Sep 2026",
            ),
        ],
        # Fraternal twins called to the same mission
        [
            Missionary(
                id=0,
                name="Elder A Ng",
                sort_name="Ng, A",
                gender="MALE",
                senior=True,
                mission="Mission",
                home_unit="Unit",
                dates_serving="Mar 2025 - Mar 2027",
            ),
            Missionary(
                id=1,
                name="Sister B Ng",
                sort_name="Ng, B",
                gender="FEMALE",
                senior=True,
                mission="Mission",
                home_unit="Unit",
                dates_serving="Mar 2025 - Sep 2026",
            ),
        ],
    ],
)
def test_merge_non_couple_cases(
    tmp_path: Path, db: Database, missionaries_data: list[Missionary]
) -> None:
    """Missionaries are not merged if they are not a couple."""
    missionaries = Missionaries(db, tmp_path, FakeLcrSession())
    result = missionaries._merge_couple_missionaries(missionaries_data)
    assert len(result) == 2


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
    db["missionaries"] = [
        Missionary(name=f"Mary Jones {i}", sort_name=f"Jones, Mary {i}")
        for i in range(count)
    ]
    lcr_client = FakeLcrSession()
    missionaries = Missionaries(db, tmp_path, lcr_client)

    missionaries_items, next_offset = missionaries.list_range(offset, limit)

    assert missionaries_items if count else not missionaries_items
    assert next_offset == expected_next_offset
