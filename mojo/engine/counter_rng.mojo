"""counter_rng — Philox4x64-10 counter-based randomness.

Stateless, addressable randomness: every draw is a pure function of its coordinates, so the same
logical draw yields the same value regardless of what a trajectory did beforehand. That is what makes
valid common random numbers possible when compared alternatives consume different numbers of draws.

rng_version = "philox4x64-10/v1"

Counter/key layout (frozen — see docs/timing/FROZEN_SPECS.md):
    c0 = replication_id
    c1 = (lap_id << 32) | (car_id << 16) | process_id
    c2 = draw_index >> 2          word = draw_index & 3
    c3 = 0                        reserved
    k0 = master_seed
    k1 = scenario_id

Every distribution consumes a FIXED number of draws. Variable-consumption sampling (ziggurat,
rejection loops) would make draw_index depend on trajectory and reintroduce the coupling this design
removes.

General-purpose infrastructure: motorsport is the first consumer, not the only possible one.
"""

from math import cos, log, sqrt

# ── Philox4x64 constants ──────────────────────────────────────────────────────

alias PHILOX_M0: UInt64 = 0xD2E7470EE14C6C93
alias PHILOX_M1: UInt64 = 0xCA5A826395121157
alias PHILOX_W0: UInt64 = 0x9E3779B97F4A7C15
alias PHILOX_W1: UInt64 = 0xBB67AE8584CAA73B

alias GLOBAL_SENTINEL: UInt64 = 0xFFFF

alias PROCESS_SAFETY_CAR: UInt64 = 1
alias PROCESS_VSC: UInt64 = 2
alias PROCESS_WEATHER: UInt64 = 3
alias PROCESS_LAP_NOISE: UInt64 = 4
alias PROCESS_PIT_SERVICE: UInt64 = 5
alias PROCESS_RETIREMENT: UInt64 = 6
alias PROCESS_OVERTAKE: UInt64 = 7
# Per-car per-race form: drawn ONCE per replication, not per lap. Distinct from lap noise because
# per-lap noise averages away over a race distance while form does not.
alias PROCESS_CAR_FORM: UInt64 = 8
# Parameter search. Not a race process -- it addresses draws by (generation, individual, gene) so a
# calibration run replays bit-exactly, which is what makes a fitted theta reportable as evidence.
# The joint bootstrap over replication ROWS. It was a hardcoded literal 9 inside option_board and
# absent from this registry, so registering PROCESS_SEARCH at 9 collided with it. Named at its existing
# value so no board interval changes; the search moved to 10 instead, which is additive.
alias PROCESS_BOOTSTRAP: UInt64 = 9
alias PROCESS_SEARCH: UInt64 = 10

alias TWO_POW_NEG_53: Float64 = 1.1102230246251565e-16
alias TWO_PI: Float64 = 6.283185307179586


fn _mul_hi64(a: UInt64, b: UInt64) -> UInt64:
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


fn philox_word(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, draw_index: UInt64
) -> UInt64:
    """One 64-bit Philox4x64-10 output word for the given draw coordinates."""
    var c0 = replication_id
    var c1 = (lap_id << 32) | (car_id << 16) | process_id
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


struct PhiloxBlock(Copyable, Movable):
    """One Philox invocation's four output words, stack-allocated.

    Exists because a 10-round Philox block is the same work whether you read one word or four. Reading
    one word per call meant rng_normal -- which needs two uniforms -- ran the full block TWICE for
    draw_index 0 and 1, which map to the identical counter. That redundancy dominated the simulation.
    """

    var w0: UInt64
    var w1: UInt64
    var w2: UInt64
    var w3: UInt64

    fn __init__(out self, w0: UInt64, w1: UInt64, w2: UInt64, w3: UInt64):
        self.w0 = w0
        self.w1 = w1
        self.w2 = w2
        self.w3 = w3

    fn word(self, i: UInt64) -> UInt64:
        if i == 0:
            return self.w0
        if i == 1:
            return self.w1
        if i == 2:
            return self.w2
        return self.w3


