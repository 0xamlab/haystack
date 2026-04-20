"""Tests for Wave 36 — Pattern Matching, Weighted Graphs, Metrics Aggregation."""

from pattern import (
    glob_match,
    starts_with,
    ends_with,
    contains,
    count_occurrences,
    replace_all,
    template_substitute,
    split_string,
    join_strings,
    pad_left,
    pad_right,
    trim,
)
from graph.weighted import (
    WeightedEdge,
    kruskal_mst,
    mst_total_weight,
    floyd_warshall,
    bellman_ford,
    has_negative_cycle,
    shortest_path_dijkstra,
    union_find_create,
    union_find_find,
    union_find_union,
)
from metrics_agg import (
    MetricsCounter,
    counter_create,
    counter_inc,
    counter_value,
    Histogram,
    histogram_create,
    histogram_observe,
    histogram_bucket_counts,
    histogram_mean,
    histogram_percentile,
    rate,
    gauge_set,
    compute_throughput,
    latency_stats,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Pattern tests ────────────────────────────────────────────────────────────


fn test_pattern() raises:
    print("── Pattern tests ──")
    var passed = 0

    # 1. glob_match *.txt matches file.txt
    _assert(glob_match("*.txt", "file.txt"), "glob *.txt vs file.txt")
    passed += 1

    # 2. glob_match *.txt does not match file.csv
    _assert(not glob_match("*.txt", "file.csv"), "glob *.txt vs file.csv")
    passed += 1

    # 3. glob_match test? matches test1
    _assert(glob_match("test?", "test1"), "glob test? vs test1")
    passed += 1

    # 4. glob_match test? does not match test12
    _assert(not glob_match("test?", "test12"), "glob test? vs test12")
    passed += 1

    # 5. glob_match with multiple wildcards
    _assert(glob_match("*.*.txt", "file.name.txt"), "glob *.*.txt")
    passed += 1

    # 6. glob_match exact match
    _assert(glob_match("hello", "hello"), "glob exact hello")
    passed += 1

    # 7. glob_match * matches anything
    _assert(glob_match("*", "anything"), "glob * matches anything")
    passed += 1

    # 8. starts_with
    _assert(starts_with("hello world", "hello"), "starts_with hello")
    passed += 1

    # 9. starts_with negative
    _assert(not starts_with("hello world", "world"), "starts_with world false")
    passed += 1

    # 10. ends_with
    _assert(ends_with("hello world", "world"), "ends_with world")
    passed += 1

    # 11. ends_with negative
    _assert(not ends_with("hello world", "hello"), "ends_with hello false")
    passed += 1

    # 12. contains
    _assert(contains("hello world", "lo wo"), "contains lo wo")
    passed += 1

    # 13. contains negative
    _assert(not contains("hello world", "xyz"), "contains xyz false")
    passed += 1

    # 14. count_occurrences
    _assert(count_occurrences("abcabc", "abc") == 2, "count abc in abcabc")
    passed += 1

    # 15. count_occurrences no match
    _assert(count_occurrences("hello", "xyz") == 0, "count xyz in hello")
    passed += 1

    # 16. count_occurrences single
    _assert(count_occurrences("abcdef", "cd") == 1, "count cd in abcdef")
    passed += 1

    # 17. replace_all
    _assert(replace_all("hello world", "world", "mojo") == "hello mojo", "replace world->mojo")
    passed += 1

    # 18. replace_all multiple
    _assert(replace_all("aaa", "a", "bb") == "bbbbbb", "replace a->bb in aaa")
    passed += 1

    # 19. template_substitute
    var keys = List[String]()
    keys.append("name")
    var vals = List[String]()
    vals.append("Angel")
    _assert(template_substitute("Hi {{name}}", keys, vals) == "Hi Angel", "template name=Angel")
    passed += 1

    # 20. template_substitute multiple keys
    var keys2 = List[String]()
    keys2.append("a")
    keys2.append("b")
    var vals2 = List[String]()
    vals2.append("1")
    vals2.append("2")
    _assert(template_substitute("{{a}}+{{b}}", keys2, vals2) == "1+2", "template a+b")
    passed += 1

    # 21. split_string
    var parts = split_string("a,b,c", ",")
    _assert(len(parts) == 3, "split a,b,c has 3 parts")
    passed += 1

    # 22. split_string values
    _assert(parts[0] == "a" and parts[1] == "b" and parts[2] == "c", "split values a b c")
    passed += 1

    # 23. join_strings
    var jp = List[String]()
    jp.append("a")
    jp.append("b")
    jp.append("c")
    _assert(join_strings(jp, "-") == "a-b-c", "join a-b-c")
    passed += 1

    # 24. trim
    _assert(trim("  hello  ") == "hello", "trim spaces")
    passed += 1

    # 25. trim tabs/newlines
    _assert(trim("\t\nhello\n\t") == "hello", "trim tabs newlines")
    passed += 1

    # 26. pad_left
    _assert(pad_left("hi", 5) == "   hi", "pad_left hi to 5")
    passed += 1

    # 27. pad_right
    _assert(pad_right("hi", 5) == "hi   ", "pad_right hi to 5")
    passed += 1

    # 28. pad_left already wide enough
    _assert(pad_left("hello", 3) == "hello", "pad_left no-op")
    passed += 1

    print("  ✓ Pattern:", passed, "passed")


# ── Weighted graph tests ─────────────────────────────────────────────────────


fn test_weighted_graph() raises:
    print("── Weighted graph tests ──")
    var passed = 0

    # Triangle: 0-1 (1.0), 1-2 (2.0), 0-2 (4.0)
    var edges = List[WeightedEdge]()
    edges.append(WeightedEdge(0, 1, 1.0))
    edges.append(WeightedEdge(1, 2, 2.0))
    edges.append(WeightedEdge(0, 2, 4.0))

    # 29. Kruskal MST on triangle → 2 edges
    var mst = kruskal_mst(3, edges)
    _assert(len(mst) == 2, "MST of triangle has 2 edges")
    passed += 1

    # 30. MST total weight = 1.0 + 2.0 = 3.0
    _assert_close(mst_total_weight(mst), 3.0, 1e-9, "MST weight = 3.0")
    passed += 1

    # 31. Floyd-Warshall on directed triangle
    var dir_edges = List[WeightedEdge]()
    dir_edges.append(WeightedEdge(0, 1, 1.0))
    dir_edges.append(WeightedEdge(1, 2, 2.0))
    dir_edges.append(WeightedEdge(0, 2, 10.0))
    var fw = floyd_warshall(3, dir_edges)
    _assert_close(fw[0][2], 3.0, 1e-9, "FW 0->2 = 3.0 (via 1)")
    passed += 1

    # 32. FW diagonal = 0
    _assert_close(fw[0][0], 0.0, 1e-9, "FW 0->0 = 0")
    passed += 1

    # 33. FW direct edge
    _assert_close(fw[0][1], 1.0, 1e-9, "FW 0->1 = 1.0")
    passed += 1

    # 34. Bellman-Ford
    var bf = bellman_ford(3, dir_edges, 0)
    _assert_close(bf[0], 0.0, 1e-9, "BF source dist = 0")
    passed += 1

    # 35. BF shortest to 2
    _assert_close(bf[2], 3.0, 1e-9, "BF 0->2 = 3.0")
    passed += 1

    # 36. Dijkstra matches Bellman-Ford on non-negative
    var dijk = shortest_path_dijkstra(3, dir_edges, 0)
    _assert_close(dijk[2], bf[2], 1e-9, "Dijkstra == BF for node 2")
    passed += 1

    # 37. Dijkstra source = 0
    _assert_close(dijk[0], 0.0, 1e-9, "Dijkstra source = 0")
    passed += 1

    # 38. has_negative_cycle False for positive graph
    _assert(not has_negative_cycle(3, dir_edges), "no negative cycle in positive graph")
    passed += 1

    # 39. has_negative_cycle True for negative cycle
    var neg_edges = List[WeightedEdge]()
    neg_edges.append(WeightedEdge(0, 1, 1.0))
    neg_edges.append(WeightedEdge(1, 2, -3.0))
    neg_edges.append(WeightedEdge(2, 0, 1.0))
    _assert(has_negative_cycle(3, neg_edges), "negative cycle detected")
    passed += 1

    # 40. Union-Find create
    var parent = union_find_create(5)
    _assert(len(parent) == 5, "UF create 5 nodes")
    passed += 1

    # 41. UF find self
    _assert(union_find_find(parent, 0) == 0, "UF find(0) = 0")
    passed += 1

    # 42. UF union different sets
    var merged = union_find_union(parent, 0, 1)
    _assert(merged, "UF union 0,1 merged")
    passed += 1

    # 43. UF same set after union
    _assert(union_find_find(parent, 0) == union_find_find(parent, 1), "UF 0 and 1 same set")
    passed += 1

    # 44. UF union same set returns False
    var merged2 = union_find_union(parent, 0, 1)
    _assert(not merged2, "UF union same set = False")
    passed += 1

    # 45. Bellman-Ford with negative edges (no cycle)
    var neg_no_cycle = List[WeightedEdge]()
    neg_no_cycle.append(WeightedEdge(0, 1, 4.0))
    neg_no_cycle.append(WeightedEdge(0, 2, 5.0))
    neg_no_cycle.append(WeightedEdge(1, 2, -3.0))
    var bf2 = bellman_ford(3, neg_no_cycle, 0)
    _assert_close(bf2[2], 1.0, 1e-9, "BF neg edge: 0->1->2 = 4 + (-3) = 1")
    passed += 1

    print("  ✓ Weighted graph:", passed, "passed")


# ── Metrics tests ────────────────────────────────────────────────────────────


fn test_metrics() raises:
    print("── Metrics tests ──")
    var passed = 0

    # 46. counter_create value = 0
    var c = counter_create("requests")
    _assert_close(counter_value(c), 0.0, 1e-9, "counter starts at 0")
    passed += 1

    # 47. counter_inc default
    counter_inc(c)
    _assert_close(counter_value(c), 1.0, 1e-9, "counter after inc = 1")
    passed += 1

    # 48. counter_inc amount
    counter_inc(c, 5.0)
    _assert_close(counter_value(c), 6.0, 1e-9, "counter after inc(5) = 6")
    passed += 1

    # 49. counter name
    _assert(c.name == "requests", "counter name")
    passed += 1

    # 50. histogram create and observe
    var bounds = List[Float64]()
    bounds.append(10.0)
    bounds.append(50.0)
    bounds.append(100.0)
    var h = histogram_create("latency", bounds)
    histogram_observe(h, 5.0)
    histogram_observe(h, 15.0)
    histogram_observe(h, 25.0)
    histogram_observe(h, 75.0)
    histogram_observe(h, 150.0)

    # 51. histogram_mean
    # mean = (5 + 15 + 25 + 75 + 150) / 5 = 270 / 5 = 54.0
    _assert_close(histogram_mean(h), 54.0, 1e-9, "histogram mean = 54")
    passed += 1

    # 52. histogram_bucket_counts
    var counts = histogram_bucket_counts(h)
    # <=10: 5 → 1, <=50: 15,25 → 2, <=100: 75 → 1, >100: 150 → 1
    _assert(counts[0] == 1, "bucket <=10 count = 1")
    passed += 1

    # 53.
    _assert(counts[1] == 2, "bucket <=50 count = 2")
    passed += 1

    # 54.
    _assert(counts[2] == 1, "bucket <=100 count = 1")
    passed += 1

    # 55.
    _assert(counts[3] == 1, "bucket >100 count = 1")
    passed += 1

    # 56. histogram_percentile p50
    # sorted: 5, 15, 25, 75, 150 → p50 = rank 2.5 → idx 2 → 15
    var p50 = histogram_percentile(h, 50.0)
    _assert_close(p50, 15.0, 1e-9, "histogram p50 = 15")
    passed += 1

    # 57. histogram_percentile p0 (min)
    var p0 = histogram_percentile(h, 1.0)
    _assert_close(p0, 5.0, 1e-9, "histogram p1 = 5 (min)")
    passed += 1

    # 58. rate
    var rate_vals = List[Float64]()
    rate_vals.append(0.0)
    rate_vals.append(10.0)
    rate_vals.append(20.0)
    _assert_close(rate(rate_vals, 1.0), 10.0, 1e-9, "rate = 10.0")
    passed += 1

    # 59. rate with different interval
    _assert_close(rate(rate_vals, 2.0), 5.0, 1e-9, "rate interval 2 = 5.0")
    passed += 1

    # 60. compute_throughput
    _assert_close(compute_throughput(100, 10.0), 10.0, 1e-9, "throughput 100/10 = 10")
    passed += 1

    # 61. compute_throughput zero duration
    _assert_close(compute_throughput(100, 0.0), 0.0, 1e-9, "throughput zero dur = 0")
    passed += 1

    # 62. gauge_set
    var g: Float64 = 0.0
    var result = gauge_set(g, 42.0)
    _assert_close(result, 42.0, 1e-9, "gauge_set returns 42")
    passed += 1

    # 63. latency_stats
    var lats = List[Float64]()
    lats.append(10.0)
    lats.append(20.0)
    lats.append(30.0)
    lats.append(40.0)
    lats.append(50.0)
    lats.append(60.0)
    lats.append(70.0)
    lats.append(80.0)
    lats.append(90.0)
    lats.append(100.0)
    var stats = latency_stats(lats)
    # [min, max, mean, p50, p95, p99]
    _assert_close(stats[0], 10.0, 1e-9, "latency min = 10")
    passed += 1

    # 64. latency max
    _assert_close(stats[1], 100.0, 1e-9, "latency max = 100")
    passed += 1

    # 65. latency mean
    _assert_close(stats[2], 55.0, 1e-9, "latency mean = 55")
    passed += 1

    # 66. min <= p50
    _assert(stats[0] <= stats[3], "min <= p50")
    passed += 1

    # 67. p50 <= p95
    _assert(stats[3] <= stats[4], "p50 <= p95")
    passed += 1

    # 68. p95 <= p99
    _assert(stats[4] <= stats[5], "p95 <= p99")
    passed += 1

    # 69. p99 <= max
    _assert(stats[5] <= stats[1], "p99 <= max")
    passed += 1

    print("  ✓ Metrics:", passed, "passed")


# ── main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 36 Tests ===")
    test_pattern()
    test_weighted_graph()
    test_metrics()
    print("=== All Wave 36 tests passed ===")
