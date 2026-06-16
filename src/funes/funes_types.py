"""Miss sentinel, exceptions, and CacheEntry for cache and result types."""

from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

# A generator program that may yield (bubble) effects and return a Value — the shape every
# funes function drives under `yield from`. Yield/send are Any: funes is effect-agnostic.
type Effectful[Value] = Generator[Any, Any, Value]


class Miss(Enum):
    """A miss sentinel."""

    MISS = auto()


class FunesError(Exception):
    """Base class for all funes exceptions."""


class UnwrapError(FunesError):
    """Raised when unwrapping an Err result."""


class StoreError(FunesError):
    """Raised when a store method is called outside its context manager."""


class ConfigError(FunesError):
    """Raised for invalid configuration, e.g. conflicting ttl_* arguments."""


@dataclass(frozen=True)
class CacheEntry:
    """Wraps a cached value with an optional expiry timestamp (seconds since epoch)."""

    value: Any
    expires_at: float | None
