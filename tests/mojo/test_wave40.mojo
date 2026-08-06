"""Tests for Wave 40 — Regex Engine, Heap Structures, Stochastic Processes (150 LIBRARY MILESTONE!)."""

from regex_engine import (
    regex_match,
    regex_search,
    regex_find_first,
    match_literal,
    match_dot_star,
    match_char_class,
    count_matches,
    split_by_literal,
    is_valid_pattern,
)
from heap import (
    heapify_min,
    heapify_max,
    heap_push_min,
    heap_pop_min,
    heap_push_max,
    heap_pop_max,
    heap_peek_min,
    heap_peek_max,
    k_smallest,
    k_largest,
    merge_sorted_lists,
    running_median,
    is_min_heap,
)
from stochastic import (
    random_walk_1d,
    random_walk_2d,
    brownian_motion,
    geometric_brownian_motion,
    poisson_process,
    ornstein_uhlenbeck,
    birth_death_process,
    monte_carlo_pi,
    expected_hitting_time,
    first_passage_time,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Regex Engine tests ────────────────────────────────────────────────────────


def test_regex_engine() raises:
    print("── Regex Engine tests ──")
    var passed = 0

    # 1. regex_match("abc", "abc") == True
    _assert(regex_match("abc", "abc"), "regex_match('abc','abc') should be True")
    passed += 1

    # 2. regex_match("abc", "abcd") == False
    _assert(not regex_match("abc", "abcd"), "regex_match('abc','abcd') should be False")
    passed += 1

    # 3. regex_search("bc", "abcd") == True
    _assert(regex_search("bc", "abcd"), "regex_search('bc','abcd') should be True")
    passed += 1

    # 4. regex_search("xyz", "abcd") == False
    _assert(not regex_search("xyz", "abcd"), "regex_search('xyz','abcd') should be False")
    passed += 1

    # 5. match_literal("hello", "hello") == True
    _assert(match_literal("hello", "hello"), "match_literal('hello','hello') should be True")
    passed += 1

    # 6. match_literal("hello", "world") == False
    _assert(not match_literal("hello", "world"), "match_literal('hello','world') should be False")
    passed += 1

    # 7. match_char_class("abc", 97) == True (97='a')
    _assert(match_char_class("abc", 97), "match_char_class('abc',97) 'a' should match")
    passed += 1

    # 8. match_char_class("abc", 100) == False (100='d')
    _assert(not match_char_class("abc", 100), "match_char_class('abc',100) 'd' should not match")
    passed += 1

    # 9. match_char_class("a-z", 109) == True (109='m')
    _assert(match_char_class("a-z", 109), "match_char_class('a-z',109) 'm' should match")
    passed += 1

    # 10. match_char_class("0-9", 53) == True (53='5')
    _assert(match_char_class("0-9", 53), "match_char_class('0-9',53) '5' should match")
    passed += 1

    # 11. count_matches("ab", "ababab") == 3
    _assert(count_matches("ab", "ababab") == 3, "count_matches('ab','ababab') should be 3")
    passed += 1

    # 12. count_matches("xx", "xxxxx") == 2 (non-overlapping)
    _assert(count_matches("xx", "xxxxx") == 2, "count_matches('xx','xxxxx') should be 2")
    passed += 1

    # 13. split_by_literal("a,b,c", ",") -> 3 parts
    var parts = split_by_literal("a,b,c", ",")
    _assert(len(parts) == 3, "split_by_literal('a,b,c',',') should have 3 parts")
    passed += 1

    # 14. split_by_literal first part is "a"
    _assert(match_literal(parts[0], "a"), "split first part should be 'a'")
    passed += 1

    # 15. split_by_literal second part is "b"
    _assert(match_literal(parts[1], "b"), "split second part should be 'b'")
    passed += 1

    # 16. split_by_literal third part is "c"
    _assert(match_literal(parts[2], "c"), "split third part should be 'c'")
    passed += 1

    # 17. is_valid_pattern("abc") == True
    _assert(is_valid_pattern("abc"), "is_valid_pattern('abc') should be True")
    passed += 1

    # 18. is_valid_pattern("[a-z]") == True
    _assert(is_valid_pattern("[a-z]"), "is_valid_pattern('[a-z]') should be True")
    passed += 1

    # 19. is_valid_pattern("[abc") == False (unbalanced)
    _assert(not is_valid_pattern("[abc"), "is_valid_pattern('[abc') unbalanced should be False")
    passed += 1

    # 20. regex_find_first("bc", "abcd") == [1, 3]
    var found = regex_find_first("bc", "abcd")
    _assert(len(found) == 2, "regex_find_first('bc','abcd') should return 2 elements")
    passed += 1

    # 21. regex_find_first start position
    _assert(found[0] == 1, "regex_find_first('bc','abcd') start should be 1")
    passed += 1

    # 22. regex_find_first end position
    _assert(found[1] == 3, "regex_find_first('bc','abcd') end should be 3")
    passed += 1

    # 23. match_dot_star within bounds
    _assert(match_dot_star("hello", 0, 5), "match_dot_star should be True for valid bounds")
    passed += 1

    # 24. match_dot_star out of bounds
    _assert(not match_dot_star("hello", 0, 6), "match_dot_star should be False for end > len")
    passed += 1

    # 25. regex_match with dot
    _assert(regex_match("a.c", "abc"), "regex_match('a.c','abc') should be True")
    passed += 1

    # 26. regex_match with star
    _assert(regex_match("ab*c", "ac"), "regex_match('ab*c','ac') should be True (0 b's)")
    passed += 1

    # 27. regex_match with star multiple
    _assert(regex_match("ab*c", "abbc"), "regex_match('ab*c','abbc') should be True")
    passed += 1

    # 28. is_valid_pattern with leading quantifier
    _assert(not is_valid_pattern("*abc"), "is_valid_pattern('*abc') should be False")
    passed += 1

    print("  ✓ " + String(passed) + " regex engine tests passed")


# ── Heap tests ────────────────────────────────────────────────────────────────


def test_heap() raises:
    print("── Heap tests ──")
    var passed = 0

    # 29. heapify_min → first element is minimum
    var h1 = List[Float64]()
    h1.append(5.0)
    h1.append(3.0)
    h1.append(8.0)
    h1.append(1.0)
    h1.append(4.0)
    heapify_min(h1)
    _assert_close(h1[0], 1.0, 1e-10, "heapify_min: root should be 1.0")
    passed += 1

    # 30. is_min_heap after heapify_min
    _assert(is_min_heap(h1), "heapify_min result should satisfy min-heap property")
    passed += 1

    # 31. heap_push_min then peek
    var h2 = List[Float64]()
    heap_push_min(h2, 5.0)
    heap_push_min(h2, 3.0)
    heap_push_min(h2, 7.0)
    _assert_close(heap_peek_min(h2), 3.0, 1e-10, "heap_peek_min should be 3.0")
    passed += 1

    # 32. heap_push_min smaller value
    heap_push_min(h2, 1.0)
    _assert_close(heap_peek_min(h2), 1.0, 1e-10, "heap_peek_min should be 1.0 after push")
    passed += 1

    # 33. heap_pop_min returns ascending
    var v1 = heap_pop_min(h2)
    _assert_close(v1, 1.0, 1e-10, "first pop should be 1.0")
    passed += 1

    # 34. second pop ascending
    var v2 = heap_pop_min(h2)
    _assert_close(v2, 3.0, 1e-10, "second pop should be 3.0")
    passed += 1

    # 35. third pop ascending
    var v3 = heap_pop_min(h2)
    _assert_close(v3, 5.0, 1e-10, "third pop should be 5.0")
    passed += 1

    # 36. heapify_max → first element is maximum
    var h3 = List[Float64]()
    h3.append(5.0)
    h3.append(3.0)
    h3.append(8.0)
    h3.append(1.0)
    h3.append(4.0)
    heapify_max(h3)
    _assert_close(h3[0], 8.0, 1e-10, "heapify_max: root should be 8.0")
    passed += 1

    # 37. heap_pop_max returns descending
    var m1 = heap_pop_max(h3)
    _assert_close(m1, 8.0, 1e-10, "first max pop should be 8.0")
    passed += 1

    # 38. second max pop descending
    var m2 = heap_pop_max(h3)
    _assert_close(m2, 5.0, 1e-10, "second max pop should be 5.0")
    passed += 1

    # 39. heap_push_max then peek
    var h4 = List[Float64]()
    heap_push_max(h4, 2.0)
    heap_push_max(h4, 9.0)
    heap_push_max(h4, 5.0)
    _assert_close(heap_peek_max(h4), 9.0, 1e-10, "heap_peek_max should be 9.0")
    passed += 1

    # 40. k_smallest([5,1,3,2,4], 3) contains {1,2,3}
    var ks_data = List[Float64]()
    ks_data.append(5.0)
    ks_data.append(1.0)
    ks_data.append(3.0)
    ks_data.append(2.0)
    ks_data.append(4.0)
    var ks = k_smallest(ks_data, 3)
    _assert(len(ks) == 3, "k_smallest should return 3 elements")
    passed += 1

    # 41. k_smallest contains 1.0
    _assert_close(ks[0], 1.0, 1e-10, "k_smallest[0] should be 1.0")
    passed += 1

    # 42. k_smallest contains 2.0
    _assert_close(ks[1], 2.0, 1e-10, "k_smallest[1] should be 2.0")
    passed += 1

    # 43. k_smallest contains 3.0
    _assert_close(ks[2], 3.0, 1e-10, "k_smallest[2] should be 3.0")
    passed += 1

    # 44. k_largest([5,1,3,2,4], 2) contains {4,5}
    var kl = k_largest(ks_data, 2)
    _assert(len(kl) == 2, "k_largest should return 2 elements")
    passed += 1

    # 45. k_largest contains 4.0 and 5.0
    _assert_close(kl[0], 4.0, 1e-10, "k_largest[0] should be 4.0")
    passed += 1

    _assert_close(kl[1], 5.0, 1e-10, "k_largest[1] should be 5.0")
    passed += 1

    # 46. merge_sorted_lists
    var l1 = List[Float64]()
    l1.append(1.0)
    l1.append(3.0)
    l1.append(5.0)
    var l2 = List[Float64]()
    l2.append(2.0)
    l2.append(4.0)
    l2.append(6.0)
    var lists = List[List[Float64]]()
    lists.append(l1^)
    lists.append(l2^)
    var merged = merge_sorted_lists(lists)
    _assert(len(merged) == 6, "merge_sorted_lists should have 6 elements")
    passed += 1

    # 47. merged is sorted
    _assert_close(merged[0], 1.0, 1e-10, "merged[0] should be 1.0")
    passed += 1

    _assert_close(merged[2], 3.0, 1e-10, "merged[2] should be 3.0")
    passed += 1

    _assert_close(merged[5], 6.0, 1e-10, "merged[5] should be 6.0")
    passed += 1

    # 48. running_median([1,3,2,4])
    var rm_data = List[Float64]()
    rm_data.append(1.0)
    rm_data.append(3.0)
    rm_data.append(2.0)
    rm_data.append(4.0)
    var rm = running_median(rm_data)
    _assert(len(rm) == 4, "running_median should have 4 values")
    passed += 1

    # 49. running_median first = 1.0
    _assert_close(rm[0], 1.0, 1e-10, "running_median[0] should be 1.0")
    passed += 1

    # 50. running_median second = (1+3)/2 = 2.0
    _assert_close(rm[1], 2.0, 1e-10, "running_median[1] should be 2.0")
    passed += 1

    # 51. running_median third = 2.0 (median of {1,2,3})
    _assert_close(rm[2], 2.0, 1e-10, "running_median[2] should be 2.0")
    passed += 1

    # 52. running_median fourth = (2+3)/2 = 2.5
    _assert_close(rm[3], 2.5, 1e-10, "running_median[3] should be 2.5")
    passed += 1

    # 53. is_min_heap for valid heap
    var valid_heap = List[Float64]()
    valid_heap.append(1.0)
    valid_heap.append(2.0)
    valid_heap.append(3.0)
    _assert(is_min_heap(valid_heap), "is_min_heap should be True for [1,2,3]")
    passed += 1

    # 54. is_min_heap for invalid heap
    var invalid_heap = List[Float64]()
    invalid_heap.append(3.0)
    invalid_heap.append(1.0)
    invalid_heap.append(2.0)
    _assert(not is_min_heap(invalid_heap), "is_min_heap should be False for [3,1,2]")
    passed += 1

    print("  ✓ " + String(passed) + " heap tests passed")


# ── Stochastic tests ──────────────────────────────────────────────────────────


def test_stochastic() raises:
    print("── Stochastic tests ──")
    var passed = 0

    # 55. random_walk_1d(100) — length 101, starts at 0
    var rw = random_walk_1d(100)
    _assert(len(rw) == 101, "random_walk_1d(100) should have length 101")
    passed += 1

    # 56. starts at 0
    _assert_close(rw[0], 0.0, 1e-10, "random_walk_1d should start at 0")
    passed += 1

    # 57. each step is ±1
    var valid_steps = True
    for i in range(1, len(rw)):
        var diff = fabs(rw[i] - rw[i - 1])
        if fabs(diff - 1.0) > 1e-10:
            valid_steps = False
            break
    _assert(valid_steps, "random_walk_1d steps should all be ±1")
    passed += 1

    # 58. random_walk_2d(50) — length 51, starts at [0,0]
    var rw2 = random_walk_2d(50)
    _assert(len(rw2) == 51, "random_walk_2d(50) should have length 51")
    passed += 1

    # 59. starts at [0,0]
    _assert_close(rw2[0][0], 0.0, 1e-10, "random_walk_2d should start at x=0")
    passed += 1

    _assert_close(rw2[0][1], 0.0, 1e-10, "random_walk_2d should start at y=0")
    passed += 1

    # 60. brownian_motion(100) — starts at 0, length 101
    var bm = brownian_motion(100)
    _assert(len(bm) == 101, "brownian_motion(100) should have length 101")
    passed += 1

    # 61. starts at 0
    _assert_close(bm[0], 0.0, 1e-10, "brownian_motion should start at 0")
    passed += 1

    # 62. geometric_brownian_motion — starts at s0
    var gbm = geometric_brownian_motion(100.0, 0.05, 0.2, 0.01, 100)
    _assert(len(gbm) == 101, "GBM should have length 101")
    passed += 1

    # 63. GBM starts at s0
    _assert_close(gbm[0], 100.0, 1e-10, "GBM should start at s0=100")
    passed += 1

    # 64. GBM all positive
    var all_positive = True
    for i in range(len(gbm)):
        if gbm[i] <= 0.0:
            all_positive = False
            break
    _assert(all_positive, "GBM values should all be positive")
    passed += 1

    # 65. poisson_process — events in sorted order
    var pp = poisson_process(10.0, 5.0)
    var pp_sorted = True
    for i in range(1, len(pp)):
        if pp[i] < pp[i - 1]:
            pp_sorted = False
            break
    _assert(pp_sorted, "poisson_process events should be sorted")
    passed += 1

    # 66. poisson_process — all events < duration
    var pp_in_range = True
    for i in range(len(pp)):
        if pp[i] >= 5.0:
            pp_in_range = False
            break
    _assert(pp_in_range, "poisson_process events should all be < duration")
    passed += 1

    # 67. ornstein_uhlenbeck — length
    var ou = ornstein_uhlenbeck(5.0, 1.0, 0.0, 0.3, 0.01, 200)
    _assert(len(ou) == 201, "OU process should have length 201")
    passed += 1

    # 68. OU starts at x0
    _assert_close(ou[0], 5.0, 1e-10, "OU process should start at x0=5.0")
    passed += 1

    # 69. birth_death_process — all values >= 0
    var bd = birth_death_process(0.6, 0.4, 10, 200)
    _assert(len(bd) == 201, "birth_death should have length 201")
    passed += 1

    var bd_non_neg = True
    for i in range(len(bd)):
        if bd[i] < 0:
            bd_non_neg = False
            break
    _assert(bd_non_neg, "birth_death values should all be >= 0")
    passed += 1

    # 70. birth_death starts at initial
    _assert(bd[0] == 10, "birth_death should start at initial=10")
    passed += 1

    # 71. monte_carlo_pi(100000) — within 0.1 of π
    var pi_est = monte_carlo_pi(100000)
    _assert(fabs(pi_est - 3.14159265) < 0.1, "monte_carlo_pi should be within 0.1 of π")
    passed += 1

    # 72. expected_hitting_time unbiased
    var eht = expected_hitting_time(0.5, 5)
    _assert_close(eht, 25.0, 1e-10, "expected_hitting_time(0.5, 5) should be 25")
    passed += 1

    # 73. expected_hitting_time biased p>0.5
    var eht2 = expected_hitting_time(0.75, 10)
    _assert_close(eht2, 20.0, 1e-10, "expected_hitting_time(0.75, 10) should be 20")
    passed += 1

    # 74. expected_hitting_time p<0.5 → infinite
    var eht3 = expected_hitting_time(0.3, 5)
    _assert_close(eht3, -1.0, 1e-10, "expected_hitting_time(0.3, 5) should be -1 (infinite)")
    passed += 1

    # 75. poisson_process with higher rate produces more events on average
    var pp_fast = poisson_process(100.0, 1.0)
    var pp_slow = poisson_process(1.0, 1.0)
    # With rate=100 over duration=1, expect ~100 events vs ~1
    _assert(len(pp_fast) > len(pp_slow), "higher rate Poisson should produce more events")
    passed += 1

    print("  ✓ " + String(passed) + " stochastic tests passed")


# ── main ──────────────────────────────────────────────────────────────────────


def main() raises:
    print("=" * 60)
    print("Wave 40 Tests — Regex Engine, Heap, Stochastic Processes")
    print("🎯 150 LIBRARY MILESTONE!")
    print("=" * 60)

    test_regex_engine()
    test_heap()
    test_stochastic()

    print("=" * 60)
    print("🎉 All Wave 40 tests passed! 150 libraries milestone reached!")
    print("=" * 60)
