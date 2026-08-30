---
icon: lock
description: Categorical data encoding, closed-form sizing arithmetic for block-cipher modes, classical-cryptanalysis statistics, and closed-form blockchain/consensus metrics — none of which perform an actual cryptographic or ledger operation.
---

# Encoding and cryptography kernels

Four modules that sit next to the engine's real cryptography (`crypto.*`, covered in
[Data integrity and encoding](data-integrity-and-encoding.md)) but do something much narrower:
each one is a set of closed-form scalar formulas *about* a cipher, a classical attack, or a
blockchain, not a working implementation of one. `encoding` has nothing to do with cryptography at
all — it is categorical/ordinal data encoding, the `sklearn.preprocessing` replacement (label,
one-hot, ordinal, binary, frequency), and is unrelated to `positional_encoding` (a transformer
building block documented in
[Transformer attention variant kernels](transformer-attention-variant-kernels.md)) despite the
shared word. `encryption_modes` computes the sizes and round counts that fall out of choosing
ECB/CBC/CTR/GCM and an AES key length — block counts, padding bytes, ciphertext length, key-schedule
rounds — but never touches a byte of plaintext or key material. `cryptanalysis` is genuinely about
*breaking* weak ciphers: index of coincidence, the Friedman and Kasiski tests, chi-squared letter
frequency scoring, Shannon entropy, and brute-force time estimation are the actual toolkit a
classical cryptanalyst uses against substitution and polyalphabetic ciphers — but every function
takes already-counted frequencies or already-observed statistics as `Float64`/`Int` arguments; none
of them reads a ciphertext string or produces a decrypted one. `blockchain` is the same pattern
applied to distributed-ledger economics: block rewards, gas cost, staking APY, confirmation-depth
attack probability, and `merkle_tree_depth` — which returns `ceil(log2(n))` and nothing else, a
completely different thing from `crypto.hash_chain`'s actual Merkle tree (root/proof/verify over
real hash values, documented on the page linked above).

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("encoding", "label_encode", [["cat", "dog", "cat", "bird"]])["result"]
# [0, 1, 0, 2] — first-appearance order, not alphabetical

runtime.execute("encryption_modes", "ciphertext_length_cbc", [32, 16])["result"]
# 64 — 32 bytes of plaintext, block-aligned, so PKCS#7 adds a full 16-byte pad block,
# plus the 16-byte prepended IV: (2 data blocks + 1 pad block + 1 IV block) * 16

runtime.execute("cryptanalysis", "index_of_coincidence_2", [10, 10, 20])["result"]
# 0.47368421052631576 — (10*9 + 10*9) / (20*19); far above English's ~0.067,
# consistent with a near-uniform (not natural-language) letter distribution
```

## The modules

| Module | What it does |
| --- | --- |
| `encoding` | Categorical/ordinal data encoding: label encoding (first-appearance order) with its vocabulary and decode inverse, one-hot vectors, ordinal encoding against a caller-supplied order, MSB-first binary digit encoding, and count/total frequency encoding. |
| `encryption_modes` | Closed-form size and round-count arithmetic for block-cipher modes: ECB/CTR block counts, PKCS#7 padding bytes, CBC and GCM ciphertext length (with IV and tag accounted for), AEAD nonce+tag overhead, AES key-schedule round counts, a throughput estimate, and a key-bits-minus-known-attack security margin. |
| `cryptanalysis` | Classical cryptanalysis statistics: chi-squared letter-frequency scoring, index of coincidence (observed, expected-random, expected-English), the Friedman key-length estimator and the Kasiski GCD step, a Caesar-shift scorer, byte-level Hamming distance, 2- and 4-symbol Shannon entropy, brute-force time estimation, and avalanche-ratio scoring. |
| `blockchain` | Closed-form blockchain/DLT metrics: block-reward halving, a simplified hash-rate-to-difficulty estimate, transaction fee and gas cost, confirmation-depth attack probability, Merkle tree *depth* (not a tree), TPS, block-size utilization, staking APY, validator uptime, PBFT finality time, and token inflation rate. |

## `encoding`: categorical transforms, not cipher encoding

Six functions plus the `build_vocabulary` helper they share, all working over `List[String]` or
`List[Int]` with no notion of a byte, a cipher, or a key. `label_encode` assigns each unique label
an integer in the order it first appears (not sorted, not by frequency):

```python
runtime.execute("encoding", "build_vocabulary",
                [["cat", "dog", "cat", "bird"]])["result"]
# ["cat", "dog", "bird"] — unique labels, first-appearance order

