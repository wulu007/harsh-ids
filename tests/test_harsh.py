import copy
import pickle

import pytest
from harsh_ids import Harsh, __version__

SALT = "this is my salt"


def test_version():
    assert isinstance(__version__, str) and __version__


def test_default_encode_decode():
    hashids = Harsh()
    assert hashids.encode(1, 2, 3) == "o2fXhV"
    decoded = hashids.decode("o2fXhV")
    assert decoded == (1, 2, 3)
    assert isinstance(decoded, tuple)


def test_encode_known_values():
    hashids = Harsh(salt=SALT)
    assert hashids.encode(1, 2, 3) == "laHquq"
    assert hashids.encode(1226198605112) == "4o6Z7KqxE"


def test_encode_varargs_and_list_agree():
    hashids = Harsh(salt=SALT)
    assert hashids.encode(1, 2, 3) == hashids.encode([1, 2, 3])
    assert hashids.encode((1, 2, 3)) == "laHquq"
    assert hashids.encode(0) == hashids.encode([0])


def test_encode_empty():
    assert Harsh().encode() == ""
    assert Harsh().encode([]) == ""
    assert Harsh().encode(()) == ""


def test_encode_rejects_bad_args():
    hashids = Harsh(salt=SALT)
    with pytest.raises(TypeError):
        hashids.encode(1, [2])
    with pytest.raises(TypeError):
        hashids.encode("1")


def test_encode_accepts_sequences():
    # Any Sequence[int] per the .pyi contract, not just list/tuple.
    import collections.abc

    hashids = Harsh(salt=SALT)
    assert hashids.encode(range(1, 4)) == "laHquq"

    class RegisteredSequence:
        def __init__(self, values):
            self._values = list(values)

        def __len__(self):
            return len(self._values)

        def __getitem__(self, index):
            return self._values[index]

    collections.abc.Sequence.register(RegisteredSequence)
    assert hashids.encode(RegisteredSequence([1, 2, 3])) == "laHquq"
    # single-element range covering the u64 maximum
    assert hashids.decode(hashids.encode(range(2**64 - 1, 2**64))) == (2**64 - 1,)


def test_encode_rejects_non_sequences():
    # str/bytes iterate to characters, generators/set/dict are not
    # Sequence[int], and duck-typed __getitem__ types are not registered.
    hashids = Harsh(salt=SALT)

    class DuckSequence:
        def __init__(self, values):
            self._values = list(values)

        def __len__(self):
            return len(self._values)

        def __getitem__(self, index):
            return self._values[index]

    for bad in [
        "123",
        b"123",
        bytearray(b"123"),
        (x for x in [1, 2]),
        DuckSequence([1, 2]),
        {1: "a"},
    ]:
        with pytest.raises(TypeError, match="sequence"):
            hashids.encode(bad)


def test_decode_known_values():
    hashids = Harsh(salt=SALT)
    assert hashids.decode("laHquq") == (1, 2, 3)
    assert hashids.decode("4o6Z7KqxE") == (1226198605112,)


def test_min_length():
    assert Harsh(salt=SALT, min_length=8).encode([1, 2, 3]) == "GlaHquq0"
    assert Harsh(salt=SALT, min_length=12).encode([1, 2, 3]) == "9LGlaHquq06D"
    assert Harsh(min_length=3).encode([1]) == "ejR"


def test_roundtrip_various():
    hashids = Harsh(salt=SALT, min_length=8)
    numbers = [
        [0],
        [1],
        [1, 2, 3],
        [0, 0, 0],
        [2**64 - 1],
        [123456789, 987654321, 555555555],
    ]
    for values in numbers:
        assert hashids.decode(hashids.encode(values)) == tuple(values)


def test_custom_alphabet():
    hashids = Harsh(alphabet="abcdefghijklmnopqrstuvwxyz")
    assert hashids.encode(1, 2, 3) == "mdfphx"
    assert hashids.decode("mdfphx") == (1, 2, 3)


