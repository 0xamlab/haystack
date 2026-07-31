"""
canonical.float_repr — one frozen shortest-round-trip Float64 -> text. Zero Python.

Where this sits, and the boundary that must not move
----------------------------------------------------
`canonical.encode.write_float` hashes a Float64 as its IEEE-754 **bit pattern**. That is
the right design for hashing and nothing here changes it: a hash needs no text form, and
introducing one would make the digest depend on a formatter.

This module is for the other half — every place a float becomes **text**: a JSON response,
a log line, a plan echoed back to a caller, a golden vector in a test. There the two
languages on either side of the wire disagree, starting at the first value:

    Python  repr(1.0)                 -> "1.0"        JS  String(1.0)         -> "1"
    Python  repr(-0.0)                -> "-0.0"       JS  String(-0)          -> "0"
    Python  json.dumps(float("nan"))  -> "NaN"        JS  JSON.stringify(NaN) -> "null"
    Python  repr(1e21)                -> "1e+21"      JS  String(1e21)        -> "1e+21"
    Python  repr(1e20)                -> "1e+20"      JS  String(1e20)        -> "100000000000000000000"

So "each side formats locally and they happen to agree" is broken before it ships, exactly
as `canonical/__init__.mojo` says for hashing. One spelling is frozen here instead.

MEASURED: Mojo's own `String(Float64)` does not round-trip, and neither does `Float64(String)`
----------------------------------------------------------------------------------------------
This module was expected to be a thin wrapper over `String(Float64)`, which looks
shortest-round-trip on every hand-picked value. It is not. Over a 199,903-value sweep of
finite binade-uniform bit patterns (`state = state*6364136223846793005 + 1442695040888963407`,
seed `0x243F6A8885A308D3`, skipping the `0x7FF` exponent), cross-checked against CPython as
the reference:

* **52 values (0.026%) — formatter.** `String(v)` produced a decimal that names a DIFFERENT
  double, one ULP away, in every language. It emitted 14-16 significant digits where 16-17
  were required. Example: bits `4856560017543203705` printed `4.94657509214361e+16`, which
  is the double `4856560017543203704`. All 52 sat in the decimal-exponent band 16..18.
* **172 values (0.086%) — parser.** `String(v)` was correct (byte-identical to CPython's
  `repr`, and CPython's `float()` maps it back to the same bits) while Mojo's own
  `Float64(String)` returned a neighbouring double. Concentrated in the 1e16..1e22 band but
  present as far out as 1e-252 and 1e+257.

Two consequences shape this file:

1. **Nothing here calls `String(Float64)`.** The digits are generated from an exact decimal
   expansion of the bit pattern, so the 0.026% formatter class cannot reach the wire.
2. **The round-trip property is proved, not tested against a parser.** A bit-pattern
   round-trip test written the obvious way — format, `Float64(...)`, compare bits — would
   have reported failures for 0.086% of *correct* strings and passed some incorrect ones.
   `round_trips()` instead decides, by exact integer arithmetic, whether a decimal lies
   strictly inside the value's rounding interval. That is a statement about every
   correctly-rounded parser (IEEE-754 / ECMA-262 `Number()` / `strtod` / CPython `float()`),
   not about the one in this toolchain.

The frozen spelling, and why each choice is the choice
------------------------------------------------------
`canonical_float(v)` emits, for finite `v`:

* **The shortest decimal that round-trips**, correctly rounded, ties to even. Shortest so the
  text is the value's identity rather than one of 17 paddings of it; proved per call rather
  than assumed (`shortest_proved`).
* **`1.0`, not `1`.** A form that loses the float/int distinction is not canonical — a plan
  echoed back must not turn a Float64 into something a schema reads as an integer. So the
  fixed form always carries a decimal point and at least one fractional digit. This is
  Python's `repr` rule; a JS caller reproduces the digits with `v.toExponential()`, which
  ECMA-262 defines as "as few digits as possible to uniquely specify the value", and then
  reformats per the rule below. Both directions are mechanical; `String(v)` in JS is not,
  because its thresholds differ (1e20 -> `100000000000000000000`, 1e21 -> `1e+21`).
* **`-0.0` keeps its sign.** This is a DELIBERATE asymmetry with `canonical.encode`, which
  normalises `-0.0` to `+0.0` because `-0.0 == 0.0` in every language here and equal values
  must hash equally. Text is bit-faithful; the hash is equality-faithful. Text has to be
  bit-faithful because its whole purpose is that the receiver rebuilds the same double, and
  the sign of a zero is the direction an underflowed product came from. The trap this creates
  is named rather than hidden: **text equality is not a proxy for hash equality.** Callers who
  want text whose equality classes match the hash call `hash_aligned_float()` instead, which
  is the only place the normalisation is spelled.
* **NaN and +-Inf are not JSON numbers, so they get no numeric text at all.** Emitting the
  bare tokens `nan`/`inf` was a real defect in `query/plan.mojo`: the response was not
  parseable by any JSON parser. Every String this module returns is a valid JSON value, and
  for a non-finite value that value is `null` — the same choice `JSON.stringify` makes, and
  the only one that cannot become a parse error downstream. `null` is ABSENCE, not `0.0`
  (rule 4): a fabricated zero would be indistinguishable from a real answer. The distinction
  between NaN, +Inf and -Inf is not lost, it is moved out of the number: `float_text()`
  returns `is_number = False`, a `class_code` and a `label` ("NaN" / "Infinity" /
  "-Infinity") for a separate field. There is no function here that can emit `nan`.
* **Exponent form when `exp10 < -4 or exp10 >= 16`**, spelled `1e-05`, `1e+16`, `5e-324`:
  sign always present, at least two exponent digits, no `.0` on a single-digit mantissa.
  Thresholds match CPython's `repr` (and what this Mojo toolchain already emits), so adopting
  them keeps every existing golden vector and log line stable; picking a different threshold
  would have rewritten text nobody asked to change.

Status/class codes: `canonical` owns 700-709
--------------------------------------------
Per rule 4e, ranges are per package. 700-703 are spent; 704-709 are free. `graph_analytics`
holds 0-13, `hostio` 050-099, `optimization` 80-139, `tensorx`/`forecasting` 300-319,
`gemm` 320-339, `causal_inference` 340-359.

Reachability
------------
`canonical` is in `_SKIP_RUNTIME_DIRS` (`apps/runtime/mojo_inventory.py`), so nothing in this
package enters the runtime library contract or the A-Z generated suite, and rule 2 does not
constrain these signatures. They are written to satisfy it anyway — flat scalars and lists in,
a struct declared IN THIS FILE out — so that removing `canonical` from the skip set is a
one-line change rather than an API rewrite. The capability block below is likewise not
scanned today (`build_capability_manifest` iterates the same filtered set); it was validated
by calling `parse_runtime_capability_specs` on this file directly so that it is correct on the
day it starts being read.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: none
golden_vectors: mojo/tests/libs/test_canonical_float_repr.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""
from std.math import isinf, isnan
from std.memory import bitcast

comptime FLOAT_TEXT_VERSION: String = "algenta-float-repr/v1"

# ── class codes: canonical owns 700-709 (rule 4e) ─────────────────────────────
comptime FLOAT_FINITE: Int = 700
comptime FLOAT_NAN: Int = 701
comptime FLOAT_POS_INF: Int = 702
comptime FLOAT_NEG_INF: Int = 703

# The one text a non-finite value gets. A JSON value in every parser; never `nan`.
comptime JSON_ABSENT: String = "null"

# 17 = ceil(53 * log10(2)) + 1: enough significant digits to name any binary64
# uniquely. The search below never needs it (shortest is usually 15-17) but the
# ceiling is what makes the loop terminate at a proved answer instead of a guess.
comptime MAX_SIGNIFICANT_DIGITS: Int = 17

# Fixed notation for exp10 in [-4, 16), exponent notation outside it. CPython's
# repr thresholds; see the frozen-spelling notes above.
comptime EXP_FIXED_LOW: Int = -4
comptime EXP_FIXED_HIGH: Int = 16

# ── exact decimal arithmetic, base 1e9 ────────────────────────────────────────
# Every quantity compared below (the value, both rounding-interval endpoints, a
# candidate decimal) is an integer times a power of ten, held EXACTLY. Base 1e9
# rather than base 10 is 9x fewer limb operations; the multipliers are chosen so
# limb * k + carry cannot wrap a UInt64:
#   limb <= 1e9-1, 2^29 = 536870912  -> 5.37e17 + 5.4e8  < 1.8e19  ok
#   limb <= 1e9-1, 5^12 = 244140625  -> 2.44e17 + 2.5e8  < 1.8e19  ok
#   limb <= 1e9-1, 10^9              -> 1.00e18 + 1.0e9  < 1.8e19  ok
comptime LIMB_BASE: UInt64 = 1000000000
comptime LIMB_DIGITS: Int = 9
comptime CHUNK_POW2: Int = 29
comptime CHUNK_POW2_VALUE: UInt64 = 536870912
comptime CHUNK_POW5: Int = 12
comptime CHUNK_POW5_VALUE: UInt64 = 244140625

# Bounds for `round_trips`, whose text comes from a caller rather than from a
# Float64's exponent field. Rule 1c: bound a declared dimension against what the
# payload contains, and count the arrays per unit.
#   <= 1200 bytes of text  -> <= 1200 significant digits -> <= 134 limbs
#   exponent field |e| <= 4000, so s >= -(4000 + 1200)
# `_cmp_dec` bounds its own scaling by the two operands' digit counts (see there),
# so the widest array either comparison allocates is ~(1200 + 780 + 2) digits
# = 221 limbs = 1.8 KB. Two of those per call, freed on return.
comptime MAX_TEXT_BYTES: Int = 1200
comptime MAX_TEXT_EXPONENT: Int = 4000


@fieldwise_init
struct FloatText(Copyable, Movable):
    """The full report for one Float64: text plus what the text does and does not claim.

    `text` is ALWAYS a valid JSON value, so no caller can emit an unparseable token.
    When `is_number` is False the value has no JSON number form at all and `text` is
    `null` — absence, not a fabricated `0.0` (rule 4). `label` and `class_code` carry
    the distinction between NaN, +Inf and -Inf that `null` cannot.
    """

    var text: String
    var is_number: Bool
    var class_code: Int
    var label: String
    var significant_digits: Int
    var round_trip_proved: Bool
    var shortest_proved: Bool


@fieldwise_init
struct _Dec(Copyable, Movable):
    """A non-negative decimal held exactly: `limbs` (base 1e9, LSB first) * 10^s."""

    var limbs: List[UInt64]
    var s: Int


@fieldwise_init
struct _Bits(Copyable, Movable):
    """A finite Float64 taken apart: |value| = m * 2^e2, with the biased exponent kept.

    `be` is retained because the rounding interval is asymmetric exactly when the
    significand sits at the bottom of a binade (`m == 2^52` with `be >= 2`), and that
    is not recoverable from `m` and `e2` alone.
    """

    var neg: Bool
    var m: UInt64
    var e2: Int
    var be: Int


@fieldwise_init
struct _Bracket(Copyable, Movable):
    """|value| with the two exact halfway points that surround it, over one shared power."""

    var value: _Dec
    var lo: _Dec
    var hi: _Dec


@fieldwise_init
struct _Cand(Copyable, Movable):
    """A candidate decimal: `digits` (MSB first) with value = 0.digits * 10^decexp."""

    var digits: List[UInt8]
    var decexp: Int
    var valid: Bool


@fieldwise_init
struct _Parsed(Copyable, Movable):
    """Text scanned into an exact decimal. `valid` is False for anything malformed."""

    var valid: Bool
    var neg: Bool
    var limbs: List[UInt64]
    var s: Int


fn float_text_version() -> String:
    """Identity of this spelling. Bump only alongside a deliberate text change."""
    return FLOAT_TEXT_VERSION


fn _limbs_from_u64(value: UInt64) -> List[UInt64]:
    var out = List[UInt64]()
    var v = value
    if v == 0:
        out.append(0)
        return out^
    while v > 0:
        out.append(v % LIMB_BASE)
        v = v // LIMB_BASE
    return out^


fn _mul_small(mut limbs: List[UInt64], k: UInt64):
    """`limbs *= k` for k < 2^30 (or 1e9). No wrap: see the base-1e9 note above."""
    var carry: UInt64 = 0
    for i in range(len(limbs)):
        var cur = limbs[i] * k + carry
        limbs[i] = cur % LIMB_BASE
        carry = cur // LIMB_BASE
    while carry > 0:
        limbs.append(carry % LIMB_BASE)
        carry = carry // LIMB_BASE


fn _add_small(mut limbs: List[UInt64], k: UInt64):
    """`limbs += k` for k < 1e9."""
    var carry = k
    var i = 0
    while carry > 0:
        if i >= len(limbs):
            limbs.append(carry % LIMB_BASE)
            carry = carry // LIMB_BASE
        else:
            var cur = limbs[i] + carry
            limbs[i] = cur % LIMB_BASE
            carry = cur // LIMB_BASE
        i += 1


fn _mul_pow2(mut limbs: List[UInt64], e: Int):
    """`limbs *= 2^e`, e >= 0. Callers derive e from a Float64 exponent, so e <= 971."""
    var remaining = e
    while remaining >= CHUNK_POW2:
        _mul_small(limbs, CHUNK_POW2_VALUE)
        remaining -= CHUNK_POW2
    if remaining > 0:
        var k: UInt64 = 1
        for _ in range(remaining):
            k *= 2
        _mul_small(limbs, k)


fn _mul_pow5(mut limbs: List[UInt64], e: Int):
    """`limbs *= 5^e`, e >= 0. Bounded by the same exponent field: e <= 1076."""
    var remaining = e
    while remaining >= CHUNK_POW5:
        _mul_small(limbs, CHUNK_POW5_VALUE)
        remaining -= CHUNK_POW5
    if remaining > 0:
        var k: UInt64 = 1
        for _ in range(remaining):
            k *= 5
        _mul_small(limbs, k)


fn _mul_pow10(mut limbs: List[UInt64], e: Int):
    """`limbs *= 10^e`, e >= 0. Whole limbs shift; the remainder is one small multiply."""
    if e <= 0:
        return
    var whole = e // LIMB_DIGITS
    var rem = e % LIMB_DIGITS
    if whole > 0:
        var shifted = List[UInt64]()
        for _ in range(whole):
            shifted.append(0)
        for i in range(len(limbs)):
            shifted.append(limbs[i])
        limbs = shifted^
    if rem > 0:
        var k: UInt64 = 1
        for _ in range(rem):
            k *= 10
        _mul_small(limbs, k)


fn _is_zero(limbs: List[UInt64]) -> Bool:
    for i in range(len(limbs)):
        if limbs[i] != 0:
            return False
    return True


fn _digit_count(limbs: List[UInt64]) -> Int:
    """Decimal digits in `limbs`; 1 for zero."""
    var top = len(limbs) - 1
    while top > 0 and limbs[top] == 0:
        top -= 1
    if top < 0:
        return 1
    var head = limbs[top]
    var head_digits = 1
    var scale: UInt64 = 10
    while head_digits < LIMB_DIGITS and head >= scale:
        head_digits += 1
        scale *= 10
    return top * LIMB_DIGITS + head_digits


fn _cmp_limbs(a: List[UInt64], b: List[UInt64]) -> Int:
    var ta = len(a) - 1
    while ta > 0 and a[ta] == 0:
        ta -= 1
    var tb = len(b) - 1
    while tb > 0 and b[tb] == 0:
        tb -= 1
    if ta < 0 or tb < 0:
        # Empty means zero; no producer here makes one, but indexing -1 would abort.
        var az = ta < 0 or _is_zero(a)
        var bz = tb < 0 or _is_zero(b)
        if az and bz:
            return 0
        return -1 if az else 1
    if ta != tb:
        return -1 if ta < tb else 1
    var i = ta
    while i >= 0:
        if a[i] != b[i]:
            return -1 if a[i] < b[i] else 1
        i -= 1
    return 0


fn _cmp_dec(a: _Dec, b: _Dec) -> Int:
    """Exact three-way compare of two non-negative decimals. No rounding anywhere.

    The magnitude shortcut is what BOUNDS the scaling: a nonzero integer with `d`
    digits lies in `[10^(d-1+s), 10^(d+s))`, so when one interval is entirely above
    the other the answer is decided with no allocation at all. Only when the decimal
    exponents are within one of each other does it scale, and then the shift is at
    most `digits(a) + digits(b) + 2` — a bound the operands carry with them, rather
    than a constant that a caller's exponent could walk past.
    """
    var a_zero = _is_zero(a.limbs)
    var b_zero = _is_zero(b.limbs)
    if a_zero and b_zero:
        return 0
    if a_zero:
        return -1
    if b_zero:
        return 1
    var da = _digit_count(a.limbs)
    var db = _digit_count(b.limbs)
    if da - 1 + a.s >= db + b.s:
        return 1
    if db - 1 + b.s >= da + a.s:
        return -1
    if a.s == b.s:
        return _cmp_limbs(a.limbs, b.limbs)
    if a.s > b.s:
        var al = a.limbs.copy()
        _mul_pow10(al, a.s - b.s)
        return _cmp_limbs(al, b.limbs)
    var bl = b.limbs.copy()
    _mul_pow10(bl, b.s - a.s)
    return _cmp_limbs(a.limbs, bl)


fn _add_limbs(mut acc: List[UInt64], other: List[UInt64]):
    """`acc += other`. Both are base-1e9, so a sum of two limbs plus carry cannot wrap."""
    var carry: UInt64 = 0
    var n = len(other) if len(other) > len(acc) else len(acc)
    for i in range(n):
        var total = carry
        if i < len(other):
            total += other[i]
        if i < len(acc):
            total += acc[i]
            acc[i] = total % LIMB_BASE
        else:
            acc.append(total % LIMB_BASE)
        carry = total // LIMB_BASE
    while carry > 0:
        acc.append(carry % LIMB_BASE)
        carry = carry // LIMB_BASE


fn _mul_u64(base: List[UInt64], factor: UInt64) -> List[UInt64]:
    """`base * factor` for factor < 1e18, as two limb-wide multiplies and one add.

    `_mul_small` alone cannot do this: its factor must stay under ~2^30 or `limb * k`
    wraps. Splitting the factor into its two base-1e9 limbs keeps every product inside
    the bound proved at the top of the file. Every caller's factor is at most
    `4 * (2^53 - 1) + 2 < 3.61e16`, so the high half is under 1e9 as required.
    """
    var high = factor // LIMB_BASE
    var low = factor % LIMB_BASE
    var out = List[UInt64]()
    if high > 0:
        out = base.copy()
        _mul_small(out, high)
        _mul_pow10(out, LIMB_DIGITS)
    else:
        out.append(0)
    if low > 0:
        var part = base.copy()
        _mul_small(part, low)
        _add_limbs(out, part)
    return out^


fn _common_power(e2: Int) -> _Dec:
    """`2^e2` as an exact decimal, for e2 in [-1078, 971].

    For e2 >= 0 that is the integer `2^e2`. For e2 < 0 it is `5^(-e2) * 10^(e2)`, exact
    because `2^-k` has exactly k decimal fraction digits. The worst case (`e2 = -1078`) is
    90 chunk multiplies over at most 86 limbs.

    Factored out because a value and BOTH its halfway points share one power of two —
    `m * 2^e2`, `(2m±1) * 2^(e2-1)` and `(4m-1) * 2^(e2-2)` all rescale to `A * 2^(e2-2)`.
    Computing the expansion once and multiplying by three small integers, instead of three
    separate expansions, is where most of the measured 3.3x came from.
    """
    var limbs = List[UInt64]()
    limbs.append(1)
    if e2 >= 0:
        _mul_pow2(limbs, e2)
        return _Dec(limbs^, 0)
    _mul_pow5(limbs, -e2)
    return _Dec(limbs^, e2)


fn _exact_dec(m: UInt64, e2: Int) -> _Dec:
    """`m * 2^e2` as an exact decimal, for m < 1e18 and e2 in [-1078, 971]."""
    var power = _common_power(e2)
    return _Dec(_mul_u64(power.limbs, m), power.s)


fn _append_limb_digits(mut out: List[UInt8], value: UInt64, pad: Bool):
    var divisor: UInt64 = 100000000
    var started = pad
    for _ in range(LIMB_DIGITS):
        var d = (value // divisor) % 10
        if d != 0:
            started = True
        if started:
            out.append(UInt8(d))
        divisor = divisor // 10
    if len(out) == 0:
        out.append(0)


fn _digits_msb(limbs: List[UInt64]) -> List[UInt8]:
    """Decimal digits of `limbs`, most significant first, no leading zeros."""
    var out = List[UInt8]()
    if len(limbs) == 0:
        out.append(0)
        return out^
    var top = len(limbs) - 1
    while top > 0 and limbs[top] == 0:
        top -= 1
    _append_limb_digits(out, limbs[top], False)
    var i = top - 1
    while i >= 0:
        _append_limb_digits(out, limbs[i], True)
        i -= 1
    return out^


fn _limbs_from_digits(digits: List[UInt8]) -> List[UInt64]:
    """Digits (MSB first) to limbs, nine at a time so the cost is per limb not per digit."""
    var limbs = List[UInt64]()
    limbs.append(0)
    var i = 0
    while i < len(digits):
        var take = LIMB_DIGITS
        if i + take > len(digits):
            take = len(digits) - i
        var chunk: UInt64 = 0
        var scale: UInt64 = 1
        for k in range(take):
            chunk = chunk * 10 + UInt64(digits[i + k])
            scale *= 10
        _mul_small(limbs, scale)
        _add_small(limbs, chunk)
        i += take
    return limbs^


fn _decompose(value: Float64) -> _Bits:
    """|value| = m * 2^e2 for a finite `value`. m == 0 exactly for +-0.0."""
    var bits = bitcast[DType.uint64](value)
    var neg = (bits >> 63) != 0
    var be = Int((bits >> 52) & 0x7FF)
    var frac = bits & 0xFFFFFFFFFFFFF
    if be == 0:
        return _Bits(neg, frac, -1074, 0)
    return _Bits(neg, frac | (UInt64(1) << 52), be - 1075, be)


fn _bracket(bits: _Bits) -> _Bracket:
    """|value| and the two exact halfway points around it. Requires m > 0.

    All three are expressed over the SAME power, `2^(e2-2)`, so one expansion serves them
    all: `|v| = 4m`, `hi = 4m + 2`, `lo = 4m - 2` — or `4m - 1` at the bottom of a binade
    (`m == 2^52` with `be >= 2`), where the predecessor is a quarter of an ULP away instead
    of half because the gap halves there. `be >= 2` and not `be >= 1`: the least normal
    shares its exponent with the subnormals, so no gap change happens at that step.

    The upper point needs no such case. The successor is `(m + 1) * 2^e2` even when it
    carries into the next binade, since `2^53 * 2^e2 == 2^52 * 2^(e2+1)`, and above the
    largest finite value the point still marks where a parser starts returning infinity.

    Rescaling to a shared power is not just a speed trick: it also removes the chance of
    the value and its bounds being derived through two different expressions, which is how
    an interval test ends up bounding something other than what it is judging (rule 4b).
    """
    var power = _common_power(bits.e2 - 2)
    var mid = 4 * bits.m
    var low_multiplier = mid - 2
    if bits.m == (UInt64(1) << 52) and bits.be >= 2:
        low_multiplier = mid - 1
    return _Bracket(
        _Dec(_mul_u64(power.limbs, mid), power.s),
        _Dec(_mul_u64(power.limbs, low_multiplier), power.s),
        _Dec(_mul_u64(power.limbs, mid + 2), power.s),
    )


fn _cand_dec(cand: _Cand) -> _Dec:
    return _Dec(_limbs_from_digits(cand.digits), cand.decexp - len(cand.digits))


fn _names_value(cand: _Cand, lo: _Dec, hi: _Dec, tie_wins: Bool) -> Bool:
    """True when a correctly-rounded parser maps `cand` to the value `lo`/`hi` bound.

    Inside the interval is the easy part. The boundary is the part worth writing down: a
    decimal exactly ON a halfway point is resolved by round-to-nearest **ties to even**,
    which IEEE-754, ECMA-262 `Number()` and C `strtod` all mandate, so the outcome is
    deterministic rather than implementation-defined. The even neighbour is the value
    itself exactly when its significand is even, which is what `tie_wins` carries in —
    both neighbours of an even significand are odd, at a binade bottom included.

    An earlier version of this function refused every boundary case as "conservative".
    That was not conservative, it was WRONG in two ways: it emitted 17 digits where 16
    round-trip (measured: 90 of 300,000 values, e.g. bits 4854345028385918414), so the
    text stopped matching what a CPython caller's `repr` produces — the divergence this
    module exists to remove — and it reported `shortest_proved = True` for a form it had
    just proved was not the shortest. A tolerance-shaped decision has to come from the
    quantity being judged (rule 4b), and here that quantity is one bit of one significand.
    """
    var cd = _cand_dec(cand)
    var below = _cmp_dec(lo, cd)
    if below > 0:
        return False
    if below == 0 and not tie_wins:
        return False
    var above = _cmp_dec(cd, hi)
    if above > 0:
        return False
    if above == 0 and not tie_wins:
        return False
    return True


fn _names_shortest_at(
    digits: List[UInt8], decexp: Int, p: Int, lo: _Dec, hi: _Dec, tie_wins: Bool
) -> _Cand:
    """The `p`-digit decimal that names the value, or `valid = False` if none does.

    Only two candidates are ever worth testing at a given length: the two `p`-digit
    decimals that BRACKET the value. Any other `p`-digit decimal is farther out on one
    side than whichever of these two is on that side, so it cannot be inside an interval
    that these two miss — which is what makes "no `p`-digit decimal works" a proof rather
    than a failed guess. Nearest first, so when both work the closer one wins; that is the
    tie-break every other shortest-round-trip formatter uses, and it is why this agrees
    with CPython `repr` byte for byte.
    """
    var truncated = _truncate(digits, decexp, p)
    var up = _wants_round_up(digits, p, truncated.digits[p - 1])
    var nearest = _incremented(truncated) if up else truncated.copy()
    if _names_value(nearest, lo, hi, tie_wins):
        return nearest^
    var other = truncated.copy() if up else _incremented(truncated)
    if _names_value(other, lo, hi, tie_wins):
        return other^
    return _Cand(List[UInt8](), 0, False)


fn _truncate(digits: List[UInt8], decexp: Int, p: Int) -> _Cand:
    var out = List[UInt8]()
    var take = p if p < len(digits) else len(digits)
    for i in range(take):
        out.append(digits[i])
    return _Cand(out^, decexp, True)


fn _incremented(cand: _Cand) -> _Cand:
    """`cand` plus one in its last place, keeping the digit count."""
    var out = List[UInt8]()
    for i in range(len(cand.digits)):
        out.append(cand.digits[i])
    var i = len(out) - 1
    var carry = True
    while i >= 0 and carry:
        if out[i] == 9:
            out[i] = 0
        else:
            out[i] = out[i] + 1
            carry = False
        i -= 1
    if not carry:
        return _Cand(out^, cand.decexp, True)
    # All nines: 999 -> 1000. Keep p digits and raise the decimal exponent.
    var rolled = List[UInt8]()
    rolled.append(1)
    for _ in range(len(out) - 1):
        rolled.append(0)
    return _Cand(rolled^, cand.decexp + 1, True)


fn _wants_round_up(digits: List[UInt8], p: Int, last: UInt8) -> Bool:
    """Round-half-even on the EXACT tail, so no tie is decided by a truncated remainder."""
    if p >= len(digits):
        return False
    if digits[p] > 5:
        return True
    if digits[p] < 5:
        return False
    for i in range(p + 1, len(digits)):
        if digits[i] != 0:
            return True
    return (last % 2) == 1


fn _format(neg: Bool, digits: List[UInt8], decexp: Int) -> String:
    """The frozen spelling of `0.digits * 10^decexp`.

    Trailing zeros are stripped first. That does not change the decimal's value, so it
    cannot change what a parser produces — the round-trip proof survives it.
    """
    var n = len(digits)
    while n > 1 and digits[n - 1] == 0:
        n -= 1
    var exp10 = decexp - 1
    var out = String("")
    if neg:
        out += "-"
    if exp10 < EXP_FIXED_LOW or exp10 >= EXP_FIXED_HIGH:
        out += chr(48 + Int(digits[0]))
        if n > 1:
            out += "."
            for i in range(1, n):
                out += chr(48 + Int(digits[i]))
        out += "e"
        var ex = exp10
        if ex < 0:
            out += "-"
            ex = -ex
        else:
            out += "+"
        if ex < 10:
            out += "0"
        out += String(ex)
        return out
    if exp10 >= 0:
        var int_digits = exp10 + 1
        for i in range(int_digits):
            if i < n:
                out += chr(48 + Int(digits[i]))
            else:
                out += "0"
        out += "."
        if n > int_digits:
            for i in range(int_digits, n):
                out += chr(48 + Int(digits[i]))
        else:
            out += "0"
        return out
    out += "0."
    for _ in range(-exp10 - 1):
        out += "0"
    for i in range(n):
        out += chr(48 + Int(digits[i]))
    return out


fn float_class(value: Float64) -> Int:
    """One of FLOAT_FINITE / FLOAT_NAN / FLOAT_POS_INF / FLOAT_NEG_INF."""
    if isnan(value):
        return FLOAT_NAN
    if isinf(value):
        return FLOAT_POS_INF if value > 0.0 else FLOAT_NEG_INF
    return FLOAT_FINITE


fn float_class_name(code: Int) -> String:
    """Name for a class code; `unknown` for anything outside canonical's 700-709."""
    if code == FLOAT_FINITE:
        return "finite"
    if code == FLOAT_NAN:
        return "nan"
    if code == FLOAT_POS_INF:
        return "positive_infinity"
    if code == FLOAT_NEG_INF:
        return "negative_infinity"
    return "unknown"


