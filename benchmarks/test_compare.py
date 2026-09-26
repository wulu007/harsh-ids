"""Cross-implementation benchmarks: harsh-ids (Rust) vs hashids (Pure Python).

Run with:
    uv run pytest benchmarks/test_compare.py --benchmark-only
"""

import pytest
from harsh_ids import Harsh as RustHashids
from hashids import Hashids as PyHashids

SALT = "benchmark_salt"
MIN_LENGTH = 16

DATA_SMALL = (1, 2, 3)
DATA_LARGE = tuple(range(100))

py_hasher = PyHashids(salt=SALT, min_length=MIN_LENGTH)
rs_hasher = RustHashids(salt=SALT, min_length=MIN_LENGTH)

HASH_SMALL = rs_hasher.encode(*DATA_SMALL)
HASH_LARGE = rs_hasher.encode(*DATA_LARGE)


@pytest.mark.benchmark(group="1. encode-small (3 nums)")
def test_rust_encode_small(benchmark):
    benchmark(rs_hasher.encode, *DATA_SMALL)


@pytest.mark.benchmark(group="1. encode-small (3 nums)")
def test_python_encode_small(benchmark):
    benchmark(py_hasher.encode, *DATA_SMALL)


@pytest.mark.benchmark(group="2. decode-small")
def test_rust_decode_small(benchmark):
    benchmark(rs_hasher.decode, HASH_SMALL)


@pytest.mark.benchmark(group="2. decode-small")
def test_python_decode_small(benchmark):
    benchmark(py_hasher.decode, HASH_SMALL)


@pytest.mark.benchmark(group="3. encode-large (100 nums)")
def test_rust_encode_large(benchmark):
    benchmark(rs_hasher.encode, *DATA_LARGE)


@pytest.mark.benchmark(group="3. encode-large (100 nums)")
def test_python_encode_large(benchmark):
    benchmark(py_hasher.encode, *DATA_LARGE)


@pytest.mark.benchmark(group="4. decode-large")
def test_rust_decode_large(benchmark):
    benchmark(rs_hasher.decode, HASH_LARGE)


@pytest.mark.benchmark(group="4. decode-large")
def test_python_decode_large(benchmark):
    benchmark(py_hasher.decode, HASH_LARGE)
