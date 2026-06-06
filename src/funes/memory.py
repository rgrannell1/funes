"""DictStore: in-memory IStore backed by an ordered dict with optional LRU eviction."""

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from funes.funes_types import CacheEntry, Miss
from funes.policy import always
from funes.protocol import IStore, default_key, validate_max_size


@dataclass(kw_only=True)
class DictStore[Key, Value](IStore):
    """An in-memory IStore backed by an ordered dict.

    When max_size is set, the store keeps at most that many entries, evicting the
    least-recently-used key on insertion. max_size=None leaves the store unbounded.
    """

    key: Callable = field(default=default_key)
    should_store: Callable = field(default=always)
    # None means unbounded; a positive int caps entry count and enables LRU eviction
    max_size: int | None = field(default=None)
    table: OrderedDict = field(default_factory=OrderedDict)
    hits: int = field(default=0)
    misses: int = field(default=0)

    def __post_init__(self) -> None:
        validate_max_size(self.max_size)

    def get(self, key: tuple[str, Key]) -> CacheEntry | Miss:
        if key not in self.table:
            return Miss.MISS
        # a read marks the key most-recently-used — only matters when bounded
        if self.max_size is not None:
            self.table.move_to_end(key)
        return self.table[key]

    def set(self, key: tuple[str, Key], value: CacheEntry) -> None:
        self.table[key] = value
        self.table.move_to_end(key)
        self.evict_lru()

    def evict_lru(self) -> None:
        """Drop least-recently-used entries until the store fits max_size."""

        if self.max_size is None:
            return
        while len(self.table) > self.max_size:
            self.table.popitem(last=False)

    def delete(self, key: tuple[str, Key]) -> None:
        self.table.pop(key, None)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False
