<div align="center">

# harsh-ids

[![CI][ci-badge]][ci-link]
[![Python][python-badge]][pypi-link]
[![License][license-badge]][license-link]
[![Built with PyO3][pyo3-badge]][pyo3-link]
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://app.codspeed.io/wulu007/harsh-ids?utm_source=badge)

**Hashids in Rust, for Python.** Encode integers into YouTube-like short ids:
sequential ids stop looking sequential, and several numbers pack into a single id.

</div>

> **⚠️ Not encryption.** Hashids obfuscates ids for convenience. It is not
> cryptographically secure, whatever the salt. Don't use it to protect secrets.

## Installation

```bash
pip install harsh-ids
```

## Quick start

```python
from harsh_ids import Harsh

hashids = Harsh(salt="this is my salt", min_length=8)

hashids.encode(1, 2, 3)          # 'GlaHquq0'
hashids.decode('GlaHquq0')       # (1, 2, 3)

hashids.encode_hex('deadbeef')   # 'kRNrpKlJ'   (MongoDB ObjectIds, etc.)
hashids.decode_hex('kRNrpKlJ')   # 'deadbeef'
```

### Constructor options

| Option | Default | Description |
|--------|---------|-------------|
| `salt` | `None` | Changes the output for the same input. Defaults to no salt |
| `min_length` | `0` | Minimum hash length — hashes may come out longer |
| `alphabet` | `None` | Custom alphabet, at least 16 unique ASCII characters, no spaces. Defaults to the standard 62-character Hashids alphabet |
| `separators` | `None` | Custom separator characters, must be part of the alphabet. Defaults to `cfhistuCFHISTU` |

## API

| Method | Returns | Description |
|--------|---------|-------------|
| `encode(*values)` | `str` | Encodes non-negative ints (each < 2⁶⁴) into one hashid. Also accepts a single sequence (`encode([1, 2, 3])`, `encode(range(5))`); `encode()` returns `''`. Raises `TypeError` if an argument is neither an int nor a single sequence of ints. |
| `decode(hashid)` | `tuple[int, ...]` | Decodes a hashid back into integers. Raises `ValueError` on invalid input. |
| `encode_hex(hex)` | `str` | Encodes a hex string. Raises `ValueError` on invalid hex. |
| `decode_hex(hashid)` | `str` | Decodes to lowercase hex. Raises `ValueError` unless the hashid round-trips through `encode_hex`. |
| `encode_many(batches)` | `list[str]` | Encodes many sequences in one call — each item is what the list form of `encode` takes. Bulk workloads pay the Python/Rust boundary once. |
| `decode_many(hashids)` | `tuple[tuple[int, ...], ...]` | Decodes many hashids in one call. Raises `ValueError` on the first invalid one. |

Using the Python `hashids` package today? `Hashids` is exported as an alias for
`Harsh`, so swapping the import is enough. The main difference is error
handling: `hashids` returns `''` or `()` on bad input, this package raises. If
your code depends on those empty returns, wrap the calls in a `try`.

## Notes

- **ASCII only** — `salt`, `alphabet`, and `separators` must be ASCII: the
  underlying [`harsh`](https://github.com/archer884/harsh) crate operates on
  bytes, so multi-byte UTF-8 would not round-trip.
- **Tuples out** — `decode` always returns a tuple, even for a single number.
- **Strict hex** — `decode_hex` re-encodes and verifies its result, so a hashid
  that does not round-trip raises `ValueError` instead of silently returning
  corrupted hex (a flaw in the underlying crate).
- **Immutable & pickleable** — instances are frozen value objects; `copy`,
  `deepcopy`, and `pickle` all work.
- **Releases the GIL — selectively** — the pure-Rust computation runs with
  the interpreter lock released (`Python::detach`) once a call is big enough
  to be worth the handoff (≥ 16 values or ≥ 32 characters); tiny calls stay
  on the GIL-held fast path. For bulk work, `encode_many`/`decode_many` pay
  the Python/Rust boundary once and run the whole batch with the GIL
  released. Instances are shared safely across threads either way.
- **No profanity by default** — the 14 default separators (`cfhistuCFHISTU`)
  are held out of the alphabet and never placed next to each other. English
  curse words are built from the lowercase seven (`cfhistu`), so ids can't
  spell them.

## Development

Source builds need a Rust toolchain; wheels are built as `abi3`, so one wheel
covers CPython 3.9 and newer.

```bash
uv sync              # installs the project + the dev group (pytest)
uv run pytest        # includes known-answer vectors from the upstream crate
uv build --wheel     # or: maturin build --release
```

## Benchmarks

<!-- BENCHMARK-START -->
| Operation (Scenario) | Pure Python (`hashids`) | Rust (`harsh-ids`) | Throughput (`harsh-ids`) | **Speedup** |
| :--- | :--- | :--- | :--- | :--- |
| **Encode (3 nums)** | 22.1 µs | **1.15 µs** | **869.1 Kops/s** | 🚀 **~19.2x** |
| **Decode (short id)** | 39.8 µs | **1.79 µs** | **560.0 Kops/s** | 🚀 **~22.3x** |
| **Encode (100 nums)** | 517.7 µs | **20.2 µs** | **49.4 Kops/s** | 🚀 **~25.6x** |
| **Decode (long payload)** | 1.07 ms | **38.3 µs** | **26.1 Kops/s** | 🚀 **~27.9x** |

> *Environment: Tested on Windows 11 with Python 3.11.13 using `pytest-benchmark`.*
<!-- BENCHMARK-END -->

Excluded from the default test run; run explicitly:

```bash
uv run --group bench pytest benchmarks --benchmark-only
```

Add `--benchmark-autosave` to store a run, `--benchmark-compare` to diff
against the stored one.

`benchmarks/test_compare.py` benchmarks against the official pure-Python
`hashids` package (20–30× slower on the same machine) and doubles as a
cross-implementation consistency check. For bulk workloads
`encode_many`/`decode_many` run 2000 ids in a single boundary crossing
(~0.5 µs/id); small calls hold the GIL, so threading batches of them
serializes cleanly, while long-payload decoding scales ~3.6× across 4 pooled
threads. Treat the medians above as same-machine regression baselines, not
absolute claims.

## License

[MIT](LICENSE)

<!-- badge link definitions -->
[ci-badge]: https://github.com/wulu007/harsh-ids/actions/workflows/CI.yml/badge.svg
[ci-link]: https://github.com/wulu007/harsh-ids/actions/workflows/CI.yml
[pypi-link]: https://pypi.org/project/harsh-ids/
[python-badge]: https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white&style=flat-square
[license-badge]: https://img.shields.io/badge/license-MIT-blue?style=flat-square
[license-link]: #license
[pyo3-badge]: https://img.shields.io/badge/built%20with-PyO3-orange?logo=rust&style=flat-square
[pyo3-link]: https://github.com/PyO3/pyo3
