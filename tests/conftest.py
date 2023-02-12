import sqlitedict
from pytest import fixture
from starlette.testclient import TestClient
from mboard.main import create_app


@fixture
def db():
    return sqlitedict.SqliteDict(":memory:")


@fixture
def client(db):
    app = create_app()
    app.state.db = db
    return TestClient(app)
