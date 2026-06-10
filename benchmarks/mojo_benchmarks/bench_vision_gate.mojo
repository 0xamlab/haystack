"""bench_vision_gate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from vision_gate import should_use_cache, needs_clearer_image, is_text_heavy, quality_gate_passed, route_image_request
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

    var _acc_should_use_cache: Float64 = 0.0
    var _t0_should_use_cache = perf_counter_ns()
    for _ in range(N):
        _acc_should_use_cache += Float64(should_use_cache(True))
    var _t1_should_use_cache = perf_counter_ns()
    var _ns_should_use_cache = Float64(_t1_should_use_cache - _t0_should_use_cache) / Float64(N)
    print("MOJO_TIMING vision_gate::should_use_cache", _ns_should_use_cache, _acc_should_use_cache)
    var _result_should_use_cache = should_use_cache(True)
    var _summary_should_use_cache = _summary_bool(_result_should_use_cache)
    print("MOJO_RESULT vision_gate::should_use_cache", _summary_should_use_cache)
    var _acc_needs_clearer_image: Float64 = 0.0
    var _t0_needs_clearer_image = perf_counter_ns()
    for _ in range(N):
        _acc_needs_clearer_image += Float64(needs_clearer_image(0.5, 0.5))
    var _t1_needs_clearer_image = perf_counter_ns()
    var _ns_needs_clearer_image = Float64(_t1_needs_clearer_image - _t0_needs_clearer_image) / Float64(N)
    print("MOJO_TIMING vision_gate::needs_clearer_image", _ns_needs_clearer_image, _acc_needs_clearer_image)
    var _result_needs_clearer_image = needs_clearer_image(0.5, 0.5)
    var _summary_needs_clearer_image = _summary_bool(_result_needs_clearer_image)
    print("MOJO_RESULT vision_gate::needs_clearer_image", _summary_needs_clearer_image)
    var _acc_is_text_heavy: Float64 = 0.0
    var _t0_is_text_heavy = perf_counter_ns()
    for _ in range(N):
        _acc_is_text_heavy += Float64(is_text_heavy(0.5, 0.5))
    var _t1_is_text_heavy = perf_counter_ns()
    var _ns_is_text_heavy = Float64(_t1_is_text_heavy - _t0_is_text_heavy) / Float64(N)
    print("MOJO_TIMING vision_gate::is_text_heavy", _ns_is_text_heavy, _acc_is_text_heavy)
    var _result_is_text_heavy = is_text_heavy(0.5, 0.5)
    var _summary_is_text_heavy = _summary_bool(_result_is_text_heavy)
    print("MOJO_RESULT vision_gate::is_text_heavy", _summary_is_text_heavy)
    var _acc_quality_gate_passed: Float64 = 0.0
    var _t0_quality_gate_passed = perf_counter_ns()
    for _ in range(N):
        _acc_quality_gate_passed += Float64(quality_gate_passed(0.5, 0.5, 0.5))
    var _t1_quality_gate_passed = perf_counter_ns()
    var _ns_quality_gate_passed = Float64(_t1_quality_gate_passed - _t0_quality_gate_passed) / Float64(N)
    print("MOJO_TIMING vision_gate::quality_gate_passed", _ns_quality_gate_passed, _acc_quality_gate_passed)
    var _result_quality_gate_passed = quality_gate_passed(0.5, 0.5, 0.5)
    var _summary_quality_gate_passed = _summary_bool(_result_quality_gate_passed)
    print("MOJO_RESULT vision_gate::quality_gate_passed", _summary_quality_gate_passed)
    var _acc_route_image_request: Float64 = 0.0
    var _t0_route_image_request = perf_counter_ns()
    for _ in range(N):
        _acc_route_image_request += Float64(route_image_request(0.5, 0.5, 0.5, 0.5, True, 5))
    var _t1_route_image_request = perf_counter_ns()
    var _ns_route_image_request = Float64(_t1_route_image_request - _t0_route_image_request) / Float64(N)
    print("MOJO_TIMING vision_gate::route_image_request", _ns_route_image_request, _acc_route_image_request)
    var _result_route_image_request = route_image_request(0.5, 0.5, 0.5, 0.5, True, 5)
    var _summary_route_image_request = _summary_int(_result_route_image_request)
    print("MOJO_RESULT vision_gate::route_image_request", _summary_route_image_request)
