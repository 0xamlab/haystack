---
icon: key
description: Checksums, encoding, keyed hashing, key derivation, a stream cipher and a Merkle tree — compiled primitives, not a general-purpose library wrapper.
---

# Data integrity and encoding

Eight kernel modules for the checksums, encodings and keyed hashes that show up underneath
almost everything else — verifying a download, deriving a key from a password, proving one
leaf belongs to a tree without shipping the whole tree. All run as compiled kernels inside the
runtime that ships with the SDK — there is nothing to start and nothing to install separately.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("crypto.crc32", "crc32", ["hello world"])["result"]
# 222957957 — the standard IEEE 802.3 CRC-32 of the bytes, as an integer

runtime.execute("crypto.crc32", "crc32_hex", ["hello world"])["result"]
# "0d4a1185" — the same checksum, as the hex string you'd compare against a published one

runtime.execute("crypto.hmac", "hmac_sha256", ["secret-key", "hello world"])["result"]
# "095d5a21fe6d0646db223fdf3de6436bb8dfb2fab0b51677ecf6441fcf5f2a67"
```

These are the exact bytes a reference implementation would produce — the CRC-32 above matches
the IEEE test vector for `"hello world"`, and the HMAC matches Python's own `hmac.new(key,
msg, hashlib.sha256).hexdigest()` bit for bit. Nothing here is a simplified or teaching version
of the algorithm.

## The modules

| Module | What it does |
| --- | --- |
| `crypto.crc32` | IEEE CRC-32, plus `crc32_combine` for the checksum of two pieces already hashed separately without re-reading either one |
| `crypto.hmac` | keyed HMAC-SHA256 and a constant-shape verify that returns a boolean rather than a checksum to compare yourself |
| `crypto.base64` | standard and URL-safe base64, encode and decode, as the four functions you'd expect |
| `crypto.pbkdf2` | PBKDF2-HMAC-SHA256 key derivation, plus the byte-level building blocks (`sha256_bytes`, `hmac_sha256_bytes`, `xor_byte_lists`) it's built from, exposed because they're independently useful |
| `crypto.chacha20` | the ChaCha20 stream cipher — block generation, encrypt, decrypt, and the state-mixing primitives (`quarter_round`, `rotl32`) underneath it |
| `crypto.hash_chain` | a Merkle tree: build a root from leaves, produce a proof for one leaf, and verify a leaf against a root and proof without the rest of the tree |
| `crypto.aes_sbox` | the AES S-box and its inverse, `shift_rows`/`inv_shift_rows`, and `add_round_key` — round primitives, not a complete AES cipher (see below) |
| `crypto.uuid` | RFC 4122 version-4 UUIDs, as a string or as unformatted hex |

## Verification is a boolean, not a checksum comparison

`hmac_sha256_verify` and `merkle_verify` both return `Bool` rather than making you recompute a
value and compare it yourself:

```python
mac = runtime.execute("crypto.hmac", "hmac_sha256", ["secret-key", "hello world"])["result"]

runtime.execute("crypto.hmac", "hmac_sha256_verify",
                ["secret-key", "hello world", mac])["result"]
# True

runtime.execute("crypto.hmac", "hmac_sha256_verify",
                ["secret-key", "hello world", mac[:-1] + "0"])["result"]
# False — one changed hex digit is a different tag
```

## A key derivation is one call, not an iteration loop you write

```python
password = [ord(c) for c in "hunter2"]
salt = [ord(c) for c in "somesalt"]

dk = runtime.execute("crypto.pbkdf2", "pbkdf2_hmac_sha256",
                     [password, salt, 1000, 32])["result"]

runtime.execute("crypto.pbkdf2", "bytes_to_hex", [dk])["result"]
# "ba747b3506de4489c52d9ac4e030804170280318f095e6c814704e3d6ca9ad9a"
```

`iterations` and `dk_len` are both explicit arguments, not defaults buried in the kernel — the
call site is where an iteration count gets decided, and it is the call site's job to decide it
deliberately rather than inherit whatever the library shipped with.

## A stream cipher decrypts by encrypting again

ChaCha20 is a keystream generator XORed against the input, so decryption is the identical
operation run on the ciphertext:

```python
key = list(range(32))          # 32-byte key
nonce = list(range(12))        # 12-byte nonce
plaintext = [ord(c) for c in "hello world"]

ct = runtime.execute("crypto.chacha20", "chacha20_encrypt",
                     [plaintext, key, nonce])["result"]
# [123, 87, 40, 68, 55, 200, 134, 223, 197, 6, 177]

pt = runtime.execute("crypto.chacha20", "chacha20_decrypt", [ct, key, nonce])["result"]
"".join(chr(b) for b in pt)
# "hello world"
```

The same `(key, nonce)` pair used for both directions is exactly the property that makes reusing
a nonce with the same key catastrophic — the keystream repeats and two ciphertexts XORed together
cancel it out, leaving the two plaintexts XORed against each other. Nothing about the call
signature enforces nonce uniqueness; that discipline is the caller's.

## A Merkle proof is checked against a root, not against the tree

```python
leaves = [runtime.execute("crypto.hash_chain", "simple_hash", [[i]])["result"]
          for i in range(4)]
# [84696351, 67918732, 118251589, 101473970]

root = runtime.execute("crypto.hash_chain", "merkle_root", [leaves])["result"]
# 3059960042

proof = runtime.execute("crypto.hash_chain", "merkle_proof", [leaves, 2])["result"]
# [101473970, 1432331051] — the sibling values needed to recompute the root from leaf 2

runtime.execute("crypto.hash_chain", "merkle_verify",
                [leaves[2], proof, 2, root])["result"]
# True

# the same proof, offered for the WRONG leaf
runtime.execute("crypto.hash_chain", "merkle_verify",
                [leaves[0], proof, 2, root])["result"]
# False
```

`merkle_verify` never touches `leaves` — it recomputes a root from the one leaf, its index, and
the proof, and compares that to the root you already have. That is the entire point of a Merkle
proof: proving membership without transmitting or trusting the rest of the tree.

{% hint style="warning" %}
**`crypto.aes_sbox` is round primitives, not a complete cipher.** `sub_bytes`, `shift_rows`,
`add_round_key` and their inverses are the pieces a full AES implementation composes across ten
or more rounds with a key schedule in between — they are exposed because they are independently
useful (as substitution/permutation building blocks), not as a drop-in AES encrypt/decrypt call.
Round-tripping one round proves the primitives are correct, not that a cipher exists:

```python
state = list(range(16))

sub = runtime.execute("crypto.aes_sbox", "sub_bytes", [state])["result"]
# [99, 124, 119, 123, 242, 107, 111, 197, 48, 1, 103, 43, 254, 215, 171, 118]
# byte 0 -> 99 (0x63), byte 1 -> 124 (0x7c) — the published AES S-box, unmodified

runtime.execute("crypto.aes_sbox", "inv_sub_bytes", [sub])["result"] == state
# True
```

If you need AES itself, encrypt with `crypto.chacha20` or build the cipher from these
primitives yourself — this module does not assemble them into one.
{% endhint %}

## See also

* [Audit and evidence](../trust/audit-and-evidence.md) — the audit export's own `X-Content-SHA256` verification, the same "recompute and compare" shape as `hmac_sha256_verify` above
* [Declared capabilities](capabilities.md) — what each kernel says about determinism, seeds and cost
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
