"""bench_trie.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from trie import trie_count_words, trie_count_nodes, trie_word_list, Trie
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var N: Int = 10000

    var _acc_trie_count_words: Float64 = 0.0
    var _t0_trie_count_words = perf_counter_ns()
    for _ in range(N):
        _acc_trie_count_words += Float64(trie_count_words(Trie()))
    var _t1_trie_count_words = perf_counter_ns()
    var _ns_trie_count_words = Float64(_t1_trie_count_words - _t0_trie_count_words) / Float64(N)
    print("MOJO_TIMING trie::trie_count_words", _ns_trie_count_words, _acc_trie_count_words)
    var _acc_trie_count_nodes: Float64 = 0.0
    var _t0_trie_count_nodes = perf_counter_ns()
    for _ in range(N):
        _acc_trie_count_nodes += Float64(trie_count_nodes(Trie()))
    var _t1_trie_count_nodes = perf_counter_ns()
    var _ns_trie_count_nodes = Float64(_t1_trie_count_nodes - _t0_trie_count_nodes) / Float64(N)
    print("MOJO_TIMING trie::trie_count_nodes", _ns_trie_count_nodes, _acc_trie_count_nodes)
    var _acc_trie_word_list: Float64 = 0.0
    var _t0_trie_word_list = perf_counter_ns()
    for _ in range(N):
        var _r_trie_word_list = trie_word_list(Trie())
        _acc_trie_word_list += Float64(len(_r_trie_word_list))
    var _t1_trie_word_list = perf_counter_ns()
    var _ns_trie_word_list = Float64(_t1_trie_word_list - _t0_trie_word_list) / Float64(N)
    print("MOJO_TIMING trie::trie_word_list", _ns_trie_word_list, _acc_trie_word_list)
