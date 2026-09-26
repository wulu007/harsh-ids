//! Python bindings for [`harsh`](https://github.com/archer884/harsh), a
//! Hashids implementation in Rust.
//!
//! Exposes a single `Harsh` class whose constructor mirrors the options of
//! `HarshBuilder` (`salt`, `min_length`, `alphabet`, `separators`) and whose
//! methods mirror `encode`, `decode`, `encode_hex`, and `decode_hex`.
//!
//! Rust-side errors are surfaced as `ValueError`.

use ::harsh::{Harsh as NativeHarsh, HarshBuilder};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyBytes, PyList, PyString, PyTuple};

fn validate_ascii(field: &str, value: Option<&str>) -> PyResult<()> {
    if let Some(value) = value {
        if !value.is_ascii() {
            return Err(PyValueError::new_err(format!(
                "{field} must contain only ASCII characters: harsh operates on bytes, \
                 and multi-byte UTF-8 values would not round-trip"
            )));
        }
    }
    Ok(())
}

// Releasing the GIL costs a fixed handoff per call; only pay it when the
// computation is long enough to outrun the handoff. Below these thresholds
// calls stay on the GIL-held fast path (which also keeps tight threaded
// loops free of convoy effects); bulk work should use encode_many/decode_many.
const DETACH_MIN_VALUES: usize = 16;
const DETACH_MIN_CHARS: usize = 32;

fn to_value_error(err: ::harsh::Error) -> PyErr {
    PyValueError::new_err(err.to_string())
}

