# funes: generator-based memoisation over a callable Store.
from funes.funes_types import ConfigError, FunesError, Miss, StoreError, UnwrapError
from funes.result import Err, Ok, Result
from funes.policy import always, is_ok
from funes.protocol import IStore, default_key
from funes.memory import DictStore
from funes.sqlite import SqliteStore

__all__ = [
    "ConfigError",
    "DictStore",
    "SqliteStore",
    "Err",
    "FunesError",
    "Miss",
    "Ok",
    "Result",
    "IStore",
    "StoreError",
    "UnwrapError",
    "always",
    "default_key",
    "is_ok",
]
