---
icon: database
description: Bit-exact float64 weight serialization for saving and restoring trained kernels.
---

# Bit-exact weight serialization

`serialization_io` persists named Float64 arrays as a versioned string —
replacing pickle / json / numpy.save weight dumps — with **bit-exact**
round-trips. The kernel stays pure (string in, string out); the caller
persists the string to a file, KV store, or receipt log. Unlike rounded
decimal formatting, `weights_from_string(weights_to_string(...))`
reproduces every Float64 bit for bit. Zero Python imports.

## The modules

| Module | What it does |
| --- | --- |
| `serialization_io` | bit-exact Float64 weight serialization to a versioned string and back — replacing pickle / json / numpy.save weight dumps, with `weights_from_string(weights_to_string(...))` reproducing every bit |

## Functions

| Function | What it does |
|---|---|
| `WeightsBundle` | Parse result: `ok` flag plus parallel `names` / `arrays` lists. `ok == False` means corrupt/invalid payload — lists stay empty, never partial. |
| `weights_to_string(names, arrays)` | Serialize named Float64 arrays to the versioned line format below, one `\n`-terminated line per array. Deterministic: identical inputs yield identical strings. Empty string on names/arrays length mismatch. |
| `weights_from_string(s)` | Strict parse back to a `WeightsBundle`. Any corruption → `ok=False` with empty lists, never a silently wrong value. Blank lines and CRLF endings tolerated. |
| `string_checksum(s)` | FNV-1a 64-bit hash of the bytes, xor-folded to 32 bits, returned as an integer-valued Float64 in `[0, 2^32)` — for receipts/audit logs. |

## Line format and token grammar

```text
v1|<name>|<len>|<v0>,<v1>,...,<v(len-1)>
```

Value tokens: `0` / `-0` (signed zeros preserved), `inf` / `-inf` / `nan`,
plain decimal digits for integers with magnitude below 2^62, and otherwise
`<m>p<e>` — value = ±m·2^e with m an odd positive integer < 2^53 (C99
hex-float `p` notation). Only exact power-of-two scalings and integer digit
arithmetic are used, so subnormals, signed zeros, and max/min magnitudes
all survive. Test-verified tokens include `0.5 → 1p-1`,
`0.1 → 3602879701896397p-55`, max finite `→ 9007199254740991p971`,
min subnormal 2^-1074 `→ 1p-1074`, and `2^1023 → 1p1023`; the
plain-integer boundary is exact at 2^62 (`2^61` renders as digits,
`2^62 → 1p62`).

## Guarantees

- **Strict rejection**: unknown version tags, declared-length mismatches,
  malformed tokens, and out-of-domain tokens (`1p1024`, `1p-1075`,
  significand ≥ 2^53) all yield `ok=False`. One corrupt line poisons the
  whole bundle — no partial loads.
- **Names**: `|`, `\n`, `\r` bytes are replaced with `_`; ASCII names
  round-trip verbatim.
- **Performance**: single pass, ~70 simple ops per value; 10k typical
  weights serialize or parse well under 1 ms (worst-case subnormal-heavy
  payloads roughly double that, still sub-ms).

## Verification

The test suite round-trips a 200-value seeded stress set spanning the full
significand/exponent domain (all 200 bit-exact), checks hand-derived
IEEE-754 decompositions for every token form, and validates
`string_checksum` against the published FNV-1a 64 vectors (Noll):
`"" → 0xCBF29CE484222325`, `"a" → 0xAF63DC4C8601EC8C`,
`"foobar" → 0x85944171F73967E8` (folded). The checksum is deterministic
and tamper-sensitive: appending one byte changes it.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
