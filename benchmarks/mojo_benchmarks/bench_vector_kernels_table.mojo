"""bench_vector_kernels_table.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from vector_kernels.table import build_query, source_id_of, role_id_of, build_table_json, CandidateTable, RankRequest
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

fn _summary_rank_request(value: RankRequest) -> String:
    var vec_summary = _summary_list_float32(value.query_vec.data)
    return "rank_request:" + String(value.source_id) + ":" + String(value.role_id) + ":" + String(value.top_k) + ":" + _summary_float32(value.query_norm_inv) + ":" + String(_summary_hash_string(vec_summary))

fn _summary_candidate_table(value: CandidateTable) -> String:
    var joined = String("")
    for i in range(len(value.entries)):
        if i > 0: joined += "|"
        var vec_summary = _summary_list_float32(value.entries[i].vec.data)
        joined += String(value.entries[i].column_id) + ":"
        joined += String(value.entries[i].source_id) + ":"
        joined += String(value.entries[i].role_id) + ":"
        joined += _summary_float32(value.entries[i].norm_inv) + ":"
        joined += _summary_float32(value.entries[i].vec.norm_inv) + ":"
        joined += vec_summary
    return "candidate_table:" + String(len(value.entries)) + ":" + String(_summary_hash_string(joined))


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

    var _keeper_build_query = List[RankRequest]()
    _keeper_build_query.append(build_query("unit_price", 1, 1, 2))
    var _acc_build_query: Float64 = 0.0
    var _t0_build_query = perf_counter_ns()
    for _ in range(N):
        _keeper_build_query[0] = build_query("unit_price", 1, 1, 2)
        _acc_build_query += Float64(len(_keeper_build_query))
    var _t1_build_query = perf_counter_ns()
    var _ns_build_query = Float64(_t1_build_query - _t0_build_query) / Float64(N)
    print("MOJO_TIMING vector_kernels_table::build_query", _ns_build_query, _acc_build_query)
    var _result_build_query = build_query("unit_price", 1, 1, 2)
    var _summary_build_query = _summary_rank_request(_result_build_query)
    print("MOJO_RESULT vector_kernels_table::build_query", _summary_build_query)
    var _acc_source_id_of: Float64 = 0.0
    var _t0_source_id_of = perf_counter_ns()
    for _ in range(N):
        _ = source_id_of("POS")
    var _t1_source_id_of = perf_counter_ns()
    var _ns_source_id_of = Float64(_t1_source_id_of - _t0_source_id_of) / Float64(N)
    print("MOJO_TIMING vector_kernels_table::source_id_of", _ns_source_id_of, _acc_source_id_of)
    var _result_source_id_of = source_id_of("POS")
    var _summary_source_id_of = _summary_uint16(_result_source_id_of)
    print("MOJO_RESULT vector_kernels_table::source_id_of", _summary_source_id_of)
    var _acc_role_id_of: Float64 = 0.0
    var _t0_role_id_of = perf_counter_ns()
    for _ in range(N):
        _acc_role_id_of += Float64(role_id_of("unit_measure"))
    var _t1_role_id_of = perf_counter_ns()
    var _ns_role_id_of = Float64(_t1_role_id_of - _t0_role_id_of) / Float64(N)
    print("MOJO_TIMING vector_kernels_table::role_id_of", _ns_role_id_of, _acc_role_id_of)
    var _result_role_id_of = role_id_of("unit_measure")
    var _summary_role_id_of = _summary_uint8(_result_role_id_of)
    print("MOJO_RESULT vector_kernels_table::role_id_of", _summary_role_id_of)
    var _acc_build_table_json: Float64 = 0.0
    var _t0_build_table_json = perf_counter_ns()
    for _ in range(N):
        _ = build_table_json('[{"id":1,"source":"POS","role":"unit_measure","name":"unit_price"},{"id":2,"source":"BACKLOG","role":"derived_measure","name":"extended_price"},{"id":3,"source":"INVOICE","role":"derived_measure","name":"invoice_total"}]')
    var _t1_build_table_json = perf_counter_ns()
    var _ns_build_table_json = Float64(_t1_build_table_json - _t0_build_table_json) / Float64(N)
    print("MOJO_TIMING vector_kernels_table::build_table_json", _ns_build_table_json, _acc_build_table_json)
    var _result_build_table_json = build_table_json('[{"id":1,"source":"POS","role":"unit_measure","name":"unit_price"},{"id":2,"source":"BACKLOG","role":"derived_measure","name":"extended_price"},{"id":3,"source":"INVOICE","role":"derived_measure","name":"invoice_total"}]')
    var _summary_build_table_json = _summary_candidate_table(_result_build_table_json)
    print("MOJO_RESULT vector_kernels_table::build_table_json", _summary_build_table_json)