fn float_text(value: Float64) -> FloatText:
    """Full report: the frozen text, plus what it is and is not claiming.

    For a finite value the text is the shortest decimal that provably round-trips, and
    both proofs are recomputed here rather than inherited: `round_trip_proved` is the
    interval test that SELECTED the digits, and `shortest_proved` says every shorter
    length was tried and rejected. A caller that trusts the text should assert both,
    because a "verified" flag is only as good as the condition behind it (rule 4d).

    @capability float_text
    complexity: O(1) — bounded by the binary64 exponent range, not by any input length
    counts: none
    @endcapability
    """
    if isnan(value):
        return FloatText(JSON_ABSENT, False, FLOAT_NAN, "NaN", 0, False, False)
    if isinf(value):
        if value > 0.0:
            return FloatText(JSON_ABSENT, False, FLOAT_POS_INF, "Infinity", 0, False, False)
        return FloatText(JSON_ABSENT, False, FLOAT_NEG_INF, "-Infinity", 0, False, False)
    var bits = _decompose(value)
    if bits.m == 0:
        # Both zeros are exact and each names itself; the sign is kept (see the header).
        var zero = String("-0.0") if bits.neg else String("0.0")
        return FloatText(zero, True, FLOAT_FINITE, String(""), 1, True, True)
    var bracket = _bracket(bits)
    var digits = _digits_msb(bracket.value.limbs)
    var decexp = len(digits) + bracket.value.s
    var lo = bracket.lo.copy()
    var hi = bracket.hi.copy()
    # Which way an exact-halfway candidate resolves is decided by this one bit, once,
    # rather than re-derived at each boundary comparison.
    var tie_wins = (bits.m % 2) == 0
    var limit = MAX_SIGNIFICANT_DIGITS if MAX_SIGNIFICANT_DIGITS < len(digits) else len(digits)
    # Binary search for the least length that names the value. Valid because the property
    # is MONOTONE in the length: a p-digit decimal padded with a zero is a (p+1)-digit
    # decimal of the same value, so if length p works every longer length does. That turns
    # 17 interval tests into ceil(log2(17)) = 5, and it matters — 96% of uniform bit
    # patterns need 15 or more digits (measured over 1,095,823 values), so a linear scan
    # from p = 1 pays for fourteen refusals before its first success.
    var best = -1
    var best_cand = _Cand(List[UInt8](), 0, False)
    var low = 1
    var high = limit
    while low <= high:
        var mid = (low + high) // 2
        var found = _names_shortest_at(digits, decexp, mid, lo, hi, tie_wins)
        if found.valid:
            best = mid
            best_cand = found^
            high = mid - 1
        else:
            low = mid + 1
    if best > 0:
        return FloatText(
            _format(bits.neg, best_cand.digits, best_cand.decexp),
            True,
            FLOAT_FINITE,
            String(""),
            best,
            True,
            True,
        )
    # Unreachable for a binary64: 17 significant digits always suffice. If it ever is
    # reached, the FULL exact expansion is emitted — that decimal IS the value, so the
    # round-trip still holds — and `shortest_proved` says plainly that it is not minimal.
    # Reporting a shortest form that was never proved would be the rule-4 failure.
    return FloatText(
        _format(bits.neg, digits, decexp),
        True,
        FLOAT_FINITE,
        String(""),
        len(digits),
        True,
        False,
    )


