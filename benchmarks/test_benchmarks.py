"""Performance benchmarks for the harsh_ids binding.

Kept out of the default test suite; run them explicitly:

    pytest benchmarks --benchmark-only

Save and compare against a previous run to spot regressions:

    pytest benchmarks --benchmark-only --benchmark-autosave
    pytest benchmarks --benchmark-only --benchmark-compare

Methodology notes:

- Microsecond-scale calls are measured with ``benchmark.pedantic`` at 100
  calls per round: a single ~1µs call sits at Windows' ~100ns timer quantum
  and the harness overhead is a large fraction of the call itself, which
  would inflate the absolute numbers by ~30%.
- Threaded tests use a pre-built worker pool: thread spawn cost (hundreds of
  µs) would otherwise pollute the measurement.
- Numbers are machine-specific (Windows, Python 3.11, Rust release build);
  use them for same-machine regression comparison, not as absolute claims.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

from harsh_ids import Harsh

SALT = "this is my salt"
SMALL_CALLS_PER_ROUND = 100


def _encode_n(hashids: Harsh, n: int) -> None:
    for i in range(n):
        hashids.encode(i, i + 1)


def _decode_n(hashids: Harsh, hashid: str, n: int) -> None:
    for _ in range(n):
        hashids.decode(hashid)


@pytest.fixture(scope="module")
def hashids() -> Harsh:
    return Harsh(salt=SALT, min_length=8)


@pytest.fixture(scope="module")
def long_hashid(hashids: Harsh) -> str:
    # Multi-segment hashid in the "long payload" shape (~1k chars).
    return hashids.encode(*range(300))


@pytest.fixture(scope="module")
def pool():
    with ThreadPoolExecutor(max_workers=4) as executor:
        yield executor


def test_encode_small_varargs(benchmark, hashids):
    benchmark.pedantic(
        lambda: hashids.encode(1, 2, 3),
        iterations=SMALL_CALLS_PER_ROUND,
        rounds=50,
        warmup_rounds=5,
    )


def test_encode_small_list(benchmark, hashids):
    benchmark.pedantic(
        lambda: hashids.encode([1, 2, 3]),
        iterations=SMALL_CALLS_PER_ROUND,
        rounds=50,
        warmup_rounds=5,
    )


def test_encode_small_range(benchmark, hashids):
    # Sequence dispatch path (scalar miss + collections.abc check).
    benchmark.pedantic(
        lambda: hashids.encode(range(1, 4)),
        iterations=SMALL_CALLS_PER_ROUND,
        rounds=50,
        warmup_rounds=5,
    )


def test_decode_short(benchmark, hashids):
    benchmark.pedantic(
        lambda: hashids.decode("GlaHquq0"),
        iterations=SMALL_CALLS_PER_ROUND,
        rounds=50,
        warmup_rounds=5,
    )


def test_construct(benchmark):
    # Builder setup: alphabet/separator shuffling driven by the salt.
    benchmark(lambda: Harsh(salt=SALT, min_length=8))


def test_encode_hex(benchmark, hashids):
    benchmark.pedantic(
        lambda: hashids.encode_hex("507f1f77bcf86cd799439011"),
        iterations=SMALL_CALLS_PER_ROUND,
        rounds=50,
        warmup_rounds=5,
    )


def test_decode_hex(benchmark, hashids):
    hashid = hashids.encode_hex("507f1f77bcf86cd799439011")
    benchmark.pedantic(
        lambda: hashids.decode_hex(hashid),
        iterations=SMALL_CALLS_PER_ROUND,
        rounds=50,
        warmup_rounds=5,
    )


def test_encode_large(benchmark, hashids):
    # ~200µs per call: timer quantization is negligible here.
    numbers = list(range(1000))
    benchmark(lambda: hashids.encode(numbers))


def test_decode_long_payload(benchmark, hashids, long_hashid):
    benchmark(lambda: hashids.decode(long_hashid))


def test_encode_many(benchmark, hashids):
    # One boundary crossing for 2000 ids; compare against test_batch_serial.
    batches = [[i, i + 1] for i in range(2000)]
    benchmark(lambda: hashids.encode_many(batches))


def test_decode_many(benchmark, hashids):
    ids = [hashids.encode(i, i + 1) for i in range(2000)]
    benchmark(lambda: hashids.decode_many(ids))


def test_batch_serial(benchmark, hashids):
    # 2000 individual calls in one thread.
    benchmark(lambda: _encode_n(hashids, 2000))


def test_batch_threaded(benchmark, hashids, pool):
    # Same per-thread work across 4 pre-spawned workers (4x total). Against
    # test_batch_serial this shows whether the GIL policy leaves room for
    # concurrency at this call size.
    def batch():
        futures = [pool.submit(_encode_n, hashids, 2000) for _ in range(4)]
        for future in futures:
            future.result()

    benchmark(batch)


def test_batch_serial_long(benchmark, hashids, long_hashid):
    # 200 long-payload decodes in one thread: each call holds the
    # interpreter for ~100µs, so here the released GIL matters.
    benchmark(lambda: _decode_n(hashids, long_hashid, 200))


def test_batch_threaded_long(benchmark, hashids, long_hashid, pool):
    # 4 workers x 50 long decodes (same total work as the serial one).
    def batch():
        futures = [pool.submit(_decode_n, hashids, long_hashid, 50) for _ in range(4)]
        for future in futures:
            future.result()

    benchmark(batch)
