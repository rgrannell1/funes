"""IStore protocol and key functions."""

import inspect
import time
from collections.abc import Callable, Generator
from typing import Any, Protocol, Self, runtime_checkable

from funes.funes_types import CacheEntry, ConfigError, Miss


def resolve_ttl(
    ttl_seconds: float | None,
    ttl_minutes: float | None,
    ttl_hours: float | None,
) -> float | None:
    """Convert mutually exclusive ttl_* args to a duration in seconds, or None."""

    provided = [val for val in (ttl_seconds, ttl_minutes, ttl_hours) if val is not None]
    if len(provided) > 1:
        raise ConfigError("only one of ttl_seconds, ttl_minutes, ttl_hours may be set")

    if ttl_seconds is not None:
        return float(ttl_seconds)

    if ttl_minutes is not None:
        return ttl_minutes * 60.0

    if ttl_hours is not None:
        return ttl_hours * 3600.0
    return None


def fn_id(fn: Callable) -> str:
    """Stable namespace key for a function or callable."""

    return getattr(fn, '__qualname__', type(fn).__qualname__)


def default_key(*args, **kwargs):
    """The default way we compute a cache key."""

    if not kwargs:
        return args

    return (args, tuple(sorted(kwargs.items())))


@runtime_checkable
class IStore[Key, Value](Protocol):
    """The key storage interface into funes."""

    # key is a function that takes the args and kwargs and returns a cache key
    key: Callable[..., Key]

    # should_store is a predicate that determines if a value should be stored
    should_store: Callable[[Value], bool]

    hits: int
    misses: int

    def get(self, key: Key) -> Value | Miss:
        ...

    def set(self, key: Key, value: Value) -> None:
        ...

    def delete(self, key: Key) -> None:
        ...

    def __enter__(self) -> Self:
        ...

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        ...

    def __call__(
        self,
        fn: Callable,
        *args: Any,
        bypass: bool = False,
        ttl_seconds: float | None = None,
        ttl_minutes: float | None = None,
        ttl_hours: float | None = None,
        **kwargs: Any,
    ) -> Generator[Any, Any, Value]:

        ttl = resolve_ttl(ttl_seconds, ttl_minutes, ttl_hours)

        # namespace by function so two fns with identical args don't collide
        cache_key = (fn_id(fn), self.key(*args, **kwargs))
        entry = self.get(cache_key)
        has_valid_entry = False
        if entry is not Miss.MISS:
            not_expired = entry.expires_at is None or time.time() < entry.expires_at
            has_valid_entry = not_expired

        if has_valid_entry and not bypass:
            self.hits += 1
            return entry.value

        # only count a true miss — bypass of a valid entry is neither hit nor miss
        if not has_valid_entry:
            self.misses += 1
        result = fn(*args, **kwargs)
        value = (yield from result) if inspect.isgenerator(result) else result

        if self.should_store(value):
            expires_at = time.time() + ttl if ttl is not None else None
            self.set(cache_key, CacheEntry(value=value, expires_at=expires_at))
        elif entry is not Miss.MISS:
            # expired entry whose recomputed value shouldn't be stored — evict
            # rather than leave a stale entry that triggers recompute every call
            self.delete(cache_key)

        return value

    def run(
        self,
        fn: Callable,
        *args: Any,
        bypass: bool = False,
        ttl_seconds: float | None = None,
        ttl_minutes: float | None = None,
        ttl_hours: float | None = None,
        **kwargs: Any,
    ) -> Value:
        """Run fn synchronously, caching the result. Any effects yielded by fn are discarded;
        use `yield from store(fn, *args)` inside a generator program to preserve them."""

        gen = self(
            fn,
            *args,
            bypass=bypass,
            ttl_seconds=ttl_seconds,
            ttl_minutes=ttl_minutes,
            ttl_hours=ttl_hours,
            **kwargs,
        )
        try:
            while True:
                next(gen)
        except StopIteration as err:
            return err.value

    def evict(self, fn: Callable, *args: Any, **kwargs: Any) -> None:
        """Remove the cached result for the given fn and args."""

        self.delete((fn_id(fn), self.key(*args, **kwargs)))
