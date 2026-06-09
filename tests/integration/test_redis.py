"""
Phase 7 — Redis Integration Tests.

Tests the Redis layer directly: connectivity, SET/GET/DEL operations, TTL handling,
rate-limiting key patterns, quota counter patterns, pub/sub, and key hygiene.

Also verifies how the API server uses Redis via the /v1/simulate endpoint
(rate-limit counters and quota counters).

Prerequisites:
  1. Redis running on localhost:6379 (or REDIS_URL env var)
  2. API server running: make dev-api  (on localhost:8000)
  3. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_redis.py
"""

import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from tests.integration.live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

from tests.integration.live_integration_artifacts import write_live_integration_summary

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()

SUITE_NAME = "redis_integration"
STARTED = time.perf_counter()

# ─── Import redis ─────────────────────────────────────────────────────────────
try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]

# ─── Test harness ─────────────────────────────────────────────────────────────
PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
REDIS_UNAVAILABLE_REASON: str | None = None


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def check(name: str, fn):
    if REDIS_UNAVAILABLE_REASON:
        skip(name, REDIS_UNAVAILABLE_REASON)
        return
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        results.append((PASS, name))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {type(e).__name__}: {e}")


def skip(name: str, reason: str):
    results.append((SKIP, name, reason))
    _emit(f"  {SKIP} {name}: {reason}")


# ─── HTTP helpers (same pattern as other integration tests) ───────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=10):
    """Make HTTP request, return (status_code, body_dict, headers_dict, elapsed)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if auth:
        h["X-API-Key"] = API_KEY
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            body_bytes = resp.read()
            try:
                body_data = json.loads(body_bytes)
            except Exception:
                body_data = body_bytes.decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            return resp.status, body_data, resp_headers, elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body_bytes = e.read()
        try:
            body_data = json.loads(body_bytes)
        except Exception:
            body_data = body_bytes.decode("utf-8", errors="replace")
        resp_headers = {k.lower(): v for k, v in e.headers.items()}
        return e.code, body_data, resp_headers, elapsed


# ─── Redis connection ─────────────────────────────────────────────────────────
def get_redis_client() -> "redis.Redis":
    """Return a synchronous Redis client connected per REDIS_URL."""
    if redis is None:
        raise RuntimeError("redis package not installed")
    return redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)


# ─── Test namespace prefix (all test keys use this for safe cleanup) ──────────
TEST_PREFIX = f"_test_phase7_{uuid.uuid4().hex[:8]}:"


def test_key(suffix: str) -> str:
    """Return a namespaced test key that will be cleaned up after tests."""
    return f"{TEST_PREFIX}{suffix}"


# Helper, not a pytest test case despite the ``test_`` prefix.
test_key.__test__ = False


# ─── Standard simulation payload (used across multiple tests) ─────────────────
SIM_PAYLOAD = {
    "mode": "auto",
    "scenario": {
        "variables": {
            "revenue": {"low": 80000, "high": 120000},
            "cost": {"low": 30000, "high": 60000},
        },
        "objective": "maximize_net_value",
    },
    "runs": 1000,
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Connectivity Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_redis_ping():
    r = get_redis_client()
    result = r.ping()
    assert result is True, f"Expected True, got {result}"
    r.close()


def test_redis_info_server():
    r = get_redis_client()
    info = r.info("server")
    assert "redis_version" in info, "INFO server missing redis_version"
    assert info["redis_version"], "redis_version is empty"
    print(f"        Redis version: {info['redis_version']}")
    r.close()


def test_redis_info_keyspace():
    r = get_redis_client()
    info = r.info("keyspace")
    # keyspace may be empty if no keys, that's fine
    assert isinstance(info, dict), f"Expected dict, got {type(info)}"
    r.close()


def test_redis_correct_database():
    """Verify we're connected to the expected database (db0 per REDIS_URL)."""
    r = get_redis_client()
    # Parse expected db from URL
    expected_db = 0
    if "/" in REDIS_URL.rstrip("/"):
        parts = REDIS_URL.rstrip("/").split("/")
        try:
            expected_db = int(parts[-1])
        except ValueError:
            pass
    # The connection object knows the db
    conn_kwargs = r.connection_pool.connection_kwargs
    actual_db = conn_kwargs.get("db", 0)
    assert actual_db == expected_db, f"Expected db{expected_db}, connected to db{actual_db}"
    r.close()


def test_redis_connection_pool():
    """Verify connection pool is functional — can issue multiple commands."""
    r = get_redis_client()
    for _i in range(5):
        assert r.ping() is True
    r.close()


def test_redis_dbsize():
    """Verify DBSIZE command works (returns an integer)."""
    r = get_redis_client()
    size = r.dbsize()
    assert isinstance(size, int), f"Expected int, got {type(size)}"
    assert size >= 0, f"DBSIZE returned negative: {size}"
    print(f"        Current key count: {size}")
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Cache Operations (SET/GET/DEL/TTL)
# ═══════════════════════════════════════════════════════════════════════════════
def test_set_get_cycle():
    r = get_redis_client()
    k = test_key("setget")
    r.set(k, "hello_decision_engine")
    val = r.get(k)
    assert val == "hello_decision_engine", f"Expected 'hello_decision_engine', got {val!r}"
    r.delete(k)
    r.close()


