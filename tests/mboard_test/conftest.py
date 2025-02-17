"""Pytest fixtures for the mboard package."""

import httpx
import pytest
import sqlitedict
from starlette.testclient import TestClient

from mboard.database import Database
from mboard.main import create_app


@pytest.fixture
def db() -> Database:
    return sqlitedict.SqliteDict(":memory:")


@pytest.fixture
def client(db: Database) -> httpx.Client:
    app = create_app()
    app.state.db = db
    return TestClient(app)