fn canonical_float(value: Float64) -> String:
    """The one frozen text for `value`. Always a valid JSON value.

    Finite: the shortest round-tripping decimal, `1.0` not `1`, `-0.0` sign kept.
    NaN / +-Inf: `null`, because they have no JSON number form and a bare `nan` is a
    response no parser accepts. Use `float_text` when the caller needs to tell those
    three apart, and `hash_aligned_float` when the text must share equality classes with
    `canonical.encode`.

    @capability canonical_float
    complexity: O(1) — bounded by the binary64 exponent range
    counts: none
    @endcapability
    """
    return float_text(value).text


fn hash_aligned_float(value: Float64) -> String:
    """Text whose equality classes match `canonical.encode.write_float`, not the bits.

    `write_float` normalises `-0.0` to `+0.0` (they compare equal, so they must hash
    equally) and collapses every NaN to one pattern. `canonical_float` does NOT follow,
    because text exists so the receiver can rebuild the same double. Those two policies
    disagreeing is a trap, so it is spelled out in exactly one place: this function.

    Consequence, and it is the point: `hash_aligned_float(-0.0) == "0.0"` does NOT
    bit-round-trip to `-0.0`. Use it for a cache key or a dedup fingerprint that has to
    agree with a digest; never for a value a caller will parse back.

    @capability hash_aligned_float
    complexity: O(1)
    counts: none
    @endcapability
    """
    if isnan(value):
        return JSON_ABSENT
    if value == 0.0:
        # Catches -0.0 exactly as write_float does, and for the same reason.
        return "0.0"
    return float_text(value).text