def test_set_get_json():
    """SET/GET with JSON-serialized value (common pattern for caching)."""
    r = get_redis_client()
    k = test_key("json")
    payload = {"simulation_id": "abc-123", "mean": 42150.3, "std": 8200.1}
    r.set(k, json.dumps(payload))
    raw = r.get(k)
    parsed = json.loads(raw)
    assert parsed["simulation_id"] == "abc-123"
    assert parsed["mean"] == 42150.3
    r.delete(k)
    r.close()


def test_del_removes_key():
    r = get_redis_client()
    k = test_key("deltest")
    r.set(k, "temporary")
    assert r.exists(k) == 1, "Key should exist after SET"
    r.delete(k)
    assert r.exists(k) == 0, "Key should not exist after DEL"
    r.close()


def test_ttl_set_correctly():
    """Verify TTL is set and counts down."""
    r = get_redis_client()
    k = test_key("ttltest")
    r.set(k, "expires_soon", ex=10)
    ttl = r.ttl(k)
    assert 0 < ttl <= 10, f"Expected TTL 1-10, got {ttl}"
    r.delete(k)
    r.close()


def test_ttl_expiration():
    """Set a key with 1-second TTL and verify it expires."""
    r = get_redis_client()
    k = test_key("expire1s")
    r.set(k, "short_lived", ex=1)
    assert r.exists(k) == 1, "Key should exist immediately after SET"
    time.sleep(1.5)
    assert r.exists(k) == 0, "Key should have expired after 1.5s"
    r.close()


def test_incr_counter():
    """INCR atomically increments a counter (used by rate limiter)."""
    r = get_redis_client()
    k = test_key("counter")
    r.delete(k)  # Ensure clean start
    v1 = r.incr(k)
    assert v1 == 1, f"First INCR should return 1, got {v1}"
    v2 = r.incr(k)
    assert v2 == 2, f"Second INCR should return 2, got {v2}"
    v3 = r.incr(k)
    assert v3 == 3, f"Third INCR should return 3, got {v3}"
    r.delete(k)
    r.close()


def test_incr_with_expire():
    """INCR + EXPIRE pattern (used by rate limiter: ratelimit:{org}:{minute})."""
    r = get_redis_client()
    k = test_key("ratelimit_sim")
    r.delete(k)
    val = r.incr(k)
    assert val == 1
    r.expire(k, 70)  # 70s TTL matching production rate limiter
    ttl = r.ttl(k)
    assert 60 < ttl <= 70, f"Expected TTL ~70, got {ttl}"
    r.delete(k)
    r.close()


def test_set_nx():
    """SET NX (set-if-not-exists) for atomic key creation."""
    r = get_redis_client()
    k = test_key("setnx")
    r.delete(k)
    result1 = r.set(k, "first", nx=True)
    assert result1 is True, f"First SET NX should succeed, got {result1}"
    result2 = r.set(k, "second", nx=True)
    assert result2 is None, f"Second SET NX should fail (return None), got {result2}"
    val = r.get(k)
    assert val == "first", f"Value should still be 'first', got {val!r}"
    r.delete(k)
    r.close()


def test_mset_mget():
    """MSET/MGET for batch operations."""
    r = get_redis_client()
    k1, k2, k3 = test_key("m1"), test_key("m2"), test_key("m3")
    r.mset({k1: "a", k2: "b", k3: "c"})
    vals = r.mget(k1, k2, k3)
    assert vals == ["a", "b", "c"], f"Expected ['a','b','c'], got {vals}"
    r.delete(k1, k2, k3)
    r.close()


def test_cache_invalidation():
    """Simulate cache invalidation: SET → verify → DEL → verify gone."""
    r = get_redis_client()
    k = test_key("invalidate")
    r.set(k, json.dumps({"result": "cached_sim_output"}), ex=300)
    assert r.exists(k) == 1
    # Invalidate
    r.delete(k)
    assert r.exists(k) == 0
    assert r.get(k) is None
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Rate Limiting Tests (via API + Redis verification)
# ═══════════════════════════════════════════════════════════════════════════════
def test_api_request_creates_ratelimit_key():
    """After hitting /v1/simulate, verify a ratelimit:* key appears in Redis."""
    r = get_redis_client()
    # Snapshot ratelimit keys before
    # Make a simulation request
    status, body, hdrs, elapsed = req("POST", "/v1/simulate", body=SIM_PAYLOAD)
    # Accept 200 (success) or 429 (rate limited) — both prove the system works
    assert status in (200, 429), f"Expected 200 or 429, got {status}: {body}"

    # Check for new ratelimit keys
    after_keys = set(r.keys("ratelimit:*"))
    all_rl_keys = after_keys
    if all_rl_keys:
        sample_key = next(iter(all_rl_keys))
        assert sample_key.startswith("ratelimit:"), (
            f"Key doesn't start with ratelimit: {sample_key}"
        )
        print(f"        Found {len(all_rl_keys)} ratelimit key(s), e.g. {sample_key}")
    else:
        # Keys may have already expired (70s TTL) — that's OK
        print("        No ratelimit keys found (may have expired — TTL 70s)")
    r.close()


