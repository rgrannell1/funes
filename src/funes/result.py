"""Result protocol, Ok/Err concrete types."""

from dataclasses import dataclass
from typing import Never, Protocol, runtime_checkable

from funes.funes_types import UnwrapError


@runtime_checkable
class Result[Value, Error](Protocol):
    """A result interface."""

    def is_ok(self) -> bool:
        """Check if the result is an Ok."""
        ...

    def unwrap(self) -> Value:
        """Unwrap the result."""
        ...


@dataclass(frozen=True)
class Ok[Value]:
    """A successful result."""
    value: Value

    def is_ok(self) -> bool:
        """Check if the result is an Ok."""
        return True

    def unwrap(self) -> Value:
        """Unwrap the result."""
        return self.value


@dataclass(frozen=True)
class Err[Error]:
    """An error result."""
    error: Error

    def is_ok(self) -> bool:
        """Check if the result is an Err."""
        return False

    def unwrap(self) -> Never:
        """Unwrap the result."""
        raise UnwrapError(self.error)
