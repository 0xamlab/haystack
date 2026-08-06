"""
stochastic.mojo — Stochastic processes. Zero Python imports.

Replaces custom Python stochastic simulation code with pure Mojo
implementations of random walks, Brownian motion, geometric Brownian
motion, Poisson processes, Ornstein-Uhlenbeck, and more.

Public API:
  random_walk_1d            — 1D random walk (+1/-1)
  random_walk_2d            — 2D random walk
  brownian_motion           — Wiener process
  geometric_brownian_motion — GBM for asset prices
  poisson_process           — Event times from Poisson process
  ornstein_uhlenbeck        — Mean-reverting OU process
  birth_death_process       — Simple birth-death chain
  monte_carlo_pi            — Estimate π via Monte Carlo
  expected_hitting_time     — Expected steps to reach target
  first_passage_time        — Average first passage time
"""
from std.math import sqrt, exp, log, abs as fabs
from std.random import random_float64


# ── Box-Muller normal approximation ──────────────────────────────────────────


def _normal_random() -> Float64:
    """Generate a standard normal random variable using Box-Muller transform."""
    # Use Box-Muller: Z = sqrt(-2 ln U1) * cos(2π U2)
    # Since we don't have cos/sin easily, use the polar method
    var u1: Float64 = 0.0
    var u2: Float64 = 0.0
    var s: Float64 = 0.0
    # Polar rejection method
    while True:
        u1 = 2.0 * random_float64() - 1.0
        u2 = 2.0 * random_float64() - 1.0
        s = u1 * u1 + u2 * u2
        if s > 0.0 and s < 1.0:
            break
    var factor = sqrt(-2.0 * log(s) / s)
    return u1 * factor


# ── random_walk_1d ────────────────────────────────────────────────────────────


def random_walk_1d(n_steps: Int) -> List[Float64]:
    """1D random walk: +1 or -1 each step with equal probability.

    Returns list of length n_steps+1 (including start at 0).
    """
    var result = List[Float64]()
    result.append(0.0)
    var pos: Float64 = 0.0
    for _ in range(n_steps):
        if random_float64() < 0.5:
            pos += 1.0
        else:
            pos -= 1.0
        result.append(pos)
    return result^


# ── random_walk_2d ────────────────────────────────────────────────────────────


def random_walk_2d(n_steps: Int) -> List[List[Float64]]:
    """2D random walk: returns [[x0,y0], [x1,y1], ...].

    At each step, move in one of 4 cardinal directions with equal probability.
    Returns list of length n_steps+1.
    """
    var result = List[List[Float64]]()
    var x: Float64 = 0.0
    var y: Float64 = 0.0
    var start = List[Float64]()
    start.append(x)
    start.append(y)
    result.append(start^)

    for _ in range(n_steps):
        var r = random_float64()
        if r < 0.25:
            x += 1.0
        elif r < 0.5:
            x -= 1.0
        elif r < 0.75:
            y += 1.0
        else:
            y -= 1.0
        var pt = List[Float64]()
        pt.append(x)
        pt.append(y)
        result.append(pt^)

    return result^


# ── brownian_motion ───────────────────────────────────────────────────────────


def brownian_motion(n_steps: Int, dt: Float64 = 0.01) -> List[Float64]:
    """Wiener process: cumulative sum of N(0, sqrt(dt)).

    Returns list of length n_steps+1 starting at 0.
    """
    var result = List[Float64]()
    result.append(0.0)
    var pos: Float64 = 0.0
    var scale = sqrt(dt)
    for _ in range(n_steps):
        pos += _normal_random() * scale
        result.append(pos)
    return result^


# ── geometric_brownian_motion ─────────────────────────────────────────────────


def geometric_brownian_motion(
    s0: Float64,
    mu: Float64,
    sigma: Float64,
    dt: Float64,
    n_steps: Int,
) -> List[Float64]:
    """Geometric Brownian Motion: S(t+dt) = S(t) * exp((μ-σ²/2)dt + σ√dt·Z).

    Models stock prices. All values positive.
    Returns list of length n_steps+1 starting at s0.
    """
    var result = List[Float64]()
    result.append(s0)
    var s = s0
    var drift = (mu - 0.5 * sigma * sigma) * dt
    var vol = sigma * sqrt(dt)
    for _ in range(n_steps):
        var z = _normal_random()
        s = s * exp(drift + vol * z)
        result.append(s)
    return result^


# ── poisson_process ───────────────────────────────────────────────────────────