fn canonical_float_texts(values: List[Float64]) -> List[String]:
    """`canonical_float` over a whole list. No count argument, so no count to get wrong.

    @capability canonical_float_texts
    complexity: O(len(values))
    counts: none
    @endcapability
    """
    var out = List[String]()
    for i in range(len(values)):
        out.append(float_text(values[i]).text)
    return out^


fn canonical_float_array(values: List[Float64]) -> String:
    """The list as one JSON array, e.g. `[1.0,-0.0,null]`. Parseable by construction.

    @capability canonical_float_array
    complexity: O(len(values))
    counts: none
    @endcapability
    """
    var out = String("[")
    for i in range(len(values)):
        if i > 0:
            out += ","
        out += float_text(values[i]).text
    out += "]"
    return out


fn _parse_decimal(text: String) -> _Parsed:
    """Scan text into an exact decimal. Rejects rather than salvages.

    Failing open is the trap here: a scanner that reads `1.0garbage` as 1.0 would let
    `round_trips` certify text that a real parser refuses. JSON's grammar is also
    stricter than most `strtod`s — no leading `+`, no bare `.5`, no hex, no `Infinity`
    — and this follows JSON, since the text it judges is destined for JSON.
    """
    var empty = List[UInt64]()
    empty.append(0)
    var n = len(text)
    if n == 0 or n > MAX_TEXT_BYTES:
        return _Parsed(False, False, empty^, 0)
    var bytes = text.as_bytes()
    var i = 0
    var neg = False
    if bytes[0] == 45:  # '-'
        neg = True
        i = 1
    var digits = List[UInt8]()
    var frac_digits = 0
    var seen_dot = False
    var seen_digit = False
    var leading_zero = True
    var int_digits = 0
    while i < n:
        var c = bytes[i]
        if c >= 48 and c <= 57:
            seen_digit = True
            if seen_dot:
                frac_digits += 1
            else:
                int_digits += 1
            if leading_zero and c == 48:
                pass  # positional only; dropping it cannot change the integer formed
            else:
                leading_zero = False
                digits.append(UInt8(c - 48))
            i += 1
        elif c == 46 and not seen_dot:  # '.'
            if int_digits == 0:
                return _Parsed(False, False, empty^, 0)  # JSON needs a digit before '.'
            seen_dot = True
            i += 1
        elif c == 101 or c == 69:  # 'e' / 'E'
            break
        else:
            return _Parsed(False, False, empty^, 0)
    if not seen_digit:
        return _Parsed(False, False, empty^, 0)
    if seen_dot and frac_digits == 0:
        return _Parsed(False, False, empty^, 0)  # JSON needs a digit after '.'
    var exponent = 0
    if i < n:
        i += 1  # the 'e'
        if i >= n:
            return _Parsed(False, False, empty^, 0)
        var esign = 1
        if bytes[i] == 45:
            esign = -1
            i += 1
        elif bytes[i] == 43:
            i += 1
        if i >= n:
            return _Parsed(False, False, empty^, 0)
        var magnitude = 0
        while i < n:
            var c = bytes[i]
            if c < 48 or c > 57:
                return _Parsed(False, False, empty^, 0)
            magnitude = magnitude * 10 + Int(c - 48)
            if magnitude > MAX_TEXT_EXPONENT:
                return _Parsed(False, False, empty^, 0)
            i += 1
        exponent = esign * magnitude
    return _Parsed(True, neg, _limbs_from_digits(digits), exponent - frac_digits)