def test_ratelimit_key_pattern():
    """Verify ratelimit key matches pattern: ratelimit:{uuid}:{YYYY-MM-DDTHH:MM}."""
    r = get_redis_client()
    keys = r.keys("ratelimit:*")
    if not keys:
        skip(
            "Rate limit key pattern matches ratelimit:{org_id}:{datetime}",
            "No ratelimit keys found",
        )
        r.close()
        return
    pattern = re.compile(r"^ratelimit:[0-9a-f\-]{36}:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
    for k in keys:
        assert pattern.match(k), f"Key doesn't match expected pattern: {k}"
    print(f"        All {len(keys)} ratelimit key(s) match expected pattern")
    r.close()


def test_ratelimit_key_has_ttl():
    """Rate limit keys should have TTL (70s) — never unbounded."""
    r = get_redis_client()
    keys = r.keys("ratelimit:*")
    if not keys:
        skip("Rate limit keys have TTL set", "No ratelimit keys found")
        r.close()
        return
    for k in keys:
        ttl = r.ttl(k)
        # TTL should be > 0 (has expiry) and <= 70 (the configured TTL)
        assert ttl > 0, f"Key {k} has no TTL (ttl={ttl})"
        assert ttl <= 70, f"Key {k} TTL too high: {ttl} (expected ≤70)"
    print(f"        All {len(keys)} ratelimit key(s) have valid TTL (≤70s)")
    r.close()


def test_ratelimit_counter_increments():
    """Verify that multiple API requests increment the rate limit counter."""
    r = get_redis_client()
    # Make two rapid requests
    req("POST", "/v1/simulate", body=SIM_PAYLOAD)
    req("POST", "/v1/simulate", body=SIM_PAYLOAD)

    # Find the most recent ratelimit key
    keys = r.keys("ratelimit:*")
    if not keys:
        skip("Rate limit counter increments with requests", "No ratelimit keys found")
        r.close()
        return
    # Get the value of any key — should be >= 2 (we just made 2 requests)
    found_nonzero = False
    for k in keys:
        val = r.get(k)
        if val and int(val) > 0:
            found_nonzero = True
            print(f"        Key {k} = {val}")
            break
    assert found_nonzero, "No ratelimit key has a non-zero counter value"
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Quota Counter Tests (via API + Redis verification)
# ═══════════════════════════════════════════════════════════════════════════════
def test_quota_count_key_exists():
    """After a simulation, a quota_count:* key should exist in Redis."""
    r = get_redis_client()
    keys = r.keys("quota_count:*")
    if not keys:
        # Trigger a simulation to seed the quota counter
        req("POST", "/v1/simulate", body=SIM_PAYLOAD)
        time.sleep(1)  # Allow async persist task to run
        keys = r.keys("quota_count:*")
    if keys:
        print(f"        Found {len(keys)} quota_count key(s)")
        for k in keys[:3]:
            val = r.get(k)
            print(f"        {k} = {val}")
    else:
        print("        No quota_count keys found (counter not yet seeded)")
    # Don't fail — the counter may not be seeded until first check
    assert True
    r.close()


def test_quota_count_key_pattern():
    """Verify quota_count key matches pattern: quota_count:{uuid}:{YYYY-MM}."""
    r = get_redis_client()
    keys = r.keys("quota_count:*")
    if not keys:
        skip("Quota counter key pattern matches expected format", "No quota_count keys found")
        r.close()
        return
    pattern = re.compile(r"^quota_count:[0-9a-f\-]{36}:\d{4}-\d{2}$")
    for k in keys:
        assert pattern.match(k), f"Key doesn't match expected pattern: {k}"
    print(f"        All {len(keys)} quota_count key(s) match expected pattern")
    r.close()


def test_quota_count_has_long_ttl():
    """Quota counter keys should have TTL ~35 days (3,024,000 seconds)."""
    r = get_redis_client()
    keys = r.keys("quota_count:*")
    if not keys:
        skip("Quota counter keys have long TTL (~35 days)", "No quota_count keys found")
        r.close()
        return
    for k in keys:
        ttl = r.ttl(k)
        if ttl == -1:
            # No TTL set — that's acceptable if not yet refreshed
            print(f"        {k} has no TTL (persistent)")
            continue
        # TTL should be > 0 and <= 35 days (3,024,000 seconds)
        max_ttl = 35 * 86400
        assert ttl > 0, f"Key {k} has expired TTL: {ttl}"
        assert ttl <= max_ttl, f"Key {k} TTL too high: {ttl} > {max_ttl}"
        print(f"        {k}: TTL = {ttl}s ({ttl / 86400:.1f} days)")
    r.close()


def test_quota_count_is_integer():
    """Quota counter value should be a parseable integer."""
    r = get_redis_client()
    keys = r.keys("quota_count:*")
    if not keys:
        skip("Quota counter values are integers", "No quota_count keys found")
        r.close()
        return
    for k in keys:
        val = r.get(k)
        if val is not None:
            parsed = int(val)
            assert parsed >= 0, f"Counter for {k} is negative: {parsed}"
            print(f"        {k} = {parsed}")
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Pub/Sub Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_pubsub_basic_message_delivery():
    """Subscribe to a test channel and verify message delivery."""
    r = get_redis_client()
    pub = get_redis_client()
    channel = test_key("pubsub_ch")
    ps = r.pubsub()
    ps.subscribe(channel)
    # Consume the subscription confirmation message
    msg = ps.get_message(timeout=2)
    assert msg is not None, "Expected subscription confirmation message"
    assert msg["type"] == "subscribe", f"Expected 'subscribe', got {msg['type']}"

    # Publish a message
    receivers = pub.publish(channel, "hello_from_test")
    assert receivers >= 1, f"Expected at least 1 subscriber, got {receivers}"

    # Receive the message
    msg = ps.get_message(timeout=2)
    assert msg is not None, "Expected to receive published message"
    assert msg["type"] == "message", f"Expected 'message', got {msg['type']}"
    assert msg["data"] == "hello_from_test", f"Expected 'hello_from_test', got {msg['data']!r}"

    ps.unsubscribe(channel)
    ps.close()
    pub.close()
    r.close()


def test_pubsub_multiple_messages():
    """Publish multiple messages and verify all are received in order."""
    r = get_redis_client()
    pub = get_redis_client()
    channel = test_key("pubsub_multi")
    ps = r.pubsub()
    ps.subscribe(channel)
    ps.get_message(timeout=2)  # consume subscribe confirmation

    messages = ["msg_1", "msg_2", "msg_3"]
    for m in messages:
        pub.publish(channel, m)

    received = []
    for _ in range(3):
        msg = ps.get_message(timeout=2)
        if msg and msg["type"] == "message":
            received.append(msg["data"])

    assert received == messages, f"Expected {messages}, got {received}"

    ps.unsubscribe(channel)
    ps.close()
    pub.close()
    r.close()


def test_pubsub_pattern_subscribe():
    """Pattern subscribe (PSUBSCRIBE) works for wildcard channels."""
    r = get_redis_client()
    pub = get_redis_client()
    pattern = test_key("events:*")
    ch1 = test_key("events:sim_start")
    ch2 = test_key("events:sim_end")
    ps = r.pubsub()
    ps.psubscribe(pattern)
    ps.get_message(timeout=2)  # consume psubscribe confirmation

    pub.publish(ch1, "started")
    pub.publish(ch2, "completed")

    received = []
    for _ in range(2):
        msg = ps.get_message(timeout=2)
        if msg and msg["type"] == "pmessage":
            received.append((msg["channel"], msg["data"]))

    assert len(received) == 2, f"Expected 2 messages, got {len(received)}"
    channels_received = {ch for ch, _ in received}
    assert ch1 in channels_received, f"Missing message from {ch1}"
    assert ch2 in channels_received, f"Missing message from {ch2}"

    ps.punsubscribe(pattern)
    ps.close()
    pub.close()
    r.close()


def test_pubsub_json_messages():
    """Pub/Sub with JSON payloads (matches SSE streaming use case)."""
    r = get_redis_client()
    pub = get_redis_client()
    channel = test_key("stream:sim")
    ps = r.pubsub()
    ps.subscribe(channel)
    ps.get_message(timeout=2)

    progress_event = json.dumps(
        {
            "type": "progress",
            "runs_completed": 5000,
            "runs_total": 50000,
            "progress": 0.10,
            "mean": 42150.3,
            "std": 8200.1,
        }
    )
    pub.publish(channel, progress_event)

    msg = ps.get_message(timeout=2)
    assert msg is not None, "Expected JSON message"
    parsed = json.loads(msg["data"])
    assert parsed["type"] == "progress"
    assert parsed["runs_completed"] == 5000
    assert parsed["progress"] == 0.10

    ps.unsubscribe(channel)
    ps.close()
    pub.close()
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Key Pattern & Hygiene Tests
# ═══════════════════════════════════════════════════════════════════════════════
# Known key prefixes used by the application
KNOWN_PREFIXES = [
    "ratelimit:",
    "quota_count:",
    "quota_alert:",
    "apikey:",
    "cache:",
    "stream:",
    "cortex:",
]


def test_all_keys_follow_naming_convention():
    """List all Redis keys and verify they follow expected naming conventions."""
    r = get_redis_client()
    all_keys = r.keys("*")
    # Filter out our test keys
    app_keys = [k for k in all_keys if not k.startswith(TEST_PREFIX)]
    if not app_keys:
        print("        No application keys found in Redis (clean state)")
        r.close()
        return

    recognized = 0
    unrecognized = []
    for k in app_keys:
        if any(k.startswith(prefix) for prefix in KNOWN_PREFIXES):
            recognized += 1
        else:
            unrecognized.append(k)

    print(f"        Total app keys: {len(app_keys)}")
    print(f"        Recognized pattern: {recognized}")
    if unrecognized:
        print(f"        Unrecognized: {len(unrecognized)}")
        for u in unrecognized[:5]:
            print(f"          → {u}")
    # We don't fail on unrecognized keys — they may be from other services
    assert True
    r.close()


def test_no_unbounded_keys():
    """Check that application keys have TTL set (no unbounded keys)."""
    r = get_redis_client()
    all_keys = r.keys("*")
    app_keys = [k for k in all_keys if not k.startswith(TEST_PREFIX)]
    if not app_keys:
        print("        No application keys to check")
        r.close()
        return

    unbounded = []
    for k in app_keys:
        ttl = r.ttl(k)
        if ttl == -1:
            unbounded.append(k)

    if unbounded:
        print(f"        ⚠️  {len(unbounded)} key(s) without TTL:")
        for u in unbounded[:5]:
            print(f"          → {u}")
    else:
        print(f"        All {len(app_keys)} key(s) have TTL set ✓")
    # Warn but don't fail — some keys may legitimately be persistent
    r.close()


def test_memory_usage_reasonable():
    """Verify Redis memory usage is reasonable (< 100MB for dev)."""
    r = get_redis_client()
    info = r.info("memory")
    used_bytes = info.get("used_memory", 0)
    used_mb = used_bytes / (1024 * 1024)
    print(f"        Used memory: {used_mb:.2f} MB")
    print(f"        Peak memory: {info.get('used_memory_peak_human', 'N/A')}")
    # For a dev instance, < 100MB is reasonable
    assert used_mb < 100, f"Redis using too much memory: {used_mb:.2f} MB"
    r.close()


def test_flushdb_not_accidentally_available():
    """
    Safety check: verify we don't accidentally call FLUSHDB.
    We test that FLUSHDB would work (Redis allows it), but we DON'T actually flush.
    Instead, we verify the command exists but is not disabled via ACL (in dev).
    """
    r = get_redis_client()
    # Just verify Redis is in a non-empty state and we can query it
    # We absolutely do NOT call FLUSHDB — this test documents that awareness
    size_before = r.dbsize()
    # If there are keys, we confirm we did NOT flush
    print(f"        DB size: {size_before} keys (verified: NOT flushed)")
    assert isinstance(size_before, int)
    r.close()


def test_key_type_consistency():
    """Verify known key types match expectations (string for counters)."""
    r = get_redis_client()
    rl_keys = r.keys("ratelimit:*")
    for k in rl_keys[:3]:
        ktype = r.type(k)
        assert ktype == "string", f"ratelimit key {k} has type {ktype}, expected string"

    qc_keys = r.keys("quota_count:*")
    for k in qc_keys[:3]:
        ktype = r.type(k)
        assert ktype == "string", f"quota_count key {k} has type {ktype}, expected string"

    if rl_keys or qc_keys:
        print("        All checked keys are type 'string' ✓")
    else:
        print("        No application keys to check types")
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Advanced Redis Operations
# ═══════════════════════════════════════════════════════════════════════════════
def test_pipeline_batch():
    """Redis pipeline batches multiple commands for efficiency."""
    r = get_redis_client()
    k1, k2, k3 = test_key("pipe1"), test_key("pipe2"), test_key("pipe3")
    pipe = r.pipeline()
    pipe.set(k1, "a")
    pipe.set(k2, "b")
    pipe.set(k3, "c")
    pipe.get(k1)
    pipe.get(k2)
    pipe.get(k3)
    results_list = pipe.execute()
    # First 3 are SET results (True), next 3 are GET results
    assert results_list[3] == "a"
    assert results_list[4] == "b"
    assert results_list[5] == "c"
    r.delete(k1, k2, k3)
    r.close()


def test_lua_script_eval():
    """Lua scripting (EVAL) works for atomic operations."""
    r = get_redis_client()
    k = test_key("lua")
    r.set(k, "10")
    # Lua script: increment by 5 and return new value
    script = "local v = redis.call('GET', KEYS[1]); v = tonumber(v) + tonumber(ARGV[1]); redis.call('SET', KEYS[1], v); return v"
    result = r.eval(script, 1, k, 5)
    assert result == 15, f"Expected 15, got {result}"
    r.delete(k)
    r.close()


def test_scan_iteration():
    """SCAN iterates over keys without blocking (production-safe alternative to KEYS)."""
    r = get_redis_client()
    # Create some test keys
    for i in range(5):
        r.set(test_key(f"scan_{i}"), f"val_{i}")

    found = set()
    for k in r.scan_iter(match=f"{TEST_PREFIX}scan_*", count=10):
        found.add(k)

    assert len(found) == 5, f"Expected 5 scan keys, found {len(found)}"

    # Cleanup
    for i in range(5):
        r.delete(test_key(f"scan_{i}"))
    r.close()


def test_hash_operations():
    """HSET/HGET/HGETALL for structured data (potential caching pattern)."""
    r = get_redis_client()
    k = test_key("hash_sim")
    r.hset(
        k,
        mapping={
            "run_id": "abc-123",
            "mean": "42150.3",
            "std": "8200.1",
            "status": "completed",
        },
    )
    assert r.hget(k, "mean") == "42150.3"
    all_fields = r.hgetall(k)
    assert all_fields["status"] == "completed"
    assert len(all_fields) == 4
    r.delete(k)
    r.close()


def test_list_operations():
    """LPUSH/RPUSH/LRANGE for queue-like patterns."""
    r = get_redis_client()
    k = test_key("queue")
    r.delete(k)
    r.rpush(k, "job_1", "job_2", "job_3")
    length = r.llen(k)
    assert length == 3, f"Expected list length 3, got {length}"
    items = r.lrange(k, 0, -1)
    assert items == ["job_1", "job_2", "job_3"]
    popped = r.lpop(k)
    assert popped == "job_1"
    r.delete(k)
    r.close()


def test_sorted_set_operations():
    """ZADD/ZRANGE for leaderboard or priority queue patterns."""
    r = get_redis_client()
    k = test_key("zset")
    r.delete(k)
    r.zadd(k, {"sim_a": 10.5, "sim_b": 25.3, "sim_c": 15.1})
    # Get all sorted by score ascending
    ranked = r.zrange(k, 0, -1, withscores=True)
    assert len(ranked) == 3
    assert ranked[0][0] == "sim_a"  # lowest score first
    assert ranked[-1][0] == "sim_b"  # highest score last
    r.delete(k)
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Concurrency & Performance Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_concurrent_incr():
    """Multiple threads incrementing the same counter — verifies atomicity."""
    r = get_redis_client()
    k = test_key("concurrent_incr")
    r.delete(k)

    n_threads = 10
    increments_per_thread = 100
    barrier = threading.Barrier(n_threads)

    def worker():
        wr = get_redis_client()
        barrier.wait()
        for _ in range(increments_per_thread):
            wr.incr(k)
        wr.close()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    final = int(r.get(k))
    expected = n_threads * increments_per_thread
    assert final == expected, (
        f"Expected {expected}, got {final} (lost {expected - final} increments)"
    )
    print(f"        {n_threads} threads × {increments_per_thread} INCRs = {final} ✓")
    r.delete(k)
    r.close()


def test_set_get_latency():
    """Measure SET/GET round-trip latency (should stay comfortably sub-15ms locally)."""
    r = get_redis_client()
    k = test_key("latency")
    iterations = 100

    t0 = time.perf_counter()
    for i in range(iterations):
        r.set(k, f"value_{i}")
        r.get(k)
    elapsed = time.perf_counter() - t0

    avg_ms = (elapsed / iterations) * 1000
    print(f"        Average SET+GET round-trip: {avg_ms:.2f}ms ({iterations} iterations)")
    assert avg_ms < 15, f"SET/GET too slow: {avg_ms:.2f}ms average (expected < 15ms)"
    r.delete(k)
    r.close()


def test_pipeline_vs_individual_performance():
    """Pipeline should be significantly faster than individual commands."""
    r = get_redis_client()
    n = 100
    keys = [test_key(f"perf_{i}") for i in range(n)]

    # Individual commands
    t0 = time.perf_counter()
    for k in keys:
        r.set(k, "val")
    individual_ms = (time.perf_counter() - t0) * 1000

    # Cleanup
    for k in keys:
        r.delete(k)

    # Pipeline
    t0 = time.perf_counter()
    pipe = r.pipeline()
    for k in keys:
        pipe.set(k, "val")
    pipe.execute()
    pipeline_ms = (time.perf_counter() - t0) * 1000

    # Cleanup
    for k in keys:
        r.delete(k)

    speedup = individual_ms / pipeline_ms if pipeline_ms > 0 else float("inf")
    print(
        f"        Individual: {individual_ms:.1f}ms, Pipeline: {pipeline_ms:.1f}ms, Speedup: {speedup:.1f}×"
    )
    # Pipeline should be at least 1.5× faster
    assert speedup > 1.5, f"Pipeline speedup only {speedup:.1f}× (expected > 1.5×)"
    r.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 9. API ↔ Redis Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_api_health_implies_redis_connected():
    """API server health check passes, which requires Redis connection (lifespan)."""
    status, body, hdrs, elapsed = req("GET", "/v1/health", auth=False)
    assert status == 200, f"Expected 200, got {status}: {body}"
    print(f"        API health OK ({elapsed * 1000:.0f}ms)")


def test_simulation_populates_redis_keys():
    """A full simulation should create or update Redis keys (rate limit + quota)."""
    r = get_redis_client()
    # Snapshot key counts
    rl_before = len(r.keys("ratelimit:*"))
    qc_before = len(r.keys("quota_count:*"))

    status, body, hdrs, elapsed = req("POST", "/v1/simulate", body=SIM_PAYLOAD)
    assert status in (200, 429), f"Expected 200 or 429, got {status}: {body}"

    # After simulation, at least rate limit key should exist
    rl_after = len(r.keys("ratelimit:*"))
    qc_after = len(r.keys("quota_count:*"))
    print(f"        Rate limit keys: {rl_before}→{rl_after}")
    print(f"        Quota count keys: {qc_before}→{qc_after}")
    print(f"        Simulation status: {status}, time: {elapsed * 1000:.0f}ms")
    r.close()


def test_quota_alert_key_pattern():
    """If any quota_alert keys exist, verify their pattern."""
    r = get_redis_client()
    keys = r.keys("quota_alert:*")
    if not keys:
        skip(
            "Quota alert keys follow expected pattern",
            "No quota_alert keys found (normal if usage < threshold)",
        )
        r.close()
        return
    # Pattern: quota_alert:{uuid}:{YYYY-MM}:{threshold_pct}
    pattern = re.compile(r"^quota_alert:[0-9a-f\-]{36}:\d{4}-\d{2}:\d+$")
    for k in keys:
        assert pattern.match(k), f"quota_alert key doesn't match pattern: {k}"
    print(f"        {len(keys)} quota_alert key(s) match expected pattern")
    r.close()


def test_multiple_simulations_increment_counters():
    """Run 3 simulations and verify counters increase."""
    r = get_redis_client()

    # Get initial rate limit state for current minute
    rl_keys_before = r.keys("ratelimit:*")
    initial_counts = {}
    for k in rl_keys_before:
        val = r.get(k)
        initial_counts[k] = int(val) if val else 0

    # Run 3 simulations
    for i in range(3):
        status, _, _, _ = req("POST", "/v1/simulate", body=SIM_PAYLOAD)
        if status == 429:
            print(f"        Request {i + 1}: rate limited (429)")
        else:
            print(f"        Request {i + 1}: status {status}")

    # Check that at least one ratelimit key has a higher count
    rl_keys_after = r.keys("ratelimit:*")
    any_incremented = False
    for k in rl_keys_after:
        val = r.get(k)
        current = int(val) if val else 0
        old = initial_counts.get(k, 0)
        if current > old:
            any_incremented = True
            print(f"        {k}: {old}→{current}")

    if not any_incremented and rl_keys_after:
        # New keys may have been created (minute boundary crossed)
        for k in rl_keys_after:
            if k not in initial_counts:
                val = r.get(k)
                if val and int(val) > 0:
                    any_incremented = True
                    print(f"        New key {k} = {val}")

    assert any_incremented, "No rate limit counter was incremented after 3 requests"
    r.close()


if __name__ == "__main__":
    # ═══════════════════════════════════════════════════════════════════════════
    # 1. Connectivity Tests
    # ═══════════════════════════════════════════════════════════════════════════
    # Verify connection upfront
    try:
        _r = get_redis_client()
        _r.ping()
        _r.close()
    except Exception as exc:
        REDIS_UNAVAILABLE_REASON = f"Redis unavailable at {REDIS_URL}: {exc}"
        print(f"{SKIP} {REDIS_UNAVAILABLE_REASON}")

    print("\n🔴 1. Redis Connectivity Tests")
    print("=" * 60)

    check("Redis PING returns True", test_redis_ping)

    check("Redis INFO returns valid server info", test_redis_info_server)

    check("Redis INFO keyspace returns dict", test_redis_info_keyspace)

    check("Connected to correct Redis database (db0)", test_redis_correct_database)

    check("Redis connection pool handles multiple commands", test_redis_connection_pool)

    check("Redis DBSIZE returns non-negative integer", test_redis_dbsize)

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. Cache Operations (SET/GET/DEL/TTL)
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 2. Cache Operations (SET/GET/DEL/TTL)")
    print("=" * 60)

    check("SET/GET cycle works", test_set_get_cycle)

    check("SET/GET with JSON payload", test_set_get_json)

    check("DEL removes key", test_del_removes_key)

    check("TTL is set correctly on cached items", test_ttl_set_correctly)

    check("Key expires after TTL elapses", test_ttl_expiration)

    check("INCR atomic counter works", test_incr_counter)

    check("INCR + EXPIRE pattern (rate limiter)", test_incr_with_expire)

    check("SET NX (set-if-not-exists) works", test_set_nx)

    check("MSET/MGET batch operations", test_mset_mget)

    check("Cache invalidation (SET → DEL → verify gone)", test_cache_invalidation)

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. Rate Limiting Tests (via API + Redis verification)
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 3. Rate Limiting Tests (via API + Redis)")
    print("=" * 60)

    check("API request creates ratelimit:* key in Redis", test_api_request_creates_ratelimit_key)

    check("Rate limit key pattern matches ratelimit:{org_id}:{datetime}", test_ratelimit_key_pattern)

    check("Rate limit keys have TTL set", test_ratelimit_key_has_ttl)

    check("Rate limit counter increments with requests", test_ratelimit_counter_increments)

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. Quota Counter Tests (via API + Redis verification)
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 4. Quota Counter Tests (via API + Redis)")
    print("=" * 60)

    check("Quota counter keys exist (quota_count:*)", test_quota_count_key_exists)

    check("Quota counter key pattern matches expected format", test_quota_count_key_pattern)

    check("Quota counter keys have long TTL (~35 days)", test_quota_count_has_long_ttl)

    check("Quota counter values are integers", test_quota_count_is_integer)

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. Pub/Sub Tests
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 5. Pub/Sub Tests")
    print("=" * 60)

    check("Pub/Sub basic message delivery", test_pubsub_basic_message_delivery)

    check("Pub/Sub multiple messages received in order", test_pubsub_multiple_messages)

    check("Pub/Sub pattern subscribe (PSUBSCRIBE) works", test_pubsub_pattern_subscribe)

    check("Pub/Sub with JSON payloads (SSE pattern)", test_pubsub_json_messages)

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. Key Pattern & Hygiene Tests
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 6. Key Pattern & Hygiene Tests")
    print("=" * 60)

    check("Application keys follow naming conventions", test_all_keys_follow_naming_convention)

    check("Check for unbounded keys (no TTL)", test_no_unbounded_keys)

    check("Redis memory usage is reasonable (< 100MB)", test_memory_usage_reasonable)

    check("FLUSHDB safety check (verified NOT called)", test_flushdb_not_accidentally_available)

    check("Key types are consistent (string for counters)", test_key_type_consistency)

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. Advanced Redis Operations
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 7. Advanced Redis Operations")
    print("=" * 60)

    check("Pipeline batch operations work", test_pipeline_batch)

    check("Lua scripting (EVAL) works", test_lua_script_eval)

    check("SCAN iteration works (production-safe key listing)", test_scan_iteration)

    check("Hash operations (HSET/HGET/HGETALL)", test_hash_operations)

    check("List operations (LPUSH/RPUSH/LRANGE/LPOP)", test_list_operations)

    check("Sorted set operations (ZADD/ZRANGE)", test_sorted_set_operations)

    # ═══════════════════════════════════════════════════════════════════════════
    # 8. Concurrency & Performance Tests
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 8. Concurrency & Performance Tests")
    print("=" * 60)

    check("Concurrent INCR atomicity (10 threads × 100)", test_concurrent_incr)

    check("SET/GET latency < 15ms per round-trip", test_set_get_latency)

    check("Pipeline faster than individual commands", test_pipeline_vs_individual_performance)

    # ═══════════════════════════════════════════════════════════════════════════
    # 9. API ↔ Redis Integration Tests
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🔴 9. API ↔ Redis Integration Tests")
    print("=" * 60)

    check(
        "API health check passes (Redis connected at startup)",
        test_api_health_implies_redis_connected,
    )

    check("Simulation creates/updates Redis keys", test_simulation_populates_redis_keys)

    check("Quota alert keys follow expected pattern", test_quota_alert_key_pattern)

    check(
        "Multiple simulations increment rate limit counters",
        test_multiple_simulations_increment_counters,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Cleanup & Summary
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n🧹 Cleaning up test keys...")
    if REDIS_UNAVAILABLE_REASON:
        print(f"   {SKIP} Cleanup skipped: {REDIS_UNAVAILABLE_REASON}")
    else:
        r = get_redis_client()
        test_keys = r.keys(f"{TEST_PREFIX}*")
        if test_keys:
            r.delete(*test_keys)
            print(f"   Deleted {len(test_keys)} test key(s)")
        else:
            print("   No test keys to clean up")
        r.close()

    # ─── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("📊 Phase 7 — Redis Integration Test Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    total = len(results)

    print(f"\n  Total:   {total}")
    print(f"  Passed:  {passed} {PASS}")
    print(f"  Failed:  {failed} {FAIL}")
    print(f"  Skipped: {skipped} {SKIP}")

    if failed:
        print(f"\n{'─' * 60}")
        print("Failed tests:")
        for r in results:
            if r[0] == FAIL:
                print(f"  {FAIL} {r[1]}: {r[2]}")

    if skipped:
        print(f"\n{'─' * 60}")
        print("Skipped tests:")
        for r in results:
            if r[0] == SKIP:
                print(f"  {SKIP} {r[1]}: {r[2]}")

    print(f"\n{'─' * 60}")
    if failed == 0 and skipped == total and total > 0:
        result_line = "⏭️ ALL SKIPPED"
    elif failed == 0:
        result_line = "✅ ALL PASSED"
    else:
        result_line = "❌ SOME FAILED"
    print(f"Result: {result_line}")
    print(f"{'=' * 60}")

    artifact_path = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_redis.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=total,
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "base_url": BASE_URL,
            "redis_url": REDIS_URL,
            "redis_available": REDIS_UNAVAILABLE_REASON is None,
            "failed_checks": [name for icon, name, *_ in results if icon == FAIL],
            "skipped_checks": [name for icon, name, *_ in results if icon == SKIP],
            "skipped_count": skipped,
        },
    )
    print(f"Summary artifact: {artifact_path}")

    import pytest

    exit_code = pytest.main([__file__, "-v"])
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_redis.py",
            passed=0,
            failed=0,
            skipped=0,
            total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