// `Sequence[int]` in the .pyi means collections.abc.Sequence; checking the
// ABC keeps runtime behavior aligned with what type checkers accept.
fn is_sequence(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<bool> {
    let sequence = py.import("collections.abc")?.getattr("Sequence")?;
    obj.is_instance(&sequence)
}

/// A Hashids-compatible hasher backed by the Rust `harsh` crate.
///
/// Generates YouTube-like short ids from lists of non-negative integers.
/// Hashids values are *not* cryptographically secure.
#[pyclass(module = "harsh_ids", frozen)]
struct Harsh {
    inner: NativeHarsh,
    salt: Option<String>,
    min_length: usize,
    alphabet: Option<String>,
    separators: Option<String>,
}

#[pymethods]
impl Harsh {
    #[new]
    #[pyo3(signature = (salt=None, min_length=0, alphabet=None, separators=None))]
    fn new(
        salt: Option<&str>,
        min_length: usize,
        alphabet: Option<&str>,
        separators: Option<&str>,
    ) -> PyResult<Self> {
        validate_ascii("salt", salt)?;
        validate_ascii("alphabet", alphabet)?;
        validate_ascii("separators", separators)?;

        let mut builder = HarshBuilder::new();
        if let Some(salt) = salt {
            builder = builder.salt(salt);
        }
        if let Some(alphabet) = alphabet {
            builder = builder.alphabet(alphabet);
        }
        if let Some(separators) = separators {
            builder = builder.separators(separators);
        }
        let builder = builder.length(min_length);

        let inner = builder
            .build()
            .map_err(|err| PyValueError::new_err(err.to_string()))?;

        Ok(Harsh {
            inner,
            salt: salt.map(str::to_string),
            min_length,
            alphabet: alphabet.map(str::to_string),
            separators: separators.map(str::to_string),
        })
    }

    /// Encode non-negative integers into a single hashid.
    ///
    /// Accepts varargs (`encode(1, 2, 3)`) as well as a single sequence of
    /// integers (`encode([1, 2, 3])`, `encode(range(5))`), following the
    /// Hashids convention. Encoding no values returns an empty string.
    /// Values must fit in an unsigned 64-bit integer.
    #[pyo3(signature = (*values))]
    fn encode<'py>(&self, py: Python<'py>, values: &Bound<'py, PyTuple>) -> PyResult<String> {
        let numbers: Vec<u64> = if values.len() == 1 {
            let first = values.get_item(0)?;
            match first.extract::<u64>() {
                Ok(number) => vec![number],
                Err(_) => {
                    // str/bytes/bytearray are sequences of the wrong element
                    // type; iterating them would yield characters.
                    let is_text = first.is_instance_of::<PyString>()
                        || first.is_instance_of::<PyBytes>()
                        || first.is_instance_of::<PyByteArray>();
                    if !is_text
                        && (first.is_instance_of::<PyList>()
                            || first.is_instance_of::<PyTuple>()
                            || is_sequence(py, &first)?)
                    {
                        first
                            .try_iter()?
                            .map(|item| item?.extract::<u64>())
                            .collect::<PyResult<Vec<u64>>>()?
                    } else {
                        // extract works under the limited API; PyString::to_str does not.
                        let name: String = first.get_type().name()?.extract()?;
                        return Err(PyTypeError::new_err(format!(
                            "encode() expects integers or a single sequence of integers, got {name}"
                        )));
                    }
                }
            }
        } else {
            values
                .iter()
                .map(|item| item.extract::<u64>())
                .collect::<PyResult<Vec<u64>>>()?
        };

        if numbers.len() >= DETACH_MIN_VALUES {
            // Pure Rust and large enough to be worth a GIL handoff.
            Ok(py.detach(|| self.inner.encode(&numbers)))
        } else {
            Ok(self.inner.encode(&numbers))
        }
    }

    /// Decode a hashid into a tuple of integers.
    ///
    /// Returns a tuple to match the Python `hashids` package. Raises
    /// ValueError if the hashid is not valid for this configuration.
    fn decode<'py>(&self, py: Python<'py>, hashid: &str) -> PyResult<Bound<'py, PyTuple>> {
        let result = if hashid.len() >= DETACH_MIN_CHARS {
            py.detach(|| self.inner.decode(hashid))
        } else {
            self.inner.decode(hashid)
        };
        let values = result.map_err(to_value_error)?;
        PyTuple::new(py, values)
    }

    /// Encode a hex string (e.g. a MongoDB ObjectId) into a hashid.
    ///
    /// Raises ValueError if the input is not valid hex.
    fn encode_hex(&self, py: Python<'_>, hex: &str) -> PyResult<String> {
        let result = if hex.len() >= DETACH_MIN_CHARS {
            py.detach(|| self.inner.encode_hex(hex))
        } else {
            self.inner.encode_hex(hex)
        };
        result.map_err(to_value_error)
    }

    /// Decode a hashid into a lowercase hex string.
    ///
    /// Only accepts hashids produced by `encode_hex`: harsh rebuilds the
    /// hex by stripping one digit from every decoded value, which silently
    /// corrupts anything else, so the result is re-encoded and compared
    /// before it is returned.
    fn decode_hex(&self, py: Python<'_>, hex_hashid: &str) -> PyResult<String> {
        // Decode + verification are pure Rust; run both with the GIL released
        // when the payload is large enough, and surface the verdict as a
        // Python error afterwards.
        let outcome = if hex_hashid.len() >= DETACH_MIN_CHARS {
            py.detach(|| self.decode_hex_verified(hex_hashid))
        } else {
            self.decode_hex_verified(hex_hashid)
        };
        let (hex, verified) = outcome.map_err(to_value_error)?;

        if !verified {
            return Err(PyValueError::new_err(format!(
                "{hex_hashid:?} was not produced by encode_hex"
            )));
        }

        Ok(hex)
    }

    /// Encode many sequences of integers in one boundary crossing.
    ///
    /// Each item is a sequence of non-negative integers — exactly what the
    /// list form of `encode` takes — and returns one hashid per item. The
    /// batch loop runs with the GIL released, so bulk workloads pay the
    /// Python/Rust boundary once instead of per call.
    fn encode_many<'py>(
        &self,
        py: Python<'py>,
        batches: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyList>> {
        // Flat value buffer + per-item lengths: one allocation for the whole
        // batch instead of one Vec per item.
        let mut flat: Vec<u64> = Vec::new();
        let mut lengths: Vec<usize> = Vec::new();
        for item in batches.try_iter()? {
            let item = item?;
            if item.is_instance_of::<PyString>()
                || item.is_instance_of::<PyBytes>()
                || item.is_instance_of::<PyByteArray>()
                || !(item.is_instance_of::<PyList>()
                    || item.is_instance_of::<PyTuple>()
                    || is_sequence(py, &item)?)
            {
                let name: String = item.get_type().name()?.extract()?;
                return Err(PyTypeError::new_err(format!(
                    "encode_many() items must be sequences of integers, got {name}"
                )));
            }
            let mut len = 0;
            for value in item.try_iter()? {
                flat.push(value?.extract::<u64>()?);
                len += 1;
            }
            lengths.push(len);
        }

        let encoded = py.detach(|| {
            let mut offset = 0;
            lengths
                .iter()
                .map(|&len| {
                    let numbers = &flat[offset..offset + len];
                    offset += len;
                    self.inner.encode(numbers)
                })
                .collect::<Vec<String>>()
        });
        PyList::new(py, encoded)
    }

    /// Decode many hashids in one boundary crossing.
    ///
    /// Returns a tuple of tuples, mirroring `decode`. Raises ValueError on
    /// the first hashid that is not valid for this configuration.
    fn decode_many<'py>(
        &self,
        py: Python<'py>,
        hashids: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyTuple>> {
        let mut inputs: Vec<String> = Vec::new();
        for item in hashids.try_iter()? {
            inputs.push(item?.extract::<String>()?);
        }

        let results: Vec<Result<Vec<u64>, ::harsh::Error>> =
            py.detach(|| inputs.iter().map(|id| self.inner.decode(id)).collect());

        let mut decoded = Vec::with_capacity(results.len());
        for result in results {
            decoded.push(PyTuple::new(py, result.map_err(to_value_error)?)?);
        }
        PyTuple::new(py, decoded)
    }

    // Reads __module__ from the class so repr can never drift from it.
    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        fn quoted(value: &Option<String>) -> String {
            match value {
                Some(value) => format!("{value:?}"),
                None => "None".to_owned(),
            }
        }
        let module: String = py.get_type::<Harsh>().getattr("__module__")?.extract()?;
        Ok(format!(
            "{module}.Harsh(salt={}, min_length={}, alphabet={}, separators={})",
            quoted(&self.salt),
            self.min_length,
            quoted(&self.alphabet),
            quoted(&self.separators),
        ))
    }

    // Lets pickle (and copy) reconstruct the instance through `__new__`.
    fn __getnewargs__(&self) -> (Option<String>, usize, Option<String>, Option<String>) {
        (
            self.salt.clone(),
            self.min_length,
            self.alphabet.clone(),
            self.separators.clone(),
        )
    }
}

impl Harsh {
    // Pure-Rust part of decode_hex: decode plus the re-encode verification.
    fn decode_hex_verified(&self, hex_hashid: &str) -> Result<(String, bool), ::harsh::Error> {
        self.inner.decode_hex(hex_hashid).map(|hex| {
            let verified = self
                .inner
                .encode_hex(&hex)
                .map(|reencoded| reencoded == hex_hashid)
                .unwrap_or(false);
            (hex, verified)
        })
    }
}

/// Python bindings for [harsh](https://github.com/archer884/harsh)
#[pymodule]
fn harsh_ids(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<Harsh>()?;
    module.add("__version__", env!("CARGO_PKG_VERSION"))?;

    // Compatibility alias mirroring the Python `hashids` package naming.
    // The very same class object is bound, so `Hashids is Harsh` holds.
    module.add("Hashids", module.getattr("Harsh")?)?;

    Ok(())
}