fn round_trips(value: Float64, text: String) -> Bool:
    """True when EVERY correctly-rounded parser maps `text` to `value`, bit for bit.

    This is the property that distinguishes shortest-round-trip from merely-close, and it
    is decided by exact integer arithmetic — `text` is compared against the two halfway
    points that bound `value` — NOT by calling a parser. That matters concretely: this
    toolchain's `Float64(String)` returns a neighbouring double for 0.086% of correct
    decimals (measured; see the header), so a parser-based check would report failures for
    correct text and could pass incorrect text.

    Every condition it checks, stated so a caller knows what the True covers (rule 4d):
    the text is a decimal JSON itself would accept; its sign matches (so `"0.0"` does not
    name `-0.0`); it lies within the halfway points around `value`; a decimal exactly ON a
    halfway point counts only when ties-to-even lands on `value`, i.e. when its significand
    is even; and a decimal below half the least subnormal names a zero of its own sign
    rather than nothing. What it does NOT cover: a non-finite `value` is always False, no
    matter the text — no decimal names NaN or Infinity, which is exactly why
    `canonical_float` gives those `null` instead of a number.

    @capability round_trips
    complexity: O(1) — bounded by MAX_TEXT_BYTES, not by the value
    counts: none
    @endcapability
    """
    if isnan(value) or isinf(value):
        return False
    var parsed = _parse_decimal(text)
    if not parsed.valid:
        return False
    var bits = _decompose(value)
    if parsed.neg != bits.neg:
        return False
    var cand = _Dec(parsed.limbs.copy(), parsed.s)
    var tie_wins = (bits.m % 2) == 0
    if bits.m == 0:
        # Half of the least subnormal. Below it every parser underflows to a zero, and the
        # sign was matched above, so `-1e-400` names -0.0 and `0.0` names +0.0. Exactly ON
        # the half goes to zero too: zero's significand is even and the least subnormal's
        # is 1, so `tie_wins` is unconditionally True here — the same rule, not an exception.
        var half_min = _exact_dec(1, -1075)
        var at_half = _cmp_dec(cand, half_min)
        return at_half < 0 or (at_half == 0 and tie_wins)
    var bracket = _bracket(bits)
    var lo = bracket.lo.copy()
    var hi = bracket.hi.copy()
    var below = _cmp_dec(lo, cand)
    if below > 0 or (below == 0 and not tie_wins):
        return False
    var above = _cmp_dec(cand, hi)
    return above < 0 or (above == 0 and tie_wins)
