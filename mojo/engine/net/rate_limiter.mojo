"""
rate_limiter.mojo — Token bucket rate limiter. Zero Python imports.

Counter-based token bucket algorithm for request throttling.
Since Mojo doesn't have a real-time clock, this is a pure counter-based
implementation where tokens are consumed on allow() calls.
The caller can refill tokens manually via add_tokens() or reset().

Public API:
  struct TokenBucket(Copyable, Movable)
    def __init__(out self, rate: Float64, burst: Int)
    def allow(mut self) -> Bool
    def allow_n(mut self, n: Int) -> Bool
    def tokens_available(self) -> Int
    def add_tokens(mut self, n: Int)
    def reset(mut self)
"""


# ── TokenBucket ──────────────────────────────────────────────────────────────


@fieldwise_init
struct TokenBucket(Copyable, Movable):
    """Token bucket rate limiter.

    A counter-based rate limiter that starts with `burst` tokens and
    consumes them on each allow() call. Without a real-time clock,
    tokens must be refilled manually via add_tokens() or reset().

    Fields:
        _rate: Tokens per second (informational; used for reset sizing).
        _burst: Maximum number of tokens (bucket capacity).
        _tokens: Current available tokens.
        _total_allowed: Count of allowed requests.
        _total_denied: Count of denied requests.
    """

    var _rate: Float64
    var _burst: Int
    var _tokens: Int
    var _total_allowed: Int
    var _total_denied: Int

    def __init__(out self, rate: Float64, burst: Int):
        """Create a new token bucket rate limiter.

        Args:
            rate: Token refill rate (tokens per second). Stored for reference;
                  actual refill is manual in this counter-based implementation.
            burst: Maximum tokens (bucket capacity). Also the initial token count.
        """
        self._rate = rate
        var b = burst
        if b < 1:
            b = 1
        self._burst = b
        self._tokens = b
        self._total_allowed = 0
        self._total_denied = 0

    def allow(mut self) -> Bool:
        """Try to consume 1 token. Returns True if allowed.

        Returns:
            True if a token was consumed, False if no tokens available.
        """
        return self.allow_n(1)

    def allow_n(mut self, n: Int) -> Bool:
        """Try to consume n tokens. Returns True if allowed.

        This is an all-or-nothing operation: either all n tokens are consumed,
        or none are.

        Args:
            n: Number of tokens to consume.

        Returns:
            True if n tokens were consumed, False if insufficient tokens.
        """
        if n <= 0:
            return True
        if self._tokens >= n:
            self._tokens -= n
            self._total_allowed += 1
            return True
        self._total_denied += 1
        return False

    def tokens_available(self) -> Int:
        """Return the number of tokens currently available.

        Returns:
            Current token count.
        """
        return self._tokens

    def add_tokens(mut self, n: Int):
        """Manually add tokens to the bucket, up to burst capacity.

        Args:
            n: Number of tokens to add.
        """
        self._tokens += n
        if self._tokens > self._burst:
            self._tokens = self._burst

    def reset(mut self):
        """Reset the bucket to full capacity and clear counters."""
        self._tokens = self._burst
        self._total_allowed = 0
        self._total_denied = 0
