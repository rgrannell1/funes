"""Miss sentinel, exceptions, and CacheEntry for cache and result types."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


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