def test_custom_separators():
    # Differentiating feature vs the Python `hashids` package, which does not
    # allow custom separators: they must change multi-value output, round-trip
    # cleanly, and be required for decoding.
    custom = Harsh(salt=SALT, separators="abZ901")
    default = Harsh(salt=SALT)

    # golden canaries generated from harsh 0.2.2 through this binding; a
    # mismatch means separator handling (or upstream) drifted
    assert custom.encode(1, 2, 3) == "B61V9H"
    assert custom.decode("B61V9H") == (1, 2, 3)
    assert custom.encode(7, 8, 9) == "ssdqeQ"

    # the parameter must have an observable effect on multi-value encoding
    assert custom.encode(1, 2, 3, 4, 5) == "uU1J9OasbU"
    assert custom.encode(1, 2, 3, 4, 5) != default.encode(1, 2, 3, 4, 5)

    # hashids built with different separators must not decode
    with pytest.raises(ValueError):
        default.decode(custom.encode(1, 2, 3))


def test_separators_outside_alphabet_are_filtered():
    # harsh silently drops separator characters missing from the alphabet
    # instead of erroring; encoding/decoding must stay self-consistent
    hashids = Harsh(salt=SALT, separators="@#$%^&*")
    assert hashids.decode(hashids.encode(7, 8, 9)) == (7, 8, 9)


def test_hex():
    hashids = Harsh(salt=SALT)
    assert hashids.encode_hex("FA") == "lzY"
    assert hashids.decode_hex("lzY") == "fa"
    assert hashids.encode_hex("deadbeef") == "kRNrpKlJ"
    assert hashids.decode_hex("kRNrpKlJ") == "deadbeef"


def test_hex_objectid():
    hashids = Harsh()
    hashid = hashids.encode_hex("507f1f77bcf86cd799439011")
    assert hashid == "y42LW46J9luq3Xq9XMly"
    assert hashids.decode_hex(hashid) == "507f1f77bcf86cd799439011"


def test_decode_hex_roundtrip():
    hashids = Harsh(salt=SALT)
    for hex_value in [
        "0",
        "fa",
        "00ff",
        "deadbeef",
        "1d7f21dd38",
        "507f1f77bcf86cd799439011",
    ]:
        assert hashids.decode_hex(hashids.encode_hex(hex_value)) == hex_value.lower()


def test_decode_hex_rejects_non_hex_hashids():
    # harsh silently strips one hex digit per decoded value, so hashids not
    # produced by encode_hex would decode to corrupted hex; expect an error.
    # (Values whose hex starts with '1' survive stripping self-consistently
    # and are accepted, e.g. decode_hex(encode(1226198605112)) == '1d7f21dd38'.)
    hashids = Harsh(salt=SALT)
    with pytest.raises(ValueError, match="encode_hex"):
        hashids.decode_hex(hashids.encode(0))
    with pytest.raises(ValueError, match="encode_hex"):
        hashids.decode_hex(hashids.encode(0, 1))
    with pytest.raises(ValueError, match="encode_hex"):
        hashids.decode_hex(hashids.encode(0xDEADBEEF))
    with pytest.raises(ValueError, match="encode_hex"):
        hashids.decode_hex(hashids.encode(1, 2, 3))


def test_decode_hex_accepts_self_consistent_hashids():
    # 1226198605112 == 0x11d7f21dd38: stripping the leading '1' leaves hex
    # that re-encodes to the same hashid, so it decodes cleanly.
    hashids = Harsh(salt=SALT)
    hashid = hashids.encode(1226198605112)
    assert hashid == "4o6Z7KqxE"
    assert hashids.decode_hex(hashid) == "1d7f21dd38"
    assert hashids.encode_hex(hashids.decode_hex(hashid)) == hashid


def test_decode_invalid():
    hashids = Harsh(salt=SALT)
    with pytest.raises(ValueError):
        hashids.decode("this$ain't|a number")
    with pytest.raises(ValueError):
        hashids.decode("")


def test_appended_garbage_invalidates():
    hashids = Harsh(min_length=4)
    with pytest.raises(ValueError):
        hashids.decode(hashids.encode([1, 2]) + "12")


