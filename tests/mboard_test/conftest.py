"""Pytest fixtures for the mboard package."""

from collections.abc import Generator

import pytest
import sqlitedict
from starlette.testclient import TestClient

from mboard.database import Database
from mboard.main import create_app


@pytest.fixture
def db() -> Database:
    return sqlitedict.SqliteDict(":memory:")


@pytest.fixture
def client(db: Database) -> Generator[TestClient, None, None]:
    app = create_app()
    app.state.db = db
    with TestClient(app) as test_client:
        yield test_client