runtime.execute("encoding", "label_decode", [[0, 1, 2], ["cat", "dog", "bird"]])["result"]
# ["cat", "dog", "bird"] — round-trips label_encode's output through the same vocabulary

runtime.execute("encoding", "ordinal_encode",
                [["low", "high", "med"], ["low", "med", "high"]])["result"]
# [0, 2, 1] — each value's index in the caller-supplied order, not the input order

runtime.execute("encoding", "binary_encode", [5, 4])["result"]
# [0, 1, 0, 1] — 5 in 4 bits, MSB first

runtime.execute("encoding", "frequency_encode", [["a", "a", "b", "a", "b"]])["result"]
# [0.6, 0.6, 0.4, 0.6, 0.4] — each element replaced by its own label's count/total
```

`label_decode` and `ordinal_encode` both have an explicit "not found" behavior rather than raising:
`label_decode` emits `"?"` for an out-of-range index, and `ordinal_encode` emits `-1` for a value
absent from `order` — a caller that doesn't check for either gets a value that silently looks like
data. `one_hot_encode` takes already-integer labels (run `label_encode` first if starting from
strings) and `n_classes` as an explicit argument rather than inferring it from the data, so it can
produce a wider matrix than any label in the input actually uses, or silently drop a label whose
value is `>= n_classes` (its row is then all zeros, indistinguishable from a genuine all-zero
encoding).

These are pinned in `tests/mojo/test_wave19.mojo` against the exact examples above, plus
`one_hot_encode([0, 1, 2], 3)` checked element-by-element in both `test_wave19.mojo` and
`test_wave9.mojo` (`[1,0,0]`, `[0,1,0]`, `[0,0,1]`) — not just smoke-tested.

## `encryption_modes`: sizing arithmetic, not a cipher

Every function here takes plain integers (byte counts, block sizes, key bits) and returns a size or
a count — there is no key, plaintext, or ciphertext argument anywhere in the module. `ecb_block_count`
and `parallel_blocks_ctr` compute the identical `ceil(data_length / block_size)` under two names
because the two modes reach the same block count for two different reasons: ECB needs one block-cipher
call per block, CTR can run all of them in parallel because each is independent.

`ciphertext_length_cbc` models PKCS#7 padding plus a prepended IV in one formula:

```python
runtime.execute("encryption_modes", "padding_pkcs7_bytes", [16, 16])["result"]
# 16 — a full pad block, because PKCS#7 always adds between 1 and block_size bytes,
# even when the data is already block-aligned

runtime.execute("encryption_modes", "ciphertext_length_cbc", [30, 16])["result"]
# 48 — ceil(30/16)=2 data blocks (already covers the 2-byte pad), + 1 IV block, * 16

runtime.execute("encryption_modes", "ciphertext_length_gcm", [100, 16])["result"]
# 116 — GCM is a stream cipher under the hood: no padding, just plaintext + the tag

runtime.execute("encryption_modes", "key_schedule_rounds_aes", [256])["result"]
# 14 — AES-256's round count; 128→10, 192→12, and anything else→0
```

`security_margin_bits(key_bits, known_attack_reduction)` is a bare subtraction
(`security_margin_bits(256, 2)` → `254`) — it has no table of real published attacks built in; the
reduction is whatever the caller supplies, so the function's honesty depends entirely on the caller
keeping it current.

{% hint style="warning" %}
**`ciphertext_length_cbc(0, 16)` returns 16, not 32.** PKCS#7 specifies a full pad block for
already-aligned plaintext, but the guard in this kernel is `plaintext_length % block_size == 0 and
plaintext_length > 0` — the `> 0` excludes empty input, so an empty plaintext gets no pad block, only
the IV block. Every non-empty aligned input (`ciphertext_length_cbc(32, 16)` → `64`) gets the full
extra block; only the zero-length edge case differs from what the formula's comment implies.
{% endhint %}

## `cryptanalysis`: classical-attack statistics, not a code-breaker

This module is genuinely about attacking weak ciphers — but at the level of "here are the numbers a
cryptanalyst computes," not "here is a function that takes ciphertext and returns plaintext." Every
function takes already-tallied counts, already-known frequencies, or an already-guessed shift as
plain arguments:

```python
runtime.execute("cryptanalysis", "expected_ic_english", [])["result"]
# 0.0667 — a constant baseline, not derived from any corpus at call time

runtime.execute("cryptanalysis", "friedman_key_length", [0.0667, 26])["result"]
# 1.0 — (0.0667 - 1/26) / (0.0667 - 1/26): an observed IC equal to English's own average
# implies a monoalphabetic cipher (effective key length 1)

