from typing import List, Optional, Sequence, Tuple, overload

__all__ = ["Harsh", "Hashids", "__version__"]
__version__: str


class Harsh:
    """A Hashids-compatible hasher backed by the Rust ``harsh`` crate.

    Generates YouTube-like short ids from lists of non-negative integers.
    Hashids values are *not* cryptographically secure.

    :param salt: salt string; changes the output for the same input.
    :param min_length: minimum hash length (hashes may be longer).
    :param alphabet: custom alphabet; must contain at least 16 unique
        ASCII characters and no spaces.
    :param separators: custom separator characters; every separator must
        be part of the alphabet.
    """

    def __init__(
        self,
        salt: Optional[str] = None,
        min_length: int = 0,
        alphabet: Optional[str] = None,
        separators: Optional[str] = None,
    ) -> None: ...

    @overload
    def encode(self, *values: int) -> str: ...
    @overload
    def encode(self, values: Sequence[int], /) -> str: ...
    def encode(self, *values: object) -> str:
        """Encode non-negative integers into a single hashid.

        Accepts varargs (``encode(1, 2, 3)``) as well as a single sequence
        of integers (``encode([1, 2, 3])``, ``encode(range(5))``), following
        the Hashids convention. Encoding no values returns an empty string.
        Values must fit in an unsigned 64-bit integer.
        """
        ...

    def decode(self, hashid: str) -> Tuple[int, ...]:
        """Decode a hashid into a tuple of integers.

        Returns a tuple to match the Python ``hashids`` package. Raises
        :class:`ValueError` if the hashid is not valid for this
        configuration.
        """
        ...

    def encode_hex(self, hex: str) -> str:
        """Encode a hex string (e.g. a MongoDB ObjectId) into a hashid.

        Raises :class:`ValueError` if the input is not valid hex.
        """
        ...

    def decode_hex(self, hashid: str) -> str:
        """Decode a hashid into a lowercase hex string.

        Only accepts hashids produced by :meth:`encode_hex` and raises
        :class:`ValueError` otherwise: the underlying crate rebuilds the
        hex by stripping one digit from every decoded value, which would
        silently corrupt anything else.
        """
        ...

    def encode_many(self, batches: Sequence[Sequence[int]]) -> List[str]:
        """Encode many sequences of integers in one boundary crossing.

        Each item is a sequence of non-negative integers — exactly what the
        list form of :meth:`encode` takes — and returns one hashid per item.
        The batch loop runs with the GIL released, so bulk workloads pay the
        Python/Rust boundary once instead of per call.
        """
        ...

    def decode_many(self, hashids: Sequence[str]) -> Tuple[Tuple[int, ...], ...]:
        """Decode many hashids in one boundary crossing.

        Returns a tuple of tuples, mirroring :meth:`decode`. Raises
        :class:`ValueError` on the first hashid that is not valid for this
        configuration.
        """
        ...


#: Compatibility alias: ``Hashids is Harsh``. Provided so that code written
#: against the Python ``hashids`` package (``from hashids import Hashids``)
#: keeps working with the same naming.
Hashids = Harsh
