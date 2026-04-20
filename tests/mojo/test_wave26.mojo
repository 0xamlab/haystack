"""Tests for Wave 26 — Data Pipeline, Advanced Caching, Differential Privacy."""

from pipeline import (
    map_list,
    filter_list,
    reduce_sum,
    reduce_product,
    reduce_min,
    reduce_max,
    chain_map_filter,
    batch,
    flatten,
    zip_lists,
    window,
    unique_values,
)
from cache import (
    TTLCacheEntry,
    TTLCache,
    create_ttl_cache,
    cache_put,
    cache_get,
    cache_evict_expired,
    cache_size,
    cache_hit_rate,
    cache_clear,
    cache_contains,
)
from privacy import (
    laplace_mechanism,
    gaussian_mechanism,
    exponential_mechanism_scores,
    randomized_response,
    composition_epsilon,
    advanced_composition,
    sensitivity_l1,
    sensitivity_l2,
    dp_mean,
    dp_count,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Pipeline Tests ───────────────────────────────────────────────────────────


fn test_pipeline() raises:
    print("── Pipeline tests ──")
    var count = 0

    # 1. map_list square
    var d1 = List[Float64]()
    d1.append(1.0)
    d1.append(2.0)
    d1.append(3.0)
    var sq = map_list(d1, 0)
    _assert_close(sq[0], 1.0, 1e-9, "map square [0]")
    _assert_close(sq[1], 4.0, 1e-9, "map square [1]")
    _assert_close(sq[2], 9.0, 1e-9, "map square [2]")
    count += 3

    # 2. map_list sqrt
    var d2 = List[Float64]()
    d2.append(4.0)
    d2.append(9.0)
    var sr = map_list(d2, 1)
    _assert_close(sr[0], 2.0, 1e-9, "map sqrt [0]")
    _assert_close(sr[1], 3.0, 1e-9, "map sqrt [1]")
    count += 2

    # 3. map_list negate
    var d3 = List[Float64]()
    d3.append(5.0)
    d3.append(-3.0)
    var neg = map_list(d3, 2)
    _assert_close(neg[0], -5.0, 1e-9, "map negate [0]")
    _assert_close(neg[1], 3.0, 1e-9, "map negate [1]")
    count += 2

    # 4. map_list abs
    var ab = map_list(d3, 3)
    _assert_close(ab[0], 5.0, 1e-9, "map abs [0]")
    _assert_close(ab[1], 3.0, 1e-9, "map abs [1]")
    count += 2

    # 5. map_list double
    var dbl = map_list(d3, 4)
    _assert_close(dbl[0], 10.0, 1e-9, "map double [0]")
    count += 1

    # 6. filter_list > threshold
    var d4 = List[Float64]()
    d4.append(1.0)
    d4.append(2.0)
    d4.append(3.0)
    d4.append(4.0)
    d4.append(5.0)
    var gt3 = filter_list(d4, 0, 3.0)
    _assert_eq(len(gt3), 2, "filter > 3: length")
    _assert_close(gt3[0], 4.0, 1e-9, "filter > 3 [0]")
    _assert_close(gt3[1], 5.0, 1e-9, "filter > 3 [1]")
    count += 3

    # 7. filter_list < threshold
    var lt3 = filter_list(d4, 1, 3.0)
    _assert_eq(len(lt3), 2, "filter < 3: length")
    _assert_close(lt3[0], 1.0, 1e-9, "filter < 3 [0]")
    count += 2

    # 8. filter_list == threshold
    var eq3 = filter_list(d4, 2, 3.0)
    _assert_eq(len(eq3), 1, "filter == 3: length")
    _assert_close(eq3[0], 3.0, 1e-9, "filter == 3 [0]")
    count += 2

    # 9. filter_list >= threshold
    var ge3 = filter_list(d4, 3, 3.0)
    _assert_eq(len(ge3), 3, "filter >= 3: length")
    count += 1

    # 10. reduce_sum
    var d5 = List[Float64]()
    d5.append(1.0)
    d5.append(2.0)
    d5.append(3.0)
    _assert_close(reduce_sum(d5), 6.0, 1e-9, "reduce_sum")
    count += 1

    # 11. reduce_product
    var d6 = List[Float64]()
    d6.append(2.0)
    d6.append(3.0)
    d6.append(4.0)
    _assert_close(reduce_product(d6), 24.0, 1e-9, "reduce_product")
    count += 1

    # 12. reduce_min / reduce_max
    _assert_close(reduce_min(d4), 1.0, 1e-9, "reduce_min")
    _assert_close(reduce_max(d4), 5.0, 1e-9, "reduce_max")
    count += 2

    # 13. chain_map_filter — square then keep > 5
    var cmf = chain_map_filter(d4, 0, 0, 5.0)
    # 1→1, 2→4, 3→9, 4→16, 5→25; >5 ⇒ [9, 16, 25]
    _assert_eq(len(cmf), 3, "chain_map_filter: length")
    _assert_close(cmf[0], 9.0, 1e-9, "chain_map_filter [0]")
    _assert_close(cmf[2], 25.0, 1e-9, "chain_map_filter [2]")
    count += 3

    # 14. batch
    var batches = batch(d4, 2)
    _assert_eq(len(batches), 3, "batch: 3 batches")
    _assert_eq(len(batches[0]), 2, "batch[0] size 2")
    _assert_eq(len(batches[2]), 1, "batch[2] size 1 (last)")
    count += 3

    # 15. flatten roundtrip
    var flat = flatten(batches)
    _assert_eq(len(flat), 5, "flatten length")
    _assert_close(flat[0], 1.0, 1e-9, "flatten [0]")
    _assert_close(flat[4], 5.0, 1e-9, "flatten [4]")
    count += 3

    # 16. zip_lists
    var za = List[Float64]()
    za.append(10.0)
    za.append(20.0)
    za.append(30.0)
    var zb = List[Float64]()
    zb.append(1.0)
    zb.append(2.0)
    var zipped = zip_lists(za, zb)
    _assert_eq(len(zipped), 2, "zip_lists: length = min(3,2)")
    _assert_close(zipped[0][0], 10.0, 1e-9, "zip [0][0]")
    _assert_close(zipped[0][1], 1.0, 1e-9, "zip [0][1]")
    _assert_close(zipped[1][0], 20.0, 1e-9, "zip [1][0]")
    count += 4

    # 17. window
    var w = window(d4, 2)
    # [1,2,3,4,5] windows of size 2: [1,2],[2,3],[3,4],[4,5]
    _assert_eq(len(w), 4, "window: 4 windows")
    _assert_close(w[0][0], 1.0, 1e-9, "window[0][0]")
    _assert_close(w[0][1], 2.0, 1e-9, "window[0][1]")
    _assert_close(w[2][0], 3.0, 1e-9, "window[2][0]")
    _assert_close(w[2][1], 4.0, 1e-9, "window[2][1]")
    count += 5

    # 18. unique_values
    var du = List[Float64]()
    du.append(1.0)
    du.append(2.0)
    du.append(2.0)
    du.append(3.0)
    du.append(1.0)
    var uv = unique_values(du)
    _assert_eq(len(uv), 3, "unique_values: length 3")
    _assert_close(uv[0], 1.0, 1e-9, "unique [0]")
    _assert_close(uv[1], 2.0, 1e-9, "unique [1]")
    _assert_close(uv[2], 3.0, 1e-9, "unique [2]")
    count += 4

    print("  Pipeline: " + String(count) + " assertions passed ✓")


# ── Cache Tests ──────────────────────────────────────────────────────────────


fn test_cache() raises:
    print("── Cache tests ──")
    var count = 0

    # 1. create_ttl_cache — empty
    var c = create_ttl_cache(10, 5.0)
    _assert_eq(cache_size(c), 0, "new cache size 0")
    count += 1

    # 2. cache_put then cache_get
    cache_put(c, 1, 42.0, 0.0)
    var v = cache_get(c, 1, 1.0)
    _assert_close(v, 42.0, 1e-9, "get after put")
    count += 1

    # 3. cache_get on missing key
    var miss = cache_get(c, 999, 1.0)
    _assert_close(miss, -999999.0, 1e-9, "miss returns sentinel")
    count += 1

    # 4. cache_size after put
    _assert_eq(cache_size(c), 1, "cache size 1 after 1 put")
    count += 1

    # 5. Multiple puts
    cache_put(c, 2, 100.0, 1.0)
    cache_put(c, 3, 200.0, 2.0)
    _assert_eq(cache_size(c), 3, "cache size 3")
    count += 1

    # 6. cache_get on expired key
    # key=1 was put at time=0 with ttl=5, so it expires at time=5
    var expired = cache_get(c, 1, 6.0)
    _assert_close(expired, -999999.0, 1e-9, "expired key returns sentinel")
    count += 1

    # 7. cache_hit_rate — 1 hit, 2 misses so far
    var rate = cache_hit_rate(c)
    _assert_close(rate, 1.0 / 3.0, 1e-9, "hit rate 1/3")
    count += 1

    # 8. cache_contains — valid key
    _assert(cache_contains(c, 2, 3.0), "contains key=2 at t=3")
    count += 1

    # 9. cache_contains — expired key
    _assert(not cache_contains(c, 1, 6.0), "key=1 expired at t=6")
    count += 1

    # 10. cache_contains — missing key
    _assert(not cache_contains(c, 999, 0.0), "missing key not contained")
    count += 1

    # 11. cache_evict_expired
    # At time=10: key1 expires at 5, key2 at 6, key3 at 7 → all expired
    var removed = cache_evict_expired(c, 10.0)
    _assert_eq(removed, 3, "evict 3 expired entries")
    _assert_eq(cache_size(c), 0, "cache empty after eviction")
    count += 2

    # 12. cache_clear
    cache_put(c, 10, 1.0, 0.0)
    cache_put(c, 11, 2.0, 0.0)
    cache_clear(c)
    _assert_eq(cache_size(c), 0, "cache clear: size 0")
    _assert_eq(c.hits, 0, "cache clear: hits 0")
    _assert_eq(c.misses, 0, "cache clear: misses 0")
    count += 3

    # 13. Capacity eviction — oldest removed when over max_size
    var small = create_ttl_cache(3, 10.0)
    cache_put(small, 1, 10.0, 0.0)
    cache_put(small, 2, 20.0, 0.0)
    cache_put(small, 3, 30.0, 0.0)
    _assert_eq(cache_size(small), 3, "small cache full at 3")
    cache_put(small, 4, 40.0, 0.0)  # should evict key=1
    _assert_eq(cache_size(small), 3, "still 3 after overflow put")
    var evicted = cache_get(small, 1, 1.0)
    _assert_close(evicted, -999999.0, 1e-9, "key=1 evicted")
    var kept = cache_get(small, 4, 1.0)
    _assert_close(kept, 40.0, 1e-9, "key=4 present")
    count += 4

    # 14. Update existing key
    cache_put(small, 2, 99.0, 1.0)
    var updated = cache_get(small, 2, 2.0)
    _assert_close(updated, 99.0, 1e-9, "updated key=2")
    _assert_eq(cache_size(small), 3, "no size increase on update")
    count += 2

    print("  Cache: " + String(count) + " assertions passed ✓")


# ── Privacy Tests ────────────────────────────────────────────────────────────


fn test_privacy() raises:
    print("── Privacy tests ──")
    var count = 0

    # 1. laplace_mechanism — noise added
    var noisy = laplace_mechanism(100.0, 1.0, 1.0)
    _assert(noisy != 100.0, "laplace adds noise")
    count += 1

    # 2. laplace_mechanism — result is finite
    _assert(noisy > -1e15 and noisy < 1e15, "laplace result finite")
    count += 1

    # 3. gaussian_mechanism — noise added
    var gnoisy = gaussian_mechanism(100.0, 1.0, 1.0, 0.001)
    _assert(gnoisy != 100.0, "gaussian adds noise")
    count += 1

    # 4. gaussian_mechanism — result is finite
    _assert(gnoisy > -1e15 and gnoisy < 1e15, "gaussian result finite")
    count += 1

    # 5. randomized_response — p=1 always returns true value
    var all_true = True
    for _ in range(20):
        if not randomized_response(True, 1.0):
            all_true = False
    _assert(all_true, "randomized_response(True, 1.0) always True")
    count += 1

    # 6. randomized_response — p=1 with false value
    var all_false = True
    for _ in range(20):
        if randomized_response(False, 1.0):
            all_false = False
    _assert(all_false, "randomized_response(False, 1.0) always False")
    count += 1

    # 7. composition_epsilon
    var eps = List[Float64]()
    eps.append(0.5)
    eps.append(0.5)
    eps.append(0.5)
    _assert_close(composition_epsilon(eps), 1.5, 1e-9, "basic composition")
    count += 1

    # 8. composition_epsilon — single
    var eps1 = List[Float64]()
    eps1.append(1.0)
    _assert_close(composition_epsilon(eps1), 1.0, 1e-9, "composition single")
    count += 1

    # 9. advanced_composition > basic composition
    var basic_eps = 3.0 * 0.5  # k=3, eps=0.5
    var adv_eps = advanced_composition(0.5, 0.001, 3)
    _assert(adv_eps > basic_eps, "advanced > basic composition")
    count += 1

    # 10. advanced_composition — positive
    _assert(adv_eps > 0.0, "advanced composition positive")
    count += 1

    # 11. sensitivity_l1
    var sd = List[Float64]()
    sd.append(1.0)
    sd.append(-5.0)
    sd.append(3.0)
    _assert_close(sensitivity_l1(sd), 5.0, 1e-9, "sensitivity_l1 = max|x|")
    count += 1

    # 12. sensitivity_l2
    _assert_close(sensitivity_l2(sd), 5.0, 1e-9, "sensitivity_l2 = max|x|")
    count += 1

    # 13. sensitivity_l1 — all positive
    var sp = List[Float64]()
    sp.append(2.0)
    sp.append(7.0)
    sp.append(4.0)
    _assert_close(sensitivity_l1(sp), 7.0, 1e-9, "l1 all positive")
    count += 1

    # 14. dp_mean — result is finite and reasonable
    var dm_data = List[Float64]()
    for _ in range(100):
        dm_data.append(50.0)
    var dm = dp_mean(dm_data, 0.0, 100.0, 1.0)
    _assert(dm > 0.0 and dm < 100.0, "dp_mean in reasonable range")
    count += 1

    # 15. dp_mean — close to true mean for large n
    _assert(fabs(dm - 50.0) < 20.0, "dp_mean near 50 for n=100")
    count += 1

    # 16. dp_count — result near true count
    var dc = dp_count(100, 1.0)
    _assert(dc > 50.0 and dc < 150.0, "dp_count near 100")
    count += 1

    # 17. dp_count — noise added
    # Run multiple times; at least one should differ from 100
    var any_diff = False
    for _ in range(10):
        var dci = dp_count(100, 1.0)
        if fabs(dci - 100.0) > 0.001:
            any_diff = True
            break
    _assert(any_diff, "dp_count adds noise")
    count += 1

    # 18. exponential_mechanism_scores — higher score → higher weight
    var scores = List[Float64]()
    scores.append(1.0)
    scores.append(2.0)
    scores.append(5.0)
    var weights = exponential_mechanism_scores(scores, 1.0, 1.0)
    _assert_eq(len(weights), 3, "exp mech: 3 weights")
    _assert(weights[2] > weights[1], "higher score → higher weight (5>2)")
    _assert(weights[1] > weights[0], "higher score → higher weight (2>1)")
    count += 3

    # 19. exponential_mechanism_scores — all positive weights
    _assert(weights[0] > 0.0, "exp mech weight[0] > 0")
    count += 1

    print("  Privacy: " + String(count) + " assertions passed ✓")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=" * 60)
    print("Wave 26 — Data Pipeline, Advanced Caching, Differential Privacy")
    print("=" * 60)

    test_pipeline()
    test_cache()
    test_privacy()

    print("=" * 60)
    print("All Wave 26 tests passed ✓")
    print("=" * 60)
