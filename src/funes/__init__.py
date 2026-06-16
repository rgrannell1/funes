# funes: generator-based memoisation over a callable Store.
from funes.funes_types import ConfigError, FunesError, Miss, StoreError, UnwrapError
from funes.maker import Maker
from funes.memory import DictStore
from funes.policy import always, is_ok
from funes.protocol import IStore, default_key
from funes.result import Err, Ok, Result
from funes.sqlite import SqliteStore

__all__ = [
    "ConfigError",
    "DictStore",
    "Err",
    "FunesError",
    "IStore",
    "Maker",
    "Miss",
    "Ok",
    "Result",
    "SqliteStore",
    "StoreError",
    "UnwrapError",
    "always",
    "default_key",
    "is_ok",
]
