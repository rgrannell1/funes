"""DictStore: in-memory IStore backed by a plain dict"""

from collections.abc import Callable
from dataclasses import dataclass, field

from funes.funes_types import Miss
from funes.policy import always
from funes.protocol import IStore, default_key


@dataclass(kw_only=True)
class DictStore[Key, Value](IStore):
    """An in-memory IStore backed by a plain dict."""

    key: Callable = field(default=default_key)
    should_store: Callable = field(default=always)
    table: dict = field(default_factory=dict)
    hits: int = field(default=0)
    misses: int = field(default=0)

    def get(self, key: Key) -> Value | Miss:
        return self.table.get(key, Miss.MISS)

    def set(self, key: Key, value: Value) -> None:
        self.table[key] = value

    def delete(self, key: Key) -> None:
        self.table.pop(key, None)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False
