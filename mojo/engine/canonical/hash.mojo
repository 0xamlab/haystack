"""
canonical.hash — SHA-256 over canonical bytes. Zero Python.

Reuses the existing frozen `sha256` kernel; the value added here is that the input
is canonical bytes rather than whatever a caller happened to serialise. Same logical
value in, same digest out, in any language — because there is exactly one encoder.

Digests are prefixed with the encoding version, so a hash carries the rules that
produced it. A stored digest can then be recognised as belonging to an older
encoding instead of silently comparing unequal to a new one.
"""
from sha256 import sha256_hex

from canonical.encode import ENCODING_VERSION, to_hex


fn hash_canonical_bytes(bytes: List[UInt8]) -> String:
    """SHA-256 of canonical bytes, as 64 lowercase hex characters.

    Goes through hex rather than raw bytes because the frozen `sha256_hex` kernel
    takes a String; hex is a faithful, unambiguous byte representation, so this
    costs a constant factor and no fidelity.
    """
    return sha256_hex(to_hex(bytes))


fn versioned_digest(bytes: List[UInt8]) -> String:
    """`<encoding-version>:<digest>` — the form to persist.

    Carrying the version means a digest written under a future encoding is visibly
    different rather than merely unequal, so a comparison can report "different
    rules" instead of "different data".
    """
    return ENCODING_VERSION + ":" + hash_canonical_bytes(bytes)


fn digest_encoding_version(digest: String) -> String:
    """The encoding version recorded in a versioned digest, or "" if unversioned."""
    var index = digest.find(":")
    if index <= 0:
        return ""
    var bytes = digest.as_bytes()
    var out = String("")
    for i in range(index):
        out += chr(Int(bytes[i]))
    return out


fn digest_matches_encoding(digest: String) -> Bool:
    """True when `digest` was produced by the encoding this build implements."""
    return digest_encoding_version(digest) == ENCODING_VERSION