def poisson_process(rate: Float64, duration: Float64) -> List[Float64]:
    """Generate event times from a Poisson process.

    Events arrive at given rate (events per time unit).
    Returns sorted list of event times, all < duration.
    Uses inter-arrival times ~ Exp(rate).
    """
    var result = List[Float64]()
    if rate <= 0.0 or duration <= 0.0:
        return result^

    var t: Float64 = 0.0
    while True:
        # Exponential inter-arrival: -ln(U)/rate
        var u = random_float64()
        if u < 1e-15:
            u = 1e-15  # avoid log(0)
        var inter = -log(u) / rate
        t += inter
        if t >= duration:
            break
        result.append(t)

    return result^


# ── ornstein_uhlenbeck ────────────────────────────────────────────────────────


def ornstein_uhlenbeck(
    x0: Float64,
    theta: Float64,
    mu: Float64,
    sigma: Float64,
    dt: Float64,
    n_steps: Int,
) -> List[Float64]:
    """Ornstein-Uhlenbeck process: mean-reverting diffusion.

    dx = θ(μ - x)dt + σdW
    theta: speed of reversion, mu: long-run mean, sigma: volatility.
    Returns list of length n_steps+1 starting at x0.
    """
    var result = List[Float64]()
    result.append(x0)
    var x = x0
    var sqrt_dt = sqrt(dt)
    for _ in range(n_steps):
        var dw = _normal_random() * sqrt_dt
        x = x + theta * (mu - x) * dt + sigma * dw
        result.append(x)
    return result^


# ── birth_death_process ───────────────────────────────────────────────────────


def birth_death_process(
    birth_rate: Float64,
    death_rate: Float64,
    initial: Int,
    n_steps: Int,
) -> List[Int]:
    """Simple birth-death process.

    At each step, population increases by 1 with prob birth_rate/(birth_rate+death_rate)
    or decreases by 1 with prob death_rate/(birth_rate+death_rate).
    Population cannot go below 0.
    Returns list of length n_steps+1.
    """
    var result = List[Int]()
    var pop = initial
    if pop < 0:
        pop = 0
    result.append(pop)
    var total = birth_rate + death_rate
    if total <= 0.0:
        for _ in range(n_steps):
            result.append(pop)
        return result^

    var p_birth = birth_rate / total
    for _ in range(n_steps):
        var r = random_float64()
        if r < p_birth:
            pop += 1
        else:
            if pop > 0:
                pop -= 1
        result.append(pop)

    return result^


# ── monte_carlo_pi ────────────────────────────────────────────────────────────


def monte_carlo_pi(n_samples: Int) -> Float64:
    """Estimate π using random points in unit square.

    Count fraction of points falling inside quarter circle.
    π ≈ 4 * (points inside circle) / (total points).
    """
    if n_samples <= 0:
        return 0.0
    var inside = 0
    for _ in range(n_samples):
        var x = random_float64()
        var y = random_float64()
        if x * x + y * y <= 1.0:
            inside += 1
    return 4.0 * Float64(inside) / Float64(n_samples)


# ── expected_hitting_time ─────────────────────────────────────────────────────


def expected_hitting_time(p: Float64, target: Int) -> Float64:
    """Expected steps for biased random walk to reach target from 0.

    p: probability of +1 step, (1-p): probability of -1 step.
    target must be > 0.

    For unbiased walk (p=0.5), expected time = target^2.
    For biased walk, E[T] = target / (2p - 1) when p > 0.5.
    For p < 0.5 with positive target, expected time is infinite → return -1.
    """
    if target <= 0:
        return 0.0
    var t = Float64(target)
    if fabs(p - 0.5) < 1e-12:
        # Unbiased: E[T] = target^2
        return t * t
    elif p > 0.5:
        return t / (2.0 * p - 1.0)
    else:
        # p < 0.5, positive target: infinite expected time
        return -1.0


# ── first_passage_time ────────────────────────────────────────────────────────


def first_passage_time(n_simulations: Int, target: Float64) -> Float64:
    """Average first passage time for standard random walk to reach target.

    Simulates n_simulations walks, each starting at 0, stepping +1/-1
    with equal probability. Returns average number of steps to reach
    |position| >= |target|. Caps each walk at 100000 steps.
    """
    if n_simulations <= 0:
        return 0.0
    var abs_target = fabs(target)
    if abs_target < 1e-12:
        return 0.0

    var total_steps: Float64 = 0.0
    var max_steps = 100000
    for _ in range(n_simulations):
        var pos: Float64 = 0.0
        var steps = 0
        while steps < max_steps:
            if random_float64() < 0.5:
                pos += 1.0
            else:
                pos -= 1.0
            steps += 1
            if fabs(pos) >= abs_target:
                break
        total_steps += Float64(steps)

    return total_steps / Float64(n_simulations)
