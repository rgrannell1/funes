# Tests for funes Store: caching policy, hit/miss, key derivation, effect propagation.
from dataclasses import dataclass

import pytest

from funes import ConfigError, DictStore, Err, Ok, UnwrapError, always, is_ok


def drive(gen):
    """Run a generator to completion; return (return_value, [yielded_effects])."""
    effects = []
    try:
        while True:
            effects.append(next(gen))
    except StopIteration as stop:
        return stop.value, effects


@dataclass
class CallCounter:
    """Generator callable that counts invocations."""

    count: int = 0

    def __call__(self, *args):
        self.count += 1
        yield from []
        return args


# --- fixture generator functions (all must be generator functions) ---


def pass_through(x):
    """Return x unchanged."""
    yield from []
    return x


def wrap_ok(x):
    """Return Ok(x)."""
    yield from []
    return Ok(x)


def wrap_err(x):
    """Return Err(x)."""
    yield from []
    return Err(x)


def raise_error(_x):
    """Raise ValueError unconditionally."""
    yield from []
    raise ValueError("transient")


def yield_effects(x):
    """Yield two effects then return x * 2."""
    yield "effect_A"
    yield "effect_B"
    return x * 2


def select_first_arg(*args, **_kw):
    """Key function: use only the first positional argument."""
    return (args[0],)


# --- caching policy ---

POLICY_CASES = [
    {"fn": pass_through, "policy": always, "args": (42,), "expect_cached": True},
    {"fn": wrap_ok, "policy": is_ok, "args": (42,), "expect_cached": True},
    {"fn": wrap_err, "policy": is_ok, "args": (42,), "expect_cached": False},
]


def test_caching_policy():
    """Caching policy: always stores plain values; is_ok stores Ok not Err."""
    for case in POLICY_CASES:
        with DictStore(should_store=case["policy"]) as store:
            drive(store(case["fn"], *case["args"]))
            drive(store(case["fn"], *case["args"]))
            if case["expect_cached"]:
                assert store.hits == 1, f"expected hit on second call: {case['fn'].__name__}"
            else:
                assert store.hits == 0, f"expected miss on second call: {case['fn'].__name__}"


# --- hit fires no recompute ---

RECOMPUTE_CASES = [
    {"args": (5,)},
    {"args": (1, 2)},
]


def test_no_recompute_on_hit():
    """A cache hit returns the stored value without re-running fn."""
    for case in RECOMPUTE_CASES:
        counter = CallCounter()
        with DictStore() as store:
            drive(store(counter, *case["args"]))
            drive(store(counter, *case["args"]))
        assert counter.count == 1, f"fn re-ran for args {case['args']}"


# --- exceptions not cached ---


def test_exception_not_cached():
    """A raised exception propagates and leaves the store empty."""
    with DictStore() as store:
        with pytest.raises(ValueError):
            drive(store(raise_error, 1))
        assert store.table == {}
        with pytest.raises(ValueError):
            drive(store(raise_error, 1))
        assert store.table == {}, "second call must also raise (no poison in store)"


# --- effects bubble through ---


def test_effects_bubble_through():
    """Yielded values from fn pass through the store to the outer caller."""
    with DictStore() as store:
        _, effects = drive(store(yield_effects, 5))
        assert effects == ["effect_A", "effect_B"]
        _, effects_on_hit = drive(store(yield_effects, 5))
        assert effects_on_hit == [], "a hit yields nothing"


# --- multi-adic keys ---

MULTI_ADIC_CASES = [
    {"a": (1, 2), "b": (1, 3), "expect_calls": 2},
    {"a": (7,), "b": (7,), "expect_calls": 1},
]


def test_multi_adic_key():
    """Different argument sets produce different cache keys; same args hit."""
    for case in MULTI_ADIC_CASES:
        counter = CallCounter()
        with DictStore() as store:
            drive(store(counter, *case["a"]))
            drive(store(counter, *case["b"]))
        assert counter.count == case["expect_calls"]


# --- custom key override ---


def test_custom_key_override():
    """A key= function can collapse different arg sets to a single cache entry."""
    counter = CallCounter()
    with DictStore(key=select_first_arg) as store:
        drive(store(counter, 1, "ignored"))
        drive(store(counter, 1, "different"))
    assert counter.count == 1, "second call must be a hit (same first arg → same key)"


# --- Ok/Err unwrap ---

