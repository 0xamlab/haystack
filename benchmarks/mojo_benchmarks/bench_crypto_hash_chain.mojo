"""bench_crypto_hash_chain.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.hash_chain import simple_hash, int_to_bytes, hash_single, combine_hashes, hash_chain_build, hash_chain_verify, merkle_root, merkle_proof, merkle_verify
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_simple_hash = simple_hash(_li5)
    var _summary_simple_hash = _summary_int(_result_simple_hash)
    print("MOJO_RESULT crypto_hash_chain::simple_hash", _summary_simple_hash)
    var _acc_int_to_bytes: Float64 = 0.0
    var _t0_int_to_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_int_to_bytes = int_to_bytes(5)
        _acc_int_to_bytes += Float64(len(_r_int_to_bytes))
    var _t1_int_to_bytes = perf_counter_ns()
    var _ns_int_to_bytes = Float64(_t1_int_to_bytes - _t0_int_to_bytes) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::int_to_bytes", _ns_int_to_bytes, _acc_int_to_bytes)
    var _result_int_to_bytes = int_to_bytes(5)
    var _summary_int_to_bytes = _summary_list_int(_result_int_to_bytes)
    print("MOJO_RESULT crypto_hash_chain::int_to_bytes", _summary_int_to_bytes)
    var _acc_hash_single: Float64 = 0.0
    var _t0_hash_single = perf_counter_ns()
    for _ in range(N):
        _acc_hash_single += Float64(hash_single(5))
    var _t1_hash_single = perf_counter_ns()
    var _ns_hash_single = Float64(_t1_hash_single - _t0_hash_single) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::hash_single", _ns_hash_single, _acc_hash_single)
    var _result_hash_single = hash_single(5)
    var _summary_hash_single = _summary_int(_result_hash_single)
    print("MOJO_RESULT crypto_hash_chain::hash_single", _summary_hash_single)
    var _acc_combine_hashes: Float64 = 0.0
    var _t0_combine_hashes = perf_counter_ns()
    for _ in range(N):
        _acc_combine_hashes += Float64(combine_hashes(5, 5))
    var _t1_combine_hashes = perf_counter_ns()
    var _ns_combine_hashes = Float64(_t1_combine_hashes - _t0_combine_hashes) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::combine_hashes", _ns_combine_hashes, _acc_combine_hashes)
    var _result_combine_hashes = combine_hashes(5, 5)
    var _summary_combine_hashes = _summary_int(_result_combine_hashes)
    print("MOJO_RESULT crypto_hash_chain::combine_hashes", _summary_combine_hashes)
    var _acc_hash_chain_build: Float64 = 0.0
    var _t0_hash_chain_build = perf_counter_ns()
    for _ in range(N):
        var _r_hash_chain_build = hash_chain_build([[0,1,1],[1,0,1],[1,1,0]])
        _acc_hash_chain_build += Float64(len(_r_hash_chain_build))
    var _t1_hash_chain_build = perf_counter_ns()
    var _ns_hash_chain_build = Float64(_t1_hash_chain_build - _t0_hash_chain_build) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::hash_chain_build", _ns_hash_chain_build, _acc_hash_chain_build)
    var _result_hash_chain_build = hash_chain_build([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_hash_chain_build = _summary_list_int(_result_hash_chain_build)
    print("MOJO_RESULT crypto_hash_chain::hash_chain_build", _summary_hash_chain_build)
    var _acc_hash_chain_verify: Float64 = 0.0
    var _t0_hash_chain_verify = perf_counter_ns()
    for _ in range(N):
        _acc_hash_chain_verify += Float64(hash_chain_verify([[0,1,1],[1,0,1],[1,1,0]], _li5))
    var _t1_hash_chain_verify = perf_counter_ns()
    var _ns_hash_chain_verify = Float64(_t1_hash_chain_verify - _t0_hash_chain_verify) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::hash_chain_verify", _ns_hash_chain_verify, _acc_hash_chain_verify)
    var _result_hash_chain_verify = hash_chain_verify([[0,1,1],[1,0,1],[1,1,0]], _li5)
    var _summary_hash_chain_verify = _summary_bool(_result_hash_chain_verify)
    print("MOJO_RESULT crypto_hash_chain::hash_chain_verify", _summary_hash_chain_verify)
    var _acc_merkle_root: Float64 = 0.0
    var _t0_merkle_root = perf_counter_ns()
    for _ in range(N):
        _acc_merkle_root += Float64(merkle_root(_li5))
    var _t1_merkle_root = perf_counter_ns()
    var _ns_merkle_root = Float64(_t1_merkle_root - _t0_merkle_root) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::merkle_root", _ns_merkle_root, _acc_merkle_root)
    var _result_merkle_root = merkle_root(_li5)
    var _summary_merkle_root = _summary_int(_result_merkle_root)
    print("MOJO_RESULT crypto_hash_chain::merkle_root", _summary_merkle_root)
    var _acc_merkle_proof: Float64 = 0.0
    var _t0_merkle_proof = perf_counter_ns()
    for _ in range(N):
        var _r_merkle_proof = merkle_proof(_li5, 5)
        _acc_merkle_proof += Float64(len(_r_merkle_proof))
    var _t1_merkle_proof = perf_counter_ns()
    var _ns_merkle_proof = Float64(_t1_merkle_proof - _t0_merkle_proof) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::merkle_proof", _ns_merkle_proof, _acc_merkle_proof)
    var _result_merkle_proof = merkle_proof(_li5, 5)
    var _summary_merkle_proof = _summary_list_int(_result_merkle_proof)
    print("MOJO_RESULT crypto_hash_chain::merkle_proof", _summary_merkle_proof)
    var _acc_merkle_verify: Float64 = 0.0
    var _t0_merkle_verify = perf_counter_ns()
    for _ in range(N):
        _acc_merkle_verify += Float64(merkle_verify(5, _li5, 5, 5))
    var _t1_merkle_verify = perf_counter_ns()
    var _ns_merkle_verify = Float64(_t1_merkle_verify - _t0_merkle_verify) / Float64(N)
    print("MOJO_TIMING crypto_hash_chain::merkle_verify", _ns_merkle_verify, _acc_merkle_verify)
    var _result_merkle_verify = merkle_verify(5, _li5, 5, 5)
    var _summary_merkle_verify = _summary_bool(_result_merkle_verify)
    print("MOJO_RESULT crypto_hash_chain::merkle_verify", _summary_merkle_verify)
