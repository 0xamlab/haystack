"""bench_crypto_hash_chain.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.hash_chain import simple_hash, int_to_bytes, hash_single, combine_hashes, hash_chain_build, hash_chain_verify, merkle_root, merkle_proof, merkle_verify
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
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_simple_hash: Float64 = 0.0
    var _t0_simple_hash = perf_counter_ns()
    for _ in range(N):
        _acc_simple_hash += Float64(simple_hash(_li5))
    var _t1_simple_hash = perf_counter_ns()
    var _ns_simple_hash = Float64(_t1_simple_hash - _t0_simple_hash) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::simple_hash", _ns_simple_hash, _acc_simple_hash)
    var _acc_int_to_bytes: Float64 = 0.0
    var _t0_int_to_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_int_to_bytes = int_to_bytes(5)
        _acc_int_to_bytes += Float64(len(_r_int_to_bytes))
    var _t1_int_to_bytes = perf_counter_ns()
    var _ns_int_to_bytes = Float64(_t1_int_to_bytes - _t0_int_to_bytes) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::int_to_bytes", _ns_int_to_bytes, _acc_int_to_bytes)
    var _acc_hash_single: Float64 = 0.0
    var _t0_hash_single = perf_counter_ns()
    for _ in range(N):
        _acc_hash_single += Float64(hash_single(5))
    var _t1_hash_single = perf_counter_ns()
    var _ns_hash_single = Float64(_t1_hash_single - _t0_hash_single) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::hash_single", _ns_hash_single, _acc_hash_single)
    var _acc_combine_hashes: Float64 = 0.0
    var _t0_combine_hashes = perf_counter_ns()
    for _ in range(N):
        _acc_combine_hashes += Float64(combine_hashes(5, 5))
    var _t1_combine_hashes = perf_counter_ns()
    var _ns_combine_hashes = Float64(_t1_combine_hashes - _t0_combine_hashes) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::combine_hashes", _ns_combine_hashes, _acc_combine_hashes)
    var _acc_hash_chain_build: Float64 = 0.0
    var _t0_hash_chain_build = perf_counter_ns()
    for _ in range(N):
        var _r_hash_chain_build = hash_chain_build([[0,1,1],[1,0,1],[1,1,0]])
        _acc_hash_chain_build += Float64(len(_r_hash_chain_build))
    var _t1_hash_chain_build = perf_counter_ns()
    var _ns_hash_chain_build = Float64(_t1_hash_chain_build - _t0_hash_chain_build) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::hash_chain_build", _ns_hash_chain_build, _acc_hash_chain_build)
    var _acc_hash_chain_verify: Float64 = 0.0
    var _t0_hash_chain_verify = perf_counter_ns()
    for _ in range(N):
        _acc_hash_chain_verify += Float64(hash_chain_verify([[0,1,1],[1,0,1],[1,1,0]], _li5))
    var _t1_hash_chain_verify = perf_counter_ns()
    var _ns_hash_chain_verify = Float64(_t1_hash_chain_verify - _t0_hash_chain_verify) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::hash_chain_verify", _ns_hash_chain_verify, _acc_hash_chain_verify)
    var _acc_merkle_root: Float64 = 0.0
    var _t0_merkle_root = perf_counter_ns()
    for _ in range(N):
        _acc_merkle_root += Float64(merkle_root(_li5))
    var _t1_merkle_root = perf_counter_ns()
    var _ns_merkle_root = Float64(_t1_merkle_root - _t0_merkle_root) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::merkle_root", _ns_merkle_root, _acc_merkle_root)
    var _acc_merkle_proof: Float64 = 0.0
    var _t0_merkle_proof = perf_counter_ns()
    for _ in range(N):
        var _r_merkle_proof = merkle_proof(_li5, 5)
        _acc_merkle_proof += Float64(len(_r_merkle_proof))
    var _t1_merkle_proof = perf_counter_ns()
    var _ns_merkle_proof = Float64(_t1_merkle_proof - _t0_merkle_proof) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::merkle_proof", _ns_merkle_proof, _acc_merkle_proof)
    var _acc_merkle_verify: Float64 = 0.0
    var _t0_merkle_verify = perf_counter_ns()
    for _ in range(N):
        _acc_merkle_verify += Float64(merkle_verify(5, _li5, 5, 5))
    var _t1_merkle_verify = perf_counter_ns()
    var _ns_merkle_verify = Float64(_t1_merkle_verify - _t0_merkle_verify) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::merkle_verify", _ns_merkle_verify, _acc_merkle_verify)
