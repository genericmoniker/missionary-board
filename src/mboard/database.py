"""Persistence layer for mboard."""
import importlib
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from sqlite3 import Binary

from cryptography.fernet import Fernet
from sqlitedict import SqliteDict  # type: ignore

from mboard.paths import INSTANCE_DIR

_logger = logging.getLogger(__name__)


class Database(SqliteDict):
    """Database for persistent data.

    The database exposes a dict-like interface, and can be used in either async or sync
    code without blocking I/O (since the underlying SqliteDict queues database
    operations to be handled on a separate thread).

    Values can be any JSON-serializable object, including datetime objects, and are
    well-obfuscated using Fernet symmetric encryption.
    """

    def __init__(self, filename=None, key=None):
        data_dir = INSTANCE_DIR
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

        if is_dataclass(o):
            dc_dict = asdict(o)
            cls = o.__class__
            dc_dict["_module_"] = cls.__module__
            dc_dict["_class_"] = cls.__qualname__
            return dc_dict

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
            except ValueError as ex:
                raise ValueError(f"Couldn't deserialize datetime {obj['_dt_']}") from ex

        if "_module_" in obj:
            module_name = obj.pop("_module_")
            class_name = obj.pop("_class_")
            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                return cls(**obj)
            except Exception as ex:
                raise ValueError(
                    f"Couldn't deserialize class {module_name}.{class_name}"
                ) from ex
        return obj
