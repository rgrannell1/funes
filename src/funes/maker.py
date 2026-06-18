"""Maker: a find/make combinator for ensuring stateful external resources exist."""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any

from funes.funes_types import Effectful

# a find may locate the resource, miss (None), or yield effects before doing either
type FindResult[Value] = Value | None | Effectful[Value | None]

# a make builds the resource directly, or yields effects before returning it
type MakeResult[Value] = Value | Effectful[Value]


def call_fn[Value](
    fn: Callable[..., Value | Effectful[Value]],
    identity: tuple[Any, ...],
) -> Effectful[Value]:
    """Invoke a find/make fn with the identity; relay its effects if it is a generator."""

    result = fn(*identity)

    if isinstance(result, Generator):
        return (yield from result)

    return result


@dataclass(kw_only=True)
class Maker[*Identifier, Value]:
    """Find-or-make a stateful external resource named by its identity. check if
    the resource exists; make it if not, return the result
    """

    # interrogates the world by identity; returns the resource or None
    find: Callable[[*Identifier], FindResult[Value]]

    # builds the resource, stamping the same identity find queries
    make: Callable[[*Identifier], MakeResult[Value]]

    def ensure(self, *identity: *Identifier) -> Effectful[Value]:
        """Return the resource find locates, else make it."""

        found = yield from call_fn(self.find, identity)
        if found is not None:
            return found
        return (yield from call_fn(self.make, identity))

    def run(self, *identity: *Identifier) -> Value:
        """Drive ensure synchronously, discarding any effects find/make yield; mirrors
        Store.run. Use `yield from maker.ensure(...)` inside a generator to preserve them."""

        gen = self.ensure(*identity)
        try:
            while True:
                next(gen)
        except StopIteration as stop:
            return stop.value
