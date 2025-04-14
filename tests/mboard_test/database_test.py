"""Tests for the database module."""

from datetime import UTC, datetime

from cryptography.fernet import Fernet

from mboard.database import Database
from mboard.missionaries import Missionary


def test_database_round_trip() -> None:
    db = Database(":memory:", Fernet.generate_key())
    test_data = [
        # Some JSON serializable data:
        ("str", "Some text 🦸‍♀️"),
        ("list", [1, 2, 3, 4, 5, True, False]),
        ("dict", {"one": 1, "two": 2, "three": 3, "hero": "🦸‍♂️"}),
        # Special handling for datetime:
        ("now", datetime.now(tz=UTC)),
        # Special handling for dataclasses:
        (
            "dataclass",
            Missionary(
                id=1,
                name="John Doe",
                sort_name="Doe, John",
                gender="MALE",
                senior=False,
                mission="Mission",
                dates_serving="Jun-Jul",
                home_unit="1st Ward",
            ),
        ),
    ]
    for key, item in test_data:
        db[key] = item

    for key, item in test_data:
        assert db[key] == item
