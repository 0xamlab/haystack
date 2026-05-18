"""
token_bucket.mojo — Advanced rate limiting. Zero Python imports.

Replaces ratelimit advanced patterns with pure Mojo implementations
for token bucket, leaky bucket, and sliding window rate limiters.

Public API:
  TokenBucket   — Token bucket struct
  tb_create     — Create token bucket
  tb_consume    — Try to consume tokens
  tb_refill     — Refill tokens based on elapsed time
  tb_available  — Current available tokens

  LeakyBucket   — Leaky bucket struct
  lb_create     — Create leaky bucket
  lb_add        — Add to bucket (returns False if overflow)
  lb_leak       — Leak tokens based on elapsed time
  lb_level      — Current fill level

  SlidingWindow — Sliding window struct
  sw_create     — Create sliding window
  sw_allow      — Check if request is allowed
  sw_count      — Count requests in current window
"""


# ── TokenBucket ───────────────────────────────────────────────────────────────


struct TokenBucket:
    """Token bucket rate limiter.

    Tokens are added at a fixed refill_rate per time unit.
    Requests consume tokens; if insufficient tokens, request is denied.
    """

    var capacity: Float64
    var tokens: Float64
    var refill_rate: Float64
    var last_refill: Float64

    fn __init__(out self, capacity: Float64, tokens: Float64,
                refill_rate: Float64, last_refill: Float64):
        self.capacity = capacity
        self.tokens = tokens
        self.refill_rate = refill_rate
        self.last_refill = last_refill


fn tb_create(capacity: Float64, refill_rate: Float64) -> TokenBucket:
    """Create token bucket starting full at time 0."""
    return TokenBucket(capacity, capacity, refill_rate, 0.0)


fn tb_refill(mut bucket: TokenBucket, current_time: Float64):
    """Refill tokens based on elapsed time since last refill."""
    var elapsed = current_time - bucket.last_refill
    if elapsed > 0.0:
        bucket.tokens += elapsed * bucket.refill_rate
        if bucket.tokens > bucket.capacity:
            bucket.tokens = bucket.capacity
        bucket.last_refill = current_time


fn tb_consume(
    mut bucket: TokenBucket, tokens: Float64, current_time: Float64
) -> Bool:
    """Try to consume tokens. Returns True if allowed."""
    tb_refill(bucket, current_time)
    if bucket.tokens >= tokens:
        bucket.tokens -= tokens
        return True
    return False


fn tb_available(bucket: TokenBucket) -> Float64:
    """Current available tokens (without refill)."""
    return bucket.tokens


# ── LeakyBucket ───────────────────────────────────────────────────────────────


struct LeakyBucket:
    """Leaky bucket rate limiter.

    Requests add to the bucket; it leaks at a fixed rate.
    If the bucket overflows, the request is denied.
    """

    var capacity: Float64
    var current: Float64
    var leak_rate: Float64
    var last_leak: Float64

    fn __init__(out self, capacity: Float64, current: Float64,
                leak_rate: Float64, last_leak: Float64):
        self.capacity = capacity
        self.current = current
        self.leak_rate = leak_rate
        self.last_leak = last_leak


fn lb_create(capacity: Float64, leak_rate: Float64) -> LeakyBucket:
    """Create leaky bucket starting empty at time 0."""
    return LeakyBucket(capacity, 0.0, leak_rate, 0.0)


fn lb_leak(mut bucket: LeakyBucket, current_time: Float64):
    """Leak tokens based on elapsed time."""
    var elapsed = current_time - bucket.last_leak
    if elapsed > 0.0:
        var leaked = elapsed * bucket.leak_rate
        bucket.current -= leaked
        if bucket.current < 0.0:
            bucket.current = 0.0
        bucket.last_leak = current_time


fn lb_add(
    mut bucket: LeakyBucket, amount: Float64, current_time: Float64
) -> Bool:
    """Add to bucket. Returns False if would overflow."""
    lb_leak(bucket, current_time)
    if bucket.current + amount > bucket.capacity:
        return False
    bucket.current += amount
    return True


fn lb_level(bucket: LeakyBucket) -> Float64:
    """Current fill level (without leaking)."""
    return bucket.current


# ── SlidingWindow ─────────────────────────────────────────────────────────────


struct SlidingWindow:
    """Sliding window rate limiter.

    Tracks timestamps of requests within a time window.
    Denies requests when max_requests is exceeded in the window.
    """

    var timestamps: List[Float64]
    var window_size: Float64
    var max_requests: Int

    fn __init__(out self, window_size: Float64, max_requests: Int):
        self.timestamps = List[Float64]()
        self.window_size = window_size
        self.max_requests = max_requests


fn sw_create(window_size: Float64, max_requests: Int) -> SlidingWindow:
    """Create sliding window limiter."""
    return SlidingWindow(window_size, max_requests)


fn _sw_prune(mut window: SlidingWindow, current_time: Float64):
    """Remove timestamps outside the window."""
    var cutoff = current_time - window.window_size
    var new_ts = List[Float64]()
    for i in range(len(window.timestamps)):
        if window.timestamps[i] > cutoff:
            new_ts.append(window.timestamps[i])
    window.timestamps = new_ts^


fn sw_allow(mut window: SlidingWindow, current_time: Float64) -> Bool:
    """Check if request is allowed; if so, record it."""
    _sw_prune(window, current_time)
    if len(window.timestamps) < window.max_requests:
        window.timestamps.append(current_time)
        return True
    return False


fn sw_count(window: SlidingWindow, current_time: Float64) -> Int:
    """Count requests in current window."""
    var cutoff = current_time - window.window_size
    var count = 0
    for i in range(len(window.timestamps)):
        if window.timestamps[i] > cutoff:
            count += 1
    return count
