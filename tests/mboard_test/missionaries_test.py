"""Tests for the missionaries module."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from mimesis import Generic

from lcr_session.session import LcrSession
from lcr_session.urls import ChurchUrl
from mboard.database import Database
from mboard.missionaries import Missionaries, Missionary

generic = Generic()


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
    assert len(missionaries_items) == 4  # noqa: PLR2004
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

    assert len(db["missionaries"]) == 4  # noqa: PLR2004
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
    assert listed_range[1].sort_name == "Thompson, Mary"
    assert listed_range[2].sort_name == "Thompson, Robert"
    assert listed_range[3].sort_name == "Wilson, Thomas"


def test_parse_lcr_data(
    tmp_path: Path, db: Database, lcr_json_data: list[dict]
) -> None:
    lcr_client = FakeLcrSession()
    missionaries = Missionaries(db, tmp_path, lcr_client)

    data = lcr_json_data[0]  # Thomas Wilson
    missionary = missionaries._parse_lcr_data(data)  # noqa: SLF001

    assert missionary.name == "Elder Thomas Wilson"
    assert missionary.sort_name == "Wilson, Thomas"
    assert "Guatemala Guatemala City East" in missionary.details
    assert "Sego Lily Ward" in missionary.details

    data = lcr_json_data[1]  # Emily Johnson
    missionary = missionaries._parse_lcr_data(data)  # noqa: SLF001

    assert missionary.name == "Sister Emily Johnson"
    assert missionary.sort_name == "Johnson, Emily"
    assert "Brazil Rio de Janeiro South" in missionary.details
    assert "Sego Lily Ward" in missionary.details


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
