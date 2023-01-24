"""Persistence layer for mboard."""
import json
import logging
from datetime import datetime
from pathlib import Path
from sqlite3 import Binary

from cryptography.fernet import Fernet
from sqlitedict import SqliteDict  # type: ignore

_logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent


class Database(SqliteDict):
    """Database for persistent data.

    The database exposes a dict-like interface, and can be used in either async or sync
    code without blocking I/O (since the underlying SqliteDict queues database
    operations to be handled on a separate thread).

    Values can be any JSON-serializable object, including datetime objects, and are
    well-obfuscated using Fernet symmetric encryption.
    """

    def __init__(self, filename=None, key=None):
        data_dir = ROOT_DIR / "instance"
        self._key = key or self._init_key(data_dir)
        self._fernet = Fernet(self._key)
        super().__init__(
            filename=filename or data_dir / "mboard.db",
            tablename="mboard",
            autocommit=True,
            encode=self._encrypted_json_encoder,
            decode=self._encrypted_json_decoder,
        )

    @staticmethod
    def _init_key(data_dir: Path) -> bytes:
        key_path = data_dir / "mboard.key"
        if key_path.exists():
            key = key_path.read_bytes()
            _logger.debug("Existing database key used at %s", key_path.absolute())
            return key

        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        _logger.debug("New database key created at %s", key_path.absolute())
        return key

    def _encrypted_json_encoder(self, obj: object) -> Binary:
        bytes_ = self._fernet.encrypt(json.dumps(obj, cls=_ExtendedEncoder).encode())
        return Binary(bytes_)

    def _encrypted_json_decoder(self, data: Binary) -> object:
        return json.loads(self._fernet.decrypt(data), cls=_ExtendedDecoder)


class _ExtendedEncoder(json.JSONEncoder):
    """JSON encoder that handles additional object types."""

    def default(self, o):
        if hasattr(o, "isoformat"):
            return {"_dt_": o.isoformat()}

        return json.JSONEncoder.default(self, o)


class _ExtendedDecoder(json.JSONDecoder):
    """JSON decoder that handles additional object types."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs["object_hook"] = self._object_hook
        super().__init__(*args, **kwargs)

    @staticmethod
    def _object_hook(obj):
        if "_dt_" in obj:
            try:
                return datetime.fromisoformat(obj["_dt_"])
            except ValueError:
                pass
        return obj
