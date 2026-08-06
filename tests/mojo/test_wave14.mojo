"""Wave 14 test suite — LRU Cache, Bloom Filter, CRC32, Rate Limiter."""

from structs.lru_cache import LRUCache
from structs.bloom_filter import BloomFilter
from crypto.crc32 import crc32, crc32_hex, crc32_combine
from net.rate_limiter import TokenBucket


def main() raises:
    print("━━━ Wave 14 test suite (LRU Cache, Bloom Filter, CRC32, Rate Limiter) ━━━\n")

    # ── LRU Cache ──
    var cache = LRUCache(3)  # capacity 3
    cache.put("a", 1.0)
    cache.put("b", 2.0)
    cache.put("c", 3.0)
    assert_true(cache.get("a", 0.0) == 1.0, "LRU: get existing key")
    cache.put("d", 4.0)  # evicts "b" (LRU after "a" was accessed)
    assert_true(not cache.contains("b"), "LRU: b should be evicted")
    assert_true(cache.contains("a"), "LRU: a should still exist")
    assert_true(cache.contains("d"), "LRU: d should exist")
    assert_true(cache.size() == 3, "LRU: size should be 3")

    # Test update existing key
    cache.put("a", 10.0)
    assert_true(cache.get("a", 0.0) == 10.0, "LRU: update value")

    # Test hit rate
    var cache2 = LRUCache(2)
    cache2.put("x", 1.0)
    _ = cache2.get("x")  # hit
    _ = cache2.get("y")  # miss
    assert_true(cache2.hit_rate() > 0.4, "LRU: hit rate > 0.4")
    assert_true(cache2.hit_rate() < 0.6, "LRU: hit rate < 0.6")

    # Test clear
    cache2.clear()
    assert_true(cache2.size() == 0, "LRU: clear empties cache")

    print("✅ LRU Cache")

    # ── Bloom Filter ──
    var bf = BloomFilter(1000, 0.01)
    bf.add("hello")
    bf.add("world")
    assert_true(bf.might_contain("hello"), "Bloom: hello should be present")
    assert_true(bf.might_contain("world"), "Bloom: world should be present")
    assert_true(not bf.might_contain("missing"), "Bloom: missing should not be present")
    assert_true(bf.count() == 2, "Bloom: count should be 2")

    # Test multiple items
    var bf2 = BloomFilter(100, 0.01)
    for i in range(50):
        bf2.add(String("item_") + String(i))
    assert_true(bf2.count() == 50, "Bloom: count should be 50")
    # All inserted items should be found
    var found_all = True
    for i in range(50):
        if not bf2.might_contain(String("item_") + String(i)):
            found_all = False
            break
    assert_true(found_all, "Bloom: all inserted items should be found")

    print("✅ Bloom Filter")

    # ── CRC32 ──
    var c1 = crc32("hello")
    var c2 = crc32("hello")
    assert_true(c1 == c2, "CRC32: deterministic")
    var c3 = crc32("world")
    assert_true(c1 != c3, "CRC32: different strings differ")
    var hex_val = crc32_hex("hello")
    assert_true(len(hex_val) == 8, "CRC32: hex is 8 chars")

    # Test known CRC-32 value for "hello" = 0x3610a686
    assert_true(c1 == UInt32(0x3610A686), "CRC32: known value for 'hello'")

    # Test empty string (CRC-32 of "" = 0x00000000)
    var c_empty = crc32("")
    assert_true(c_empty == UInt32(0x00000000), "CRC32: empty string is 0")

    # Test hex output
    var hex_hello = crc32_hex("hello")
    assert_true(hex_hello == "3610a686", "CRC32: hex of 'hello'")

    print("✅ CRC32")

    # ── Rate Limiter ──
    var rl = TokenBucket(10.0, 5)  # 10/sec, burst 5
    assert_true(rl.allow(), "RL: 1st request ok")
    assert_true(rl.allow(), "RL: 2nd request ok")
    assert_true(rl.allow(), "RL: 3rd request ok")
    assert_true(rl.allow(), "RL: 4th request ok")
    assert_true(rl.allow(), "RL: 5th request ok")
    assert_true(not rl.allow(), "RL: 6th request denied (burst exhausted)")
    assert_true(rl.tokens_available() == 0, "RL: 0 tokens left")

    # Test reset
    rl.reset()
    assert_true(rl.allow(), "RL: reset refills tokens")
    assert_true(rl.tokens_available() == 4, "RL: 4 tokens after 1 consumed")

    # Test allow_n
    var rl2 = TokenBucket(100.0, 10)
    assert_true(rl2.allow_n(5), "RL: allow_n(5) ok")
    assert_true(rl2.tokens_available() == 5, "RL: 5 tokens remaining")
    assert_true(not rl2.allow_n(6), "RL: allow_n(6) denied")
    assert_true(rl2.tokens_available() == 5, "RL: tokens unchanged after deny")
    assert_true(rl2.allow_n(5), "RL: allow_n(5) ok again")
    assert_true(rl2.tokens_available() == 0, "RL: 0 tokens")

    # Test add_tokens
    rl2.add_tokens(3)
    assert_true(rl2.tokens_available() == 3, "RL: add_tokens works")
    rl2.add_tokens(100)  # Should cap at burst
    assert_true(rl2.tokens_available() == 10, "RL: add_tokens capped at burst")

    print("✅ Rate Limiter")

    print("\n✅ All Wave 14 tests passed")


def assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + msg)
