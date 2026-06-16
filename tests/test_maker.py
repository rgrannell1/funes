# Tests for funes Maker: find/make sequencing, effect propagation, the shared-identity law.
from dataclasses import dataclass, field

import pytest

from funes import Maker, Miss


def drive(gen):
    """Run a generator to completion; return (return_value, [yielded_effects])."""
    effects = []
    try:
        while True:
            effects.append(next(gen))
    except StopIteration as stop:
        return stop.value, effects


@dataclass
class FunctionCounter:
    """Generator function recording each identity it was called with, returning a fixed value."""

    returns: object
    calls: list = field(default_factory=list)

    def __call__(self, *identity):
        self.calls.append(identity)
        yield from []
        return self.returns


# --- fixture functions (generators) ---


def find_effectful(*_identity):
    """Yield an effect, then miss."""
    yield "find_effect"
    return Miss.MISS


def find_hit_effectful(*_identity):
    """Yield an effect, then locate the resource."""
    yield "find_effect"
    return "found"


def make_effectful(*_identity):
    """Yield an effect, then build the resource."""
    yield "make_effect"
    return "made"


def make_raising(*_identity):
    """Raise unconditionally — a failed provision."""
    yield from []
    raise ValueError("provision failed")


# --- find/make sequencing ---

SEQUENCING_CASES = [
    {"desc": "hit: find locates, make skipped", "find": ("found",), "expect": ("found",),
     "make_ran": False},
    {"desc": "miss: find empty, make runs", "find": Miss.MISS, "expect": ("made",),
     "make_ran": True},
]


def test_find_make_sequencing():
    """find locates → make skipped; find misses → make runs; ensure returns the live value."""
    for case in SEQUENCING_CASES:
        find = FunctionCounter(returns=case["find"])
        make = FunctionCounter(returns=("made",))
        maker = Maker(find=find, make=make)
        value, _ = drive(maker.ensure("web-1"))
        assert value == case["expect"], case["desc"]
        assert (make.calls != []) == case["make_ran"], case["desc"]


# --- the shared-identity law ---


def test_shared_identity():
    """find and make receive the identical identity passed to ensure."""
    find = FunctionCounter(returns=Miss.MISS)
    make = FunctionCounter(returns="made")
    maker = Maker(find=find, make=make)
    drive(maker.ensure("ensure:web-1", "lon1"))
    assert find.calls == [("ensure:web-1", "lon1")]
    assert make.calls == [("ensure:web-1", "lon1")]


# --- effects bubble through ---


def test_effects_bubble_on_miss():
    """On a miss, find's then make's effects bubble through ensure in order."""
    maker = Maker(find=find_effectful, make=make_effectful)
    value, effects = drive(maker.ensure("x"))
    assert value == "made"
    assert effects == ["find_effect", "make_effect"]


def test_make_effects_absent_on_hit():
    """On a hit, find's effects bubble but make never runs, so its effects never appear."""
    maker = Maker(find=find_hit_effectful, make=make_effectful)
    value, effects = drive(maker.ensure("x"))
    assert value == "found"
    assert effects == ["find_effect"]


# --- failure propagates, nothing recorded ---


def test_make_raise_propagates():
    """A make that raises propagates; the Maker holds no state to poison."""
    maker = Maker(find=find_effectful, make=make_raising)
    with pytest.raises(ValueError):
        drive(maker.ensure("x"))
    # second call must also raise — the Maker recorded nothing to poison
    with pytest.raises(ValueError):
        drive(maker.ensure("x"))


# --- plain (non-generator) functions ---


def test_plain_functions():
    """Plain (non-generator) find/make are supported, like Store's plain-function path."""

    def find_plain(*_identity):
        return Miss.MISS

    def make_plain(*identity):
        return ("made", identity)

    maker = Maker(find=find_plain, make=make_plain)
    value, _ = drive(maker.ensure("x"))
    assert value == ("made", ("x",))