def test_encode_rejects_negative():
    with pytest.raises(Exception):
        Harsh().encode([-1])


def test_encode_rejects_too_large():
    with pytest.raises(Exception):
        Harsh().encode([2**64])


def test_alphabet_too_short():
    with pytest.raises(ValueError, match="at least 16"):
        Harsh(alphabet="abc")


def test_alphabet_illegal_character():
    with pytest.raises(ValueError, match="illegal character"):
        Harsh(alphabet="a b c defghijklmno")


def test_non_ascii_rejected():
    with pytest.raises(ValueError, match="ASCII"):
        Harsh(alphabet="abcdefghijklmnopqrstü")
    with pytest.raises(ValueError, match="ASCII"):
        Harsh(salt="盐")


def test_repr():
    hashids = Harsh(salt=SALT, min_length=8)
    assert repr(hashids) == (
        'harsh_ids.Harsh(salt="this is my salt", min_length=8, alphabet=None, separators=None)'
    )
    assert repr(Harsh()) == (
        "harsh_ids.Harsh(salt=None, min_length=0, alphabet=None, separators=None)"
    )


def test_pickle_and_copy():
    hashids = Harsh(salt=SALT, min_length=8)
    clones = [
        pickle.loads(pickle.dumps(hashids)),
        copy.copy(hashids),
        copy.deepcopy(hashids),
    ]
    for clone in clones:
        assert clone.encode(1, 2, 3) == "GlaHquq0"
        assert clone.decode("GlaHquq0") == (1, 2, 3)


def test_hashids_alias():
    import harsh_ids

    assert harsh_ids.Hashids is Harsh
    assert sorted(harsh_ids.__all__) == ["Harsh", "Hashids", "__version__"]

    hashids = harsh_ids.Hashids(salt=SALT)
    assert hashids.encode(1, 2, 3) == "laHquq"
    assert hashids.decode("laHquq") == (1, 2, 3)


def test_hashids_alias_star_import():
    namespace: dict = {}
    exec("from harsh_ids import *", namespace)
    assert namespace["Hashids"] is Harsh
    assert namespace["Harsh"] is Harsh


def test_module_attr():
    assert Harsh.__module__ == "harsh_ids"


def test_thread_safety():
    # Frozen instances are shared across threads; the Rust computation runs
    # with the GIL released, so this exercises the detach path end to end.
    import threading

    hashids = Harsh(salt=SALT, min_length=8)
    expected = [hashids.encode(i, i + 1) for i in range(200)]
    results = []

    def worker():
        results.append([hashids.encode(i, i + 1) for i in range(200)])

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 4
    for produced in results:
        assert produced == expected


def test_encode_many_and_decode_many():
    hashids = Harsh(salt=SALT)
    encoded = hashids.encode_many([[1, 2, 3], [1226198605112], range(4, 6)])
    assert encoded == ["laHquq", "4o6Z7KqxE", hashids.encode(4, 5)]
    assert hashids.decode_many(encoded) == ((1, 2, 3), (1226198605112,), (4, 5))
    assert hashids.decode_many([]) == ()
    # empty batch item encodes to '' and cannot decode, like encode()/decode()
    assert hashids.encode_many([[]]) == [""]
    with pytest.raises(ValueError):
        hashids.decode_many([""])
    # consistency with the single-call API
    assert encoded[0] == hashids.encode(1, 2, 3)


def test_encode_many_rejects_bad_items():
    hashids = Harsh(salt=SALT)
    # scalar items are ambiguous (one id of three numbers vs three ids)
    with pytest.raises(TypeError, match="encode_many"):
        hashids.encode_many([1, 2, 3])
    with pytest.raises(TypeError, match="encode_many"):
        hashids.encode_many(["123"])


def test_decode_many_rejects_invalid():
    hashids = Harsh(salt=SALT)
    good = hashids.encode_many([[1, 2], [3, 4]])
    with pytest.raises(ValueError):
        hashids.decode_many([good[0], "not-a-hashid"])
    with pytest.raises(TypeError):
        hashids.decode_many([good[0], 42])
