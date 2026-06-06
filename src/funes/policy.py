"""should_store predicates: built-in policies for controlling cache storage."""

from funes.result import Result


def always(_value) -> bool:
    return True


def is_ok(value) -> bool:
    return isinstance(value, Result) and value.is_ok()