fn philox_block(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, block_index: UInt64
) -> PhiloxBlock:
    """All four output words for one counter block. block_index == draw_index >> 2."""
    var c0 = replication_id
    var c1 = (lap_id << 32) | (car_id << 16) | process_id
    var c2 = block_index
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
    return PhiloxBlock(c0, c1, c2, c3)


fn rng_uniform(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, draw_index: UInt64
) -> Float64:
    """Uniform on [0, 1) — 53-bit mantissa, exactly representable. Consumes 1 draw."""
    var u = philox_word(
        master_seed, scenario_id, replication_id, lap_id, car_id, process_id, draw_index
    )
    return Float64(u >> 11) * TWO_POW_NEG_53


fn rng_uniform_left_open(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, draw_index: UInt64
) -> Float64:
    """Uniform on (0, 1] — never zero, so log() is always defined. Consumes 1 draw."""
    var u = philox_word(
        master_seed, scenario_id, replication_id, lap_id, car_id, process_id, draw_index
    )
    return Float64((u >> 11) + 1) * TWO_POW_NEG_53


fn rng_bernoulli(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, draw_index: UInt64, p: Float64
) -> Bool:
    """Bernoulli(p). Consumes 1 draw."""
    return rng_uniform(
        master_seed, scenario_id, replication_id, lap_id, car_id, process_id, draw_index
    ) < p


fn rng_exponential(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, draw_index: UInt64, rate: Float64
) -> Float64:
    """Exponential(rate) via inverse CDF. Consumes 1 draw. rate <= 0 returns 0."""
    if rate <= 0.0:
        return 0.0
    var u = rng_uniform_left_open(
        master_seed, scenario_id, replication_id, lap_id, car_id, process_id, draw_index
    )
    return -log(u) / rate


fn rng_normal(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, draw_index: UInt64
) -> Float64:
    """Standard normal via Box-Muller, cosine branch. Consumes 2 draws: draw_index, draw_index+1.

    Box-Muller rather than a ziggurat precisely because consumption is fixed and rejection-free.
    The sine companion is discarded rather than cached; caching would make consumption depend on
    call parity.
    """
    var i0 = draw_index & 3
    var b = philox_block(
        master_seed, scenario_id, replication_id, lap_id, car_id, process_id, draw_index >> 2
    )
    var raw1 = b.word(i0)
    var raw2: UInt64
    if i0 == 3:
        # the pair straddles a block boundary; only then is a second invocation needed
        var b2 = philox_block(
            master_seed, scenario_id, replication_id, lap_id, car_id, process_id,
            (draw_index + 1) >> 2,
        )
        raw2 = b2.word(0)
    else:
        raw2 = b.word(i0 + 1)
    var u1 = Float64((raw1 >> 11) + 1) * TWO_POW_NEG_53
    var u2 = Float64(raw2 >> 11) * TWO_POW_NEG_53
    return sqrt(-2.0 * log(u1)) * cos(TWO_PI * u2)


fn rng_normal_scaled(
    master_seed: UInt64, scenario_id: UInt64, replication_id: UInt64,
    lap_id: UInt64, car_id: UInt64, process_id: UInt64, draw_index: UInt64,
    mean: Float64, sigma: Float64
) -> Float64:
    """Normal(mean, sigma). Consumes 2 draws."""
    var z = rng_normal(
        master_seed, scenario_id, replication_id, lap_id, car_id, process_id, draw_index
    )
    return mean + sigma * z


# ── Deterministic zero-argument probes (shard requirement) ────────────────────


fn rng_version() -> String:
    """The frozen generator contract identifier. Deterministic, zero-argument."""
    return String("philox4x64-10/v1")


fn rng_global_sentinel() -> UInt64:
    """car_id value used by global (non-per-car) processes. Deterministic, zero-argument."""
    return GLOBAL_SENTINEL


fn rng_selftest() -> UInt64:
    """Fold 64 words from fixed coordinates into one value. Deterministic, zero-argument.

    Changing the generator, layout, or word selection changes this value — which is the point.
    """
    var acc: UInt64 = 0
    for i in range(64):
        var w = philox_word(1, 2, 3, 4, 5, PROCESS_LAP_NOISE, UInt64(i))
        acc = acc ^ (w + UInt64(i))
    return acc