runtime.execute("cryptanalysis", "friedman_key_length", [0.045, 26])["result"]
# 4.318823529411766 — a lower, more random-looking IC implies a longer polyalphabetic key

runtime.execute("cryptanalysis", "kasiski_distance_gcd", [12, 8])["result"]
# 4 — two repeated-trigram distances of 12 and 8 apart both divide evenly by 4,
# a candidate Vigenère key length

runtime.execute("cryptanalysis", "hamming_distance_bytes", [0xFF, 0x00])["result"]
# 8 — every bit differs between 0xFF and 0x00

runtime.execute("cryptanalysis", "brute_force_time_estimate", [16, 65536.0])["result"]
# 1.0 — a 16-bit keyspace (65536 keys) at 65536 guesses/sec takes 1 second
```

`avalanche_effect(changed_bits, total_bits)` is the diffusion metric used to judge a cipher or hash,
not to attack one: a good block cipher or hash flips close to half its output bits for a one-bit
input change (`avalanche_effect(64, 128)` → `0.5`), so a real avalanche measurement far from `0.5`
is itself evidence of a weak construction.

All twelve functions are pinned with hand-verified values in `tests/mojo/test_wave64.mojo` (not
just smoke-tested) — the index-of-coincidence, Friedman, Kasiski, entropy, and brute-force values
shown above are taken directly from that suite.

## `blockchain`: closed-form ledger and consensus metrics, not a chain

Twelve functions, each a one-line formula over plain `Float64`/`Int` arguments — there is no block
struct, no hash function, no signature, and no actual consensus loop anywhere in the module.

```python
runtime.execute("blockchain", "block_reward_halving", [50.0, 3])["result"]
# 6.25 — 50 / 2^3; matches Bitcoin's own 50 -> 25 -> 12.5 -> 6.25 BTC halving schedule

runtime.execute("blockchain", "gas_cost", [21000.0, 30.0])["result"]
# 0.00063 — a standard 21000-gas ETH transfer at 30 gwei/gas, in ETH

runtime.execute("blockchain", "confirmations_security", [6, 30.0])["result"]
# 0.000729 — (30/100)^6: a simplified geometric proxy for "probability an attacker
# holding 30% of hashrate out-mines 6 confirmations," not the Poisson model from
# Nakamoto's original analysis

runtime.execute("blockchain", "merkle_tree_depth", [1000])["result"]
# 10 — ceil(log2(1000)); a depth number only, no tree is built or hashed
```

{% hint style="warning" %}
**`finality_time_pbft`'s `n_validators` argument has no effect on the result.** The function always
returns `3.0 * round_time` — `finality_time_pbft(100, 2.0)` and a hypothetical
`finality_time_pbft(4, 2.0)` both return `6.0`. This models PBFT's fixed three-phase structure
(pre-prepare, prepare, commit) as three fixed rounds, but a real deployment's round time itself
grows with validator count (more validators, more messages per round) — that growth is not
represented here, so `n_validators` is accepted but currently inert. Two calls confirm this in
`tests/mojo/test_wave100.mojo`: `finality_time_pbft(100, 2.0)` → `6.0` and
`finality_time_pbft(21, 1.5)` → `4.5`, differing only because `round_time` changed.
{% endhint %}

All twelve functions are pinned with hand-verified values in `tests/mojo/test_wave100.mojo`
alongside `encryption_modes` — both modules share that one wave file — rather than relying on the
auto-generated smoke tests in `mojo/tests/libs/`.

## Verification notes

`mojo/tests/libs/test_encoding.mojo`, `test_encryption_modes.mojo`, `test_cryptanalysis.mojo`, and
`test_blockchain.mojo` are the auto-generated smoke suite: they call each function once with
placeholder arguments and check the result is finite (or just that the call doesn't crash), not that
it equals a specific number. The real, hand-verified numeric coverage for all four modules lives in
`tests/mojo/test_wave19.mojo` (`encoding`), `test_wave64.mojo` (`cryptanalysis`), and
`test_wave100.mojo` (`encryption_modes` and `blockchain`) — every worked example on this page is
taken from, or independently cross-checked against, those pinned assertions.

**Next:** see [Data integrity and encoding](data-integrity-and-encoding.md) for the engine's actual
cryptographic primitives (CRC-32, HMAC, ChaCha20, a real Merkle tree), or browse the
[runtime library catalog](runtime-library-catalog.md) for every module and function.
