"""
canonical — one byte-exact encoding, so identical inputs hash identically everywhere.

Why not canonical JSON
----------------------
Every language formats JSON differently and the differences start at the first
float:

    Python  json.dumps(1.0)          -> "1.0"
    JS      JSON.stringify(1.0)      -> "1"
    Python  json.dumps(-0.0)         -> "-0.0"
    JS      JSON.stringify(-0)       -> "0"
    Python  json.dumps(float("nan")) -> "NaN"   (not valid JSON)
    JS      JSON.stringify(NaN)      -> "null"

Any design where each SDK canonicalises locally and the hashes "happen to agree" is
therefore broken before it ships. So this encodes to **binary**, with every
ambiguity decided once:

* floats as IEEE-754 big-endian bit patterns — no decimal formatting anywhere
* one frozen quiet-NaN pattern, so NaN has exactly one encoding
* -0.0 normalised to +0.0, because a sign bit on zero is not a value difference
* object keys sorted by UTF-8 byte order, not by locale or insertion order
* lengths as explicit varints, so nothing depends on delimiter escaping

The hash is computed **only here**, in Mojo. Both SDKs call this kernel rather than
hashing locally, which makes cross-language agreement a property of having one
implementation instead of a coincidence to be tested for.

Modules:
  encode — canonical binary TLV writer
  hash   — SHA-256 over canonical bytes

Invoked directly, not through `library_execute`, so this package is excluded from
the runtime-library inventory.
"""
