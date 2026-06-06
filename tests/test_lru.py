# Tests for LRU eviction on DictStore and SqliteStore.
from functools import partial

import pytest

from funes import ConfigError, DictStore, SqliteStore


def make_dict_store(max_size):
    """Build a bounded DictStore context manager."""
    return DictStore(max_size=max_size)


def make_sqlite_store(tmp_path, max_size):
    """Build a bounded SqliteStore context manager backed by a temp file."""
    return SqliteStore(db_path=tmp_path / "lru.db", max_size=max_size)


@pytest.fixture(params=["dict", "sqlite"])
def bounded_store(request, tmp_path):
    """Yield a factory taking max_size and returning a fresh bounded store of each backend."""
    if request.param == "dict":
        return make_dict_store
    return partial(make_sqlite_store, tmp_path)


def test_lru_evicts_oldest_on_overflow(bounded_store):
    """Inserting beyond max_size drops the least-recently-used entry, forcing recompute."""
    calls = []

    def tracked(value):
        calls.append(value)
        return value

    with bounded_store(2) as store:
        store.run(tracked, "a")          # cache: a
        store.run(tracked, "b")          # cache: a, b
        store.run(tracked, "c")          # overflow → evict a; cache: b, c
        store.run(tracked, "b")          # hit
        store.run(tracked, "a")          # a was evicted → recompute

    assert calls == ["a", "b", "c", "a"]


def test_lru_hit_refreshes_recency(bounded_store):
    """A cache hit on the oldest key spares it; the next-oldest is evicted instead."""
    calls = []

    def tracked(value):
        calls.append(value)
        return value

    with bounded_store(2) as store:
        store.run(tracked, "a")          # cache: a
        store.run(tracked, "b")          # cache: a, b
        store.run(tracked, "a")          # hit → a now most-recent; cache: b, a
        store.run(tracked, "c")          # overflow → evict b; cache: a, c
        store.run(tracked, "a")          # hit (a was spared)
        store.run(tracked, "b")          # b was evicted → recompute

    assert calls == ["a", "b", "c", "b"]


INVALID_MAX_SIZE_CASES = [-1, 0]


def test_invalid_max_size_rejected(bounded_store):
    """A non-positive max_size is rejected at construction, not at eviction time."""
    for max_size in INVALID_MAX_SIZE_CASES:
        with pytest.raises(ConfigError):
            bounded_store(max_size)


def test_unbounded_store_never_evicts(bounded_store):
    """max_size=None keeps every entry; no recompute regardless of count."""
    calls = []

    def tracked(value):
        calls.append(value)
        return value

    with bounded_store(None) as store:
        for value in range(10):
            store.run(tracked, value)
        for value in range(10):
            store.run(tracked, value)    # all hits

    assert calls == list(range(10))
