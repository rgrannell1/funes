"""SqliteStore: durable IStore backed by SQLite in WAL mode."""

import pickle
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from funes.funes_types import CacheEntry, Miss, StoreError
from funes.policy import always
from funes.protocol import IStore, default_key, validate_max_size

# milliseconds SQLite waits for a lock before raising OperationalError
_BUSY_TIMEOUT_MS = 5000

# seq orders entries by recency: a higher seq means more-recently-used
_CREATE = "CREATE TABLE IF NOT EXISTS memo (key BLOB PRIMARY KEY, value BLOB, seq INTEGER)"
_SELECT = "SELECT value FROM memo WHERE key = ?"
_UPSERT = "INSERT OR REPLACE INTO memo (key, value, seq) VALUES (?, ?, ?)"
_DELETE = "DELETE FROM memo WHERE key = ?"
_TOUCH = "UPDATE memo SET seq = ? WHERE key = ?"
_MAX_SEQ = "SELECT COALESCE(MAX(seq), 0) FROM memo"
_COUNT = "SELECT COUNT(*) FROM memo"
# deletes the N least-recently-used rows (smallest seq first)
_EVICT_LRU = "DELETE FROM memo WHERE seq IN (SELECT seq FROM memo ORDER BY seq ASC LIMIT ?)"


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
    """A SQLite IStore backed by a SQLite database.

    When max_size is set, the store keeps at most that many entries, evicting the
    least-recently-used key on insertion. max_size=None leaves the store unbounded.
    """

    db_path: str | Path
    key: Callable = field(default=default_key)
    should_store: Callable = field(default=always)
    # None means unbounded; a positive int caps entry count and enables LRU eviction
    max_size: int | None = field(default=None)
    hits: int = field(default=0)
    misses: int = field(default=0)
    _conn: sqlite3.Connection | None = field(default=None, init=False, repr=False)
    # monotonic recency counter, seeded from the table's max seq on enter
    _seq: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        validate_max_size(self.max_size)

    def __enter__(self):
        """Enter the context manager."""

        self._conn = _connect(str(self.db_path))
        self._seq = self._conn.execute(_MAX_SEQ).fetchone()[0]
        return self

    def next_seq(self) -> int:
        """Return the next recency sequence number."""

        self._seq += 1
        return self._seq

    def __exit__(self, *_exc):
        """Exit the context manager."""

        if self._conn:
            self._conn.close()
            self._conn = None
        return False

    def get(self, key: tuple[str, Key]) -> CacheEntry | Miss:
        """Get a value from the store, marking the key most-recently-used on a hit."""

        if self._conn is None:
            raise StoreError("get called outside with block")
        key_blob = pickle.dumps(key)
        row = self._conn.execute(_SELECT, (key_blob,)).fetchone()
        if row is None:
            return Miss.MISS
        # a read marks the key most-recently-used — only matters when bounded
        if self.max_size is not None:
            self._conn.execute(_TOUCH, (self.next_seq(), key_blob))
        return pickle.loads(row[0])

    def set(self, key: tuple[str, Key], value: CacheEntry) -> None:
        """Set a value in the store, evicting the least-recently-used entry if over capacity."""

        if self._conn is None:
            raise StoreError("set called outside with block")
        params = (pickle.dumps(key), pickle.dumps(value), self.next_seq())
        self._conn.execute(_UPSERT, params)
        self.evict_lru()

    def evict_lru(self) -> None:
        """Drop least-recently-used rows until the table fits max_size."""

        if self.max_size is None or self._conn is None:
            return
        count = self._conn.execute(_COUNT).fetchone()[0]
        excess = count - self.max_size
        if excess > 0:
            self._conn.execute(_EVICT_LRU, (excess,))

    def delete(self, key: tuple[str, Key]) -> None:
        """Delete a cached value by key."""

        if self._conn is None:
            raise StoreError("delete called outside with block")
        self._conn.execute(_DELETE, (pickle.dumps(key),))
