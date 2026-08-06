"""bench_pulmonology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pulmonology import tidal_volume_predicted, minute_ventilation, alveolar_ventilation, fev1_fvc_ratio, peak_expiratory_flow, alveolar_oxygen, a_a_gradient, respiratory_quotient, compliance_static, airway_resistance
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_tidal_volume_predicted: Float64 = 0.0
    var _t0_tidal_volume_predicted = perf_counter_ns()
    for _ in range(N):
        _acc_tidal_volume_predicted += tidal_volume_predicted(0.5)
    var _t1_tidal_volume_predicted = perf_counter_ns()
    var _ns_tidal_volume_predicted = Float64(_t1_tidal_volume_predicted - _t0_tidal_volume_predicted) / Float64(N)
    print("MOJO_TIMING pulmonology::tidal_volume_predicted", _ns_tidal_volume_predicted, _acc_tidal_volume_predicted)
    var _result_tidal_volume_predicted = tidal_volume_predicted(0.5)
    var _summary_tidal_volume_predicted = _summary_float64(_result_tidal_volume_predicted)
    print("MOJO_RESULT pulmonology::tidal_volume_predicted", _summary_tidal_volume_predicted)
    var _acc_minute_ventilation: Float64 = 0.0
    var _t0_minute_ventilation = perf_counter_ns()
    for _ in range(N):
        _acc_minute_ventilation += minute_ventilation(0.5, 0.5)
    var _t1_minute_ventilation = perf_counter_ns()
    var _ns_minute_ventilation = Float64(_t1_minute_ventilation - _t0_minute_ventilation) / Float64(N)
    print("MOJO_TIMING pulmonology::minute_ventilation", _ns_minute_ventilation, _acc_minute_ventilation)
    var _result_minute_ventilation = minute_ventilation(0.5, 0.5)
    var _summary_minute_ventilation = _summary_float64(_result_minute_ventilation)
    print("MOJO_RESULT pulmonology::minute_ventilation", _summary_minute_ventilation)
    var _acc_alveolar_ventilation: Float64 = 0.0
    var _t0_alveolar_ventilation = perf_counter_ns()
    for _ in range(N):
        _acc_alveolar_ventilation += alveolar_ventilation(0.5, 0.5, 0.5)
    var _t1_alveolar_ventilation = perf_counter_ns()
    var _ns_alveolar_ventilation = Float64(_t1_alveolar_ventilation - _t0_alveolar_ventilation) / Float64(N)
    print("MOJO_TIMING pulmonology::alveolar_ventilation", _ns_alveolar_ventilation, _acc_alveolar_ventilation)
    var _result_alveolar_ventilation = alveolar_ventilation(0.5, 0.5, 0.5)
    var _summary_alveolar_ventilation = _summary_float64(_result_alveolar_ventilation)
    print("MOJO_RESULT pulmonology::alveolar_ventilation", _summary_alveolar_ventilation)
    var _acc_fev1_fvc_ratio: Float64 = 0.0
    var _t0_fev1_fvc_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_fev1_fvc_ratio += fev1_fvc_ratio(0.5, 0.5)
    var _t1_fev1_fvc_ratio = perf_counter_ns()
    var _ns_fev1_fvc_ratio = Float64(_t1_fev1_fvc_ratio - _t0_fev1_fvc_ratio) / Float64(N)
    print("MOJO_TIMING pulmonology::fev1_fvc_ratio", _ns_fev1_fvc_ratio, _acc_fev1_fvc_ratio)
    var _result_fev1_fvc_ratio = fev1_fvc_ratio(0.5, 0.5)
    var _summary_fev1_fvc_ratio = _summary_float64(_result_fev1_fvc_ratio)
    print("MOJO_RESULT pulmonology::fev1_fvc_ratio", _summary_fev1_fvc_ratio)
    var _acc_peak_expiratory_flow: Float64 = 0.0
    var _t0_peak_expiratory_flow = perf_counter_ns()
    for _ in range(N):
        _acc_peak_expiratory_flow += peak_expiratory_flow(0.5, 0.5)
    var _t1_peak_expiratory_flow = perf_counter_ns()
    var _ns_peak_expiratory_flow = Float64(_t1_peak_expiratory_flow - _t0_peak_expiratory_flow) / Float64(N)
    print("MOJO_TIMING pulmonology::peak_expiratory_flow", _ns_peak_expiratory_flow, _acc_peak_expiratory_flow)
    var _result_peak_expiratory_flow = peak_expiratory_flow(0.5, 0.5)
    var _summary_peak_expiratory_flow = _summary_float64(_result_peak_expiratory_flow)
    print("MOJO_RESULT pulmonology::peak_expiratory_flow", _summary_peak_expiratory_flow)
    var _acc_alveolar_oxygen: Float64 = 0.0
    var _t0_alveolar_oxygen = perf_counter_ns()
    for _ in range(N):
        _acc_alveolar_oxygen += alveolar_oxygen(0.5, 0.5, 0.5)
    var _t1_alveolar_oxygen = perf_counter_ns()
    var _ns_alveolar_oxygen = Float64(_t1_alveolar_oxygen - _t0_alveolar_oxygen) / Float64(N)
    print("MOJO_TIMING pulmonology::alveolar_oxygen", _ns_alveolar_oxygen, _acc_alveolar_oxygen)
    var _result_alveolar_oxygen = alveolar_oxygen(0.5, 0.5, 0.5)
    var _summary_alveolar_oxygen = _summary_float64(_result_alveolar_oxygen)
    print("MOJO_RESULT pulmonology::alveolar_oxygen", _summary_alveolar_oxygen)
    var _acc_a_a_gradient: Float64 = 0.0
    var _t0_a_a_gradient = perf_counter_ns()
    for _ in range(N):
        _acc_a_a_gradient += a_a_gradient(0.5, 0.5)
    var _t1_a_a_gradient = perf_counter_ns()
    var _ns_a_a_gradient = Float64(_t1_a_a_gradient - _t0_a_a_gradient) / Float64(N)
    print("MOJO_TIMING pulmonology::a_a_gradient", _ns_a_a_gradient, _acc_a_a_gradient)
    var _result_a_a_gradient = a_a_gradient(0.5, 0.5)
    var _summary_a_a_gradient = _summary_float64(_result_a_a_gradient)
    print("MOJO_RESULT pulmonology::a_a_gradient", _summary_a_a_gradient)
    var _acc_respiratory_quotient: Float64 = 0.0
    var _t0_respiratory_quotient = perf_counter_ns()
    for _ in range(N):
        _acc_respiratory_quotient += respiratory_quotient(0.5, 0.5)
    var _t1_respiratory_quotient = perf_counter_ns()
    var _ns_respiratory_quotient = Float64(_t1_respiratory_quotient - _t0_respiratory_quotient) / Float64(N)
    print("MOJO_TIMING pulmonology::respiratory_quotient", _ns_respiratory_quotient, _acc_respiratory_quotient)
    var _result_respiratory_quotient = respiratory_quotient(0.5, 0.5)
    var _summary_respiratory_quotient = _summary_float64(_result_respiratory_quotient)
    print("MOJO_RESULT pulmonology::respiratory_quotient", _summary_respiratory_quotient)
    var _acc_compliance_static: Float64 = 0.0
    var _t0_compliance_static = perf_counter_ns()
    for _ in range(N):
        _acc_compliance_static += compliance_static(0.5, 0.5)
    var _t1_compliance_static = perf_counter_ns()
    var _ns_compliance_static = Float64(_t1_compliance_static - _t0_compliance_static) / Float64(N)
    print("MOJO_TIMING pulmonology::compliance_static", _ns_compliance_static, _acc_compliance_static)
    var _result_compliance_static = compliance_static(0.5, 0.5)
    var _summary_compliance_static = _summary_float64(_result_compliance_static)
    print("MOJO_RESULT pulmonology::compliance_static", _summary_compliance_static)
    var _acc_airway_resistance: Float64 = 0.0
    var _t0_airway_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_airway_resistance += airway_resistance(0.5, 0.5)
    var _t1_airway_resistance = perf_counter_ns()
    var _ns_airway_resistance = Float64(_t1_airway_resistance - _t0_airway_resistance) / Float64(N)
    print("MOJO_TIMING pulmonology::airway_resistance", _ns_airway_resistance, _acc_airway_resistance)
    var _result_airway_resistance = airway_resistance(0.5, 0.5)
    var _summary_airway_resistance = _summary_float64(_result_airway_resistance)
    print("MOJO_RESULT pulmonology::airway_resistance", _summary_airway_resistance)
