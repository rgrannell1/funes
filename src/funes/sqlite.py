"""SqliteStore: durable IStore backed by SQLite in WAL mode."""

import pickle
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from funes.funes_types import Miss, StoreError
from funes.policy import always
from funes.protocol import IStore, default_key

# milliseconds SQLite waits for a lock before raising OperationalError
_BUSY_TIMEOUT_MS = 5000

_CREATE = "CREATE TABLE IF NOT EXISTS memo (key BLOB PRIMARY KEY, value BLOB)"
_SELECT = "SELECT value FROM memo WHERE key = ?"
_UPSERT = "INSERT OR REPLACE INTO memo (key, value) VALUES (?, ?)"
_DELETE = "DELETE FROM memo WHERE key = ?"


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(_CREATE)
    return conn


@dataclass(kw_only=True)
class SqliteStore[Key, Value](IStore):
    """A SQLite IStore backed by a SQLite database."""

    db_path: str | Path
    key: Callable = field(default=default_key)
    should_store: Callable = field(default=always)
    hits: int = field(default=0)
    misses: int = field(default=0)
    _conn: sqlite3.Connection | None = field(default=None, init=False, repr=False)

    def __enter__(self):
        """Enter the context manager."""

        self._conn = _connect(str(self.db_path))
        return self

    def __exit__(self, *_exc):
        """Exit the context manager."""

        if self._conn:
            self._conn.close()
            self._conn = None
        return False

    def get(self, key: Key) -> Value | Miss:
        """Get a value from the store."""

        if self._conn is None:
            raise StoreError("get called outside with block")
        cursor = self._conn.execute(_SELECT, (pickle.dumps(key),))
        row = cursor.fetchone()
        return Miss.MISS if row is None else pickle.loads(row[0])  # noqa: S301

    def set(self, key: Key, value: Value) -> None:
        """Set a value in the store."""

        if self._conn is None:
            raise StoreError("set called outside with block")
        self._conn.execute(_UPSERT, (pickle.dumps(key), pickle.dumps(value)))

    def delete(self, key: Key) -> None:
        """Delete a cached value by key."""

        if self._conn is None:
            raise StoreError("delete called outside with block")
        self._conn.execute(_DELETE, (pickle.dumps(key),))
