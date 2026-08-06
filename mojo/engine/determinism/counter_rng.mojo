"""counter_rng — Philox4x64-10 counter-based randomness.

Stateless, addressable randomness: every draw is a pure function of its coordinates, so the same
logical draw yields the same value regardless of what a trajectory did beforehand. That is what makes
valid common random numbers possible when compared alternatives consume different numbers of draws.

rng_version = "philox4x64-10/v1"

Counter/key layout (FROZEN — changing it changes every value ever drawn):
    c0 = replication_id
    c1 = (dim0 << 32) | (dim1 << 16) | stream_id
    c2 = draw_index >> 2          word = draw_index & 3
    c3 = 0                        reserved
    k0 = master_seed
    k1 = scenario_id

Every distribution consumes a FIXED number of draws. Variable-consumption sampling (ziggurat,
rejection loops) would make draw_index depend on trajectory and reintroduce the coupling this design
removes.

The `dim0`/`dim1` coordinates are caller-defined (e.g. step and entity), and `stream_id` names an
independent stream — see determinism/streams.mojo for deriving one from a name. Bit widths and
packing are unchanged from the original layout, so values drawn before this generalisation still
reproduce exactly.
"""

from std.math import cos, log, sqrt

# ── Philox4x64 constants ──────────────────────────────────────────────────────

comptime PHILOX_M0: UInt64 = 0xD2E7470EE14C6C93
comptime PHILOX_M1: UInt64 = 0xCA5A826395121157
comptime PHILOX_W0: UInt64 = 0x9E3779B97F4A7C15
comptime PHILOX_W1: UInt64 = 0xBB67AE8584CAA73B

comptime GLOBAL_SENTINEL: UInt64 = 0xFFFF

# Stream ids 1-7 are reserved: they were assigned to named processes by the first
# consumer of this kernel, and reusing them for anything else would silently
# change values that consumer already drew. Derive new ids by name via
# determinism/streams.mojo, which hashes into the space above them.
comptime RESERVED_STREAM_MAX: UInt64 = 7

comptime TWO_POW_NEG_53: Float64 = 1.1102230246251565e-16
comptime TWO_PI: Float64 = 6.283185307179586


def _mul_hi64(a: UInt64, b: UInt64) -> UInt64:
    """High 64 bits of a 64x64 product, via 32-bit decomposition."""
    var a_lo = a & 0xFFFFFFFF
    var a_hi = a >> 32
    var b_lo = b & 0xFFFFFFFF
    var b_hi = b >> 32
    var p0 = a_lo * b_lo
    var p1 = a_hi * b_lo
    var p2 = a_lo * b_hi
    var p3 = a_hi * b_hi
    var mid = (p0 >> 32) + (p1 & 0xFFFFFFFF) + (p2 & 0xFFFFFFFF)
    return p3 + (p1 >> 32) + (p2 >> 32) + (mid >> 32)


def philox_word(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    dim0: UInt64, dim1: UInt64, stream_id: UInt64, draw_index: UInt64
) -> UInt64:
    """One 64-bit Philox4x64-10 output word for the given draw coordinates."""
    var c0 = replication_id
    var c1 = (dim0 << 32) | (dim1 << 16) | stream_id
    var c2 = draw_index >> 2
    var c3: UInt64 = 0
    var k0 = master_seed
    var k1 = scenario_id

    for r in range(10):
        if r > 0:
            k0 += PHILOX_W0
            k1 += PHILOX_W1
        var hi0 = _mul_hi64(PHILOX_M0, c0)
        var lo0 = PHILOX_M0 * c0
        var hi1 = _mul_hi64(PHILOX_M1, c2)
        var lo1 = PHILOX_M1 * c2
        var n0 = hi1 ^ c1 ^ k0
        var n1 = lo1
        var n2 = hi0 ^ c3 ^ k1
        var n3 = lo0
        c0 = n0
        c1 = n1
        c2 = n2
        c3 = n3

    var w = draw_index & 3
    if w == 0:
        return c0
    if w == 1:
        return c1
    if w == 2:
        return c2
    return c3


def rng_uniform(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    dim0: UInt64, dim1: UInt64, stream_id: UInt64, draw_index: UInt64
) -> Float64:
    """Uniform on [0, 1) — 53-bit mantissa, exactly representable. Consumes 1 draw."""
    var u = philox_word(
        master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index
    )
    return Float64(u >> 11) * TWO_POW_NEG_53


def rng_uniform_left_open(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    dim0: UInt64, dim1: UInt64, stream_id: UInt64, draw_index: UInt64
) -> Float64:
    """Uniform on (0, 1] — never zero, so log() is always defined. Consumes 1 draw."""
    var u = philox_word(
        master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index
    )
    return Float64((u >> 11) + 1) * TWO_POW_NEG_53


def rng_bernoulli(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    dim0: UInt64, dim1: UInt64, stream_id: UInt64, draw_index: UInt64, p: Float64
) -> Bool:
    """Bernoulli(p). Consumes 1 draw."""
    return rng_uniform(
        master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index
    ) < p


def rng_exponential(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    dim0: UInt64, dim1: UInt64, stream_id: UInt64, draw_index: UInt64, rate: Float64
) -> Float64:
    """Exponential(rate) via inverse CDF. Consumes 1 draw. rate <= 0 returns 0."""
    if rate <= 0.0:
        return 0.0
    var u = rng_uniform_left_open(
        master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index
    )
    return -log(u) / rate


def rng_normal(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    dim0: UInt64, dim1: UInt64, stream_id: UInt64, draw_index: UInt64
) -> Float64:
    """Standard normal via Box-Muller, cosine branch. Consumes 2 draws: draw_index, draw_index+1.

    Box-Muller rather than a ziggurat precisely because consumption is fixed and rejection-free.
    The sine companion is discarded rather than cached; caching would make consumption depend on
    call parity.
    """
    var u1 = rng_uniform_left_open(
        master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index
    )
    var u2 = rng_uniform(
        master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index + 1
    )
    return sqrt(-2.0 * log(u1)) * cos(TWO_PI * u2)


def rng_normal_scaled(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    dim0: UInt64, dim1: UInt64, stream_id: UInt64, draw_index: UInt64,
    mean: Float64, sigma: Float64
) -> Float64:
    """Normal(mean, sigma). Consumes 2 draws."""
    var z = rng_normal(
        master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index
    )
    return mean + sigma * z


# ── Deterministic zero-argument probes (shard requirement) ────────────────────


def rng_version() -> String:
    """The frozen generator contract identifier. Deterministic, zero-argument."""
    return String("philox4x64-10/v1")


def rng_global_sentinel() -> UInt64:
    """dim1 value used by global (non-per-car) processes. Deterministic, zero-argument."""
    return GLOBAL_SENTINEL


def rng_selftest() -> UInt64:
    """Fold 64 words from fixed coordinates into one value. Deterministic, zero-argument.

    Changing the generator, layout, or word selection changes this value — which is the point.
    """
    var acc: UInt64 = 0
    for i in range(64):
        var w = philox_word(1, 2, 3, 4, 5, UInt64(4), UInt64(i))
        acc = acc ^ (w + UInt64(i))
    return acc
