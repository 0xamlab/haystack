"""
test_wave11.mojo — Tests for Wave 11 libraries: HashMap, Graph, Bit Utils.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave11.mojo
"""
from structs.hashmap import HashMap
from graph.algorithms import (
    Graph,
    graph_new,
    graph_add_edge,
    dijkstra,
    bfs,
    dfs,
    topological_sort,
    connected_components,
    shortest_path,
)
from bitops import (
    popcount,
    leading_zeros,
    trailing_zeros,
    next_power_of_2,
    is_power_of_2,
    reverse_bits,
    rotate_left,
    rotate_right,
    bit_set,
    bit_clear,
    bit_test,
    bit_toggle,
    fnv1a_hash,
)
from std.math import abs as fabs
from testing import assert_true


def main() raises:
    print("━━━ Wave 11 test suite (HashMap, Graph, Bit Utils) ━━━")
    print("")

    # ── HashMap ──────────────────────────────────────────────────────────
    var m = HashMap()
    m.put("alpha", 1.0)
    m.put("beta", 2.0)
    m.put("gamma", 3.0)
    assert_true(m.size() == 3, "HashMap size should be 3, got " + String(m.size()))
    assert_true(
        m.get("alpha", 0.0) == 1.0,
        "get(alpha) should be 1.0, got " + String(m.get("alpha", 0.0)),
    )
    assert_true(
        m.get("beta", 0.0) == 2.0,
        "get(beta) should be 2.0, got " + String(m.get("beta", 0.0)),
    )
    assert_true(m.contains("gamma"), "should contain gamma")
    assert_true(not m.contains("delta"), "should not contain delta")
    assert_true(
        m.get("missing", -1.0) == -1.0,
        "get(missing) should be -1.0, got " + String(m.get("missing", -1.0)),
    )
    m.put("alpha", 10.0)  # update
    assert_true(
        m.get("alpha", 0.0) == 10.0,
        "get(alpha) after update should be 10.0, got " + String(m.get("alpha", 0.0)),
    )
    assert_true(m.size() == 3, "size after update should still be 3")  # no new entry
    _ = m.remove("beta")
    assert_true(m.size() == 2, "size after remove should be 2")
    assert_true(not m.contains("beta"), "should not contain beta after remove")

    # Test all_keys and all_values
    var keys = m.all_keys()
    assert_true(len(keys) == 2, "all_keys should return 2 keys")
    var vals = m.all_values()
    assert_true(len(vals) == 2, "all_values should return 2 values")

    # Test resize by inserting many entries
    var m2 = HashMap(8)  # small initial capacity
    for i in range(20):
        m2.put(String("key") + String(i), Float64(i))
    assert_true(m2.size() == 20, "HashMap should hold 20 entries after resize")
    assert_true(
        m2.get("key5", -1.0) == 5.0,
        "get(key5) should be 5.0 after resize",
    )

    print("✅ HashMap")

    # ── Graph ────────────────────────────────────────────────────────────
    var g = graph_new(5)
    graph_add_edge(g, 0, 1, 4.0)
    graph_add_edge(g, 0, 2, 1.0)
    graph_add_edge(g, 2, 1, 2.0)
    graph_add_edge(g, 1, 3, 1.0)
    graph_add_edge(g, 2, 3, 5.0)
    var dist = dijkstra(g, 0)
    assert_true(
        fabs(dist[0]) < 0.001,
        "dijkstra dist[0] should be 0, got " + String(dist[0]),
    )
    assert_true(
        fabs(dist[1] - 3.0) < 0.001,
        "dijkstra dist[1] should be 3.0 (0→2→1 = 1+2), got " + String(dist[1]),
    )
    assert_true(
        fabs(dist[3] - 4.0) < 0.001,
        "dijkstra dist[3] should be 4.0 (0→2→1→3 = 1+2+1), got " + String(dist[3]),
    )

    # BFS
    var bfs_order = bfs(g, 0)
    assert_true(bfs_order[0] == 0, "BFS should start with source node 0")
    assert_true(len(bfs_order) >= 1, "BFS should visit at least the source")

    # DFS
    var dfs_order = dfs(g, 0)
    assert_true(dfs_order[0] == 0, "DFS should start with source node 0")
    assert_true(len(dfs_order) >= 1, "DFS should visit at least the source")

    # Shortest path
    var path = shortest_path(g, 0, 3)
    assert_true(len(path) > 0, "shortest_path should find a path from 0 to 3")
    assert_true(path[0] == 0, "shortest_path should start at source")
    assert_true(path[len(path) - 1] == 3, "shortest_path should end at target")

    # Topological sort (DAG: 0→1→3, 0→2→1, 2→3)
    var topo = topological_sort(g)
    assert_true(len(topo) >= 1, "topological_sort should return nodes")

    # Connected components
    var comp = connected_components(g)
    assert_true(len(comp) == 5, "connected_components should label all 5 nodes")
    # Nodes 0-3 are connected, node 4 is isolated
    assert_true(
        comp[0] == comp[1] and comp[1] == comp[2] and comp[2] == comp[3],
        "nodes 0-3 should be in the same component",
    )
    assert_true(
        comp[4] != comp[0],
        "isolated node 4 should be in a different component",
    )

    print("✅ Graph (Dijkstra, BFS, DFS, shortest_path, topo_sort, components)")

    # ── Bit ops ──────────────────────────────────────────────────────────
    assert_true(popcount(0b1011) == 3, "popcount(0b1011) should be 3")
    assert_true(popcount(0) == 0, "popcount(0) should be 0")
    assert_true(popcount(255) == 8, "popcount(255) should be 8")

    assert_true(is_power_of_2(64), "64 is a power of 2")
    assert_true(not is_power_of_2(63), "63 is not a power of 2")
    assert_true(is_power_of_2(1), "1 is a power of 2")
    assert_true(not is_power_of_2(0), "0 is not a power of 2")

    assert_true(
        next_power_of_2(5) == 8,
        "next_power_of_2(5) should be 8, got " + String(next_power_of_2(5)),
    )
    assert_true(
        next_power_of_2(8) == 8,
        "next_power_of_2(8) should be 8, got " + String(next_power_of_2(8)),
    )
    assert_true(
        next_power_of_2(1) == 1,
        "next_power_of_2(1) should be 1",
    )

    assert_true(bit_test(0b1010, 1), "bit 1 of 0b1010 should be set")
    assert_true(not bit_test(0b1010, 0), "bit 0 of 0b1010 should not be set")
    assert_true(bit_test(0b1010, 3), "bit 3 of 0b1010 should be set")

    assert_true(
        bit_set(0, 3) == 8,
        "bit_set(0, 3) should be 8, got " + String(bit_set(0, 3)),
    )
    assert_true(
        bit_clear(0b1111, 2) == 0b1011,
        "bit_clear(0b1111, 2) should be 0b1011, got " + String(bit_clear(0b1111, 2)),
    )
    assert_true(
        bit_toggle(0b1010, 0) == 0b1011,
        "bit_toggle(0b1010, 0) should be 0b1011",
    )
    assert_true(
        bit_toggle(0b1010, 1) == 0b1000,
        "bit_toggle(0b1010, 1) should be 0b1000",
    )

    # Leading / trailing zeros
    assert_true(trailing_zeros(8) == 3, "trailing_zeros(8) should be 3")
    assert_true(trailing_zeros(1) == 0, "trailing_zeros(1) should be 0")
    assert_true(trailing_zeros(0) == 64, "trailing_zeros(0) should be 64")

    # FNV-1a hash
    var h1 = fnv1a_hash("hello")
    var h2 = fnv1a_hash("hello")
    var h3 = fnv1a_hash("world")
    assert_true(h1 == h2, "fnv1a_hash should be deterministic")
    assert_true(h1 != h3, "fnv1a_hash should differ for different strings")
    assert_true(h1 > 0, "fnv1a_hash should be positive")

    # Rotate
    var val: UInt32 = 0b1
    var rotated = rotate_left(val, 4)
    assert_true(rotated == UInt32(16), "rotate_left(1, 4) should be 16")
    var back = rotate_right(rotated, 4)
    assert_true(back == UInt32(1), "rotate_right should undo rotate_left")

    print("✅ Bit ops")

    print("")
    print("✅ All Wave 11 tests passed")