UNWRAP_CASES = [
    {"result": Ok(42), "expect_value": 42, "expect_raise": False},
    {"result": Ok("hello"), "expect_value": "hello", "expect_raise": False},
    {"result": Err("oops"), "expect_value": None, "expect_raise": True},
]


def test_unwrap():
    """Ok.unwrap() returns the value; Err.unwrap() raises UnwrapError."""
    for case in UNWRAP_CASES:
        result = case["result"]
        if case["expect_raise"]:
            with pytest.raises(UnwrapError):
                result.unwrap()
        else:
            assert result.unwrap() == case["expect_value"]


# --- plain function support ---


def plain_double(x):
    """A plain (non-generator) function."""
    return x * 2


def test_plain_function():
    """A plain function is memoised without requiring yield from at the call site."""
    counter = CallCounter()

    def plain_count(*args):
        counter.count += 1
        return args

    with DictStore() as store:
        store.run(plain_count, 7)
        store.run(plain_count, 7)
    assert counter.count == 1


# --- run() synchronous interface ---

RUN_CASES = [
    {"args": (3,), "fn": plain_double, "expected": 6},
    {"args": ("x",), "fn": plain_double, "expected": "xx"},
]


def test_run():
    """run() drives the store synchronously and returns the cached value."""
    for case in RUN_CASES:
        with DictStore() as store:
            result = store.run(case["fn"], *case["args"])
            assert result == case["expected"]
            cached = store.run(case["fn"], *case["args"])
            assert cached == case["expected"]


# --- bypass ---


def test_bypass():
    """bypass=True skips the cache and re-runs fn, refreshing the stored value."""
    counter = CallCounter()
    with DictStore() as store:
        store.run(counter, 1)
        store.run(counter, 1)           # hit — fn not called again
        store.run(counter, 1, bypass=True)  # bypass — fn called again
    assert counter.count == 2


# --- evict ---


def test_evict():
    """evict() removes a cached entry; the next call is a miss."""
    counter = CallCounter()
    with DictStore() as store:
        store.run(counter, 5)
        store.evict(counter, 5)
        store.run(counter, 5)           # miss after eviction
    assert counter.count == 2


# --- key collision ---


def alpha(*args):
    return args


def beta(*args):
    return args


def test_no_key_collision():
    """Two functions called with identical args must not share a cache entry."""
    with DictStore() as store:
        store.run(alpha, 1)
        store.run(beta, 1)
        assert len(store.table) == 2


# --- statistics ---


def test_statistics():
    """hits and misses are counted correctly."""
    with DictStore() as store:
        store.run(alpha, 1)   # miss
        store.run(alpha, 1)   # hit
        store.run(alpha, 2)   # miss
    assert store.hits == 1
    assert store.misses == 2


# --- ttl ---


def test_ttl_hit_within_expiry():
    """A cached entry is returned when called within its TTL."""
    with DictStore() as store:
        store.run(alpha, 1, ttl_seconds=60)
        store.run(alpha, 1, ttl_seconds=60)
    assert store.hits == 1


def test_ttl_miss_after_expiry():
    """An expired entry is treated as a miss and re-computed."""
    with DictStore() as store:
        store.run(alpha, 1, ttl_seconds=-1)   # already expired
        store.run(alpha, 1, ttl_seconds=-1)
    assert store.hits == 0
    assert store.misses == 2


def test_ttl_mutual_exclusivity():
    """Providing more than one ttl_* argument raises ValueError."""
    with DictStore() as store, pytest.raises(ConfigError):
        store.run(alpha, 1, ttl_seconds=10, ttl_minutes=1)


def test_expired_entry_evicted_when_not_stored():
    """Stale expired entry is deleted when recomputed value fails should_store."""
    responses = [Ok(1), Err("fail")]
    call_idx = [0]

    def toggling(*_args):
        result = responses[call_idx[0] % len(responses)]
        call_idx[0] += 1
        return result

    with DictStore(should_store=is_ok) as store:
        store.run(toggling, 1, ttl_seconds=-1)  # Ok stored with already-expired TTL
        assert len(store.table) == 1
        store.run(toggling, 1)                  # expired → Err → not stored → stale entry deleted
        assert len(store.table) == 0


def test_bypass_does_not_inflate_misses():
    """bypass=True counts as a miss only if there was no valid cached entry."""
    with DictStore() as store:
        store.run(alpha, 1)                 # miss
        store.run(alpha, 1, bypass=True)    # bypass — not a true miss
    assert store.misses == 1
