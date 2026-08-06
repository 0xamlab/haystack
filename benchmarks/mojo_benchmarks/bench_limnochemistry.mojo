"""bench_limnochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from limnochemistry import carbonate_alkalinity, ionic_strength, activity_coefficient_davies, pow_10, saturation_index_calcite, silicon_weathering_flux, redox_pe_eh, phosphorus_fractionation, nitrogen_speciation, doc_light_attenuation, epilimnion_mixing_depth
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

    var _acc_carbonate_alkalinity: Float64 = 0.0
    var _t0_carbonate_alkalinity = perf_counter_ns()
    for _ in range(N):
        _acc_carbonate_alkalinity += carbonate_alkalinity(0.5, 0.5, 0.5, 0.5)
    var _t1_carbonate_alkalinity = perf_counter_ns()
    var _ns_carbonate_alkalinity = Float64(_t1_carbonate_alkalinity - _t0_carbonate_alkalinity) / Float64(N)
    print("MOJO_TIMING limnochemistry::carbonate_alkalinity", _ns_carbonate_alkalinity, _acc_carbonate_alkalinity)
    var _result_carbonate_alkalinity = carbonate_alkalinity(0.5, 0.5, 0.5, 0.5)
    var _summary_carbonate_alkalinity = _summary_float64(_result_carbonate_alkalinity)
    print("MOJO_RESULT limnochemistry::carbonate_alkalinity", _summary_carbonate_alkalinity)
    var _acc_ionic_strength: Float64 = 0.0
    var _t0_ionic_strength = perf_counter_ns()
    for _ in range(N):
        _acc_ionic_strength += ionic_strength(0.5, 0.5)
    var _t1_ionic_strength = perf_counter_ns()
    var _ns_ionic_strength = Float64(_t1_ionic_strength - _t0_ionic_strength) / Float64(N)
    print("MOJO_TIMING limnochemistry::ionic_strength", _ns_ionic_strength, _acc_ionic_strength)
    var _result_ionic_strength = ionic_strength(0.5, 0.5)
    var _summary_ionic_strength = _summary_float64(_result_ionic_strength)
    print("MOJO_RESULT limnochemistry::ionic_strength", _summary_ionic_strength)
    var _acc_activity_coefficient_davies: Float64 = 0.0
    var _t0_activity_coefficient_davies = perf_counter_ns()
    for _ in range(N):
        _acc_activity_coefficient_davies += activity_coefficient_davies(0.5, 0.5)
    var _t1_activity_coefficient_davies = perf_counter_ns()
    var _ns_activity_coefficient_davies = Float64(_t1_activity_coefficient_davies - _t0_activity_coefficient_davies) / Float64(N)
    print("MOJO_TIMING limnochemistry::activity_coefficient_davies", _ns_activity_coefficient_davies, _acc_activity_coefficient_davies)
    var _result_activity_coefficient_davies = activity_coefficient_davies(0.5, 0.5)
    var _summary_activity_coefficient_davies = _summary_float64(_result_activity_coefficient_davies)
    print("MOJO_RESULT limnochemistry::activity_coefficient_davies", _summary_activity_coefficient_davies)
    var _acc_pow_10: Float64 = 0.0
    var _t0_pow_10 = perf_counter_ns()
    for _ in range(N):
        _acc_pow_10 += pow_10(0.5)
    var _t1_pow_10 = perf_counter_ns()
    var _ns_pow_10 = Float64(_t1_pow_10 - _t0_pow_10) / Float64(N)
    print("MOJO_TIMING limnochemistry::pow_10", _ns_pow_10, _acc_pow_10)
    var _result_pow_10 = pow_10(0.5)
    var _summary_pow_10 = _summary_float64(_result_pow_10)
    print("MOJO_RESULT limnochemistry::pow_10", _summary_pow_10)
    var _acc_saturation_index_calcite: Float64 = 0.0
    var _t0_saturation_index_calcite = perf_counter_ns()
    for _ in range(N):
        _acc_saturation_index_calcite += saturation_index_calcite(0.5, 0.5, 0.5, 0.5)
    var _t1_saturation_index_calcite = perf_counter_ns()
    var _ns_saturation_index_calcite = Float64(_t1_saturation_index_calcite - _t0_saturation_index_calcite) / Float64(N)
    print("MOJO_TIMING limnochemistry::saturation_index_calcite", _ns_saturation_index_calcite, _acc_saturation_index_calcite)
    var _result_saturation_index_calcite = saturation_index_calcite(0.5, 0.5, 0.5, 0.5)
    var _summary_saturation_index_calcite = _summary_float64(_result_saturation_index_calcite)
    print("MOJO_RESULT limnochemistry::saturation_index_calcite", _summary_saturation_index_calcite)
    var _acc_silicon_weathering_flux: Float64 = 0.0
    var _t0_silicon_weathering_flux = perf_counter_ns()
    for _ in range(N):
        _acc_silicon_weathering_flux += silicon_weathering_flux(0.5, 0.5, 0.5)
    var _t1_silicon_weathering_flux = perf_counter_ns()
    var _ns_silicon_weathering_flux = Float64(_t1_silicon_weathering_flux - _t0_silicon_weathering_flux) / Float64(N)
    print("MOJO_TIMING limnochemistry::silicon_weathering_flux", _ns_silicon_weathering_flux, _acc_silicon_weathering_flux)
    var _result_silicon_weathering_flux = silicon_weathering_flux(0.5, 0.5, 0.5)
    var _summary_silicon_weathering_flux = _summary_float64(_result_silicon_weathering_flux)
    print("MOJO_RESULT limnochemistry::silicon_weathering_flux", _summary_silicon_weathering_flux)
    var _acc_redox_pe_eh: Float64 = 0.0
    var _t0_redox_pe_eh = perf_counter_ns()
    for _ in range(N):
        _acc_redox_pe_eh += redox_pe_eh(0.5, 0.5)
    var _t1_redox_pe_eh = perf_counter_ns()
    var _ns_redox_pe_eh = Float64(_t1_redox_pe_eh - _t0_redox_pe_eh) / Float64(N)
    print("MOJO_TIMING limnochemistry::redox_pe_eh", _ns_redox_pe_eh, _acc_redox_pe_eh)
    var _result_redox_pe_eh = redox_pe_eh(0.5, 0.5)
    var _summary_redox_pe_eh = _summary_float64(_result_redox_pe_eh)
    print("MOJO_RESULT limnochemistry::redox_pe_eh", _summary_redox_pe_eh)
    var _acc_phosphorus_fractionation: Float64 = 0.0
    var _t0_phosphorus_fractionation = perf_counter_ns()
    for _ in range(N):
        _acc_phosphorus_fractionation += phosphorus_fractionation(0.5, 0.5)
    var _t1_phosphorus_fractionation = perf_counter_ns()
    var _ns_phosphorus_fractionation = Float64(_t1_phosphorus_fractionation - _t0_phosphorus_fractionation) / Float64(N)
    print("MOJO_TIMING limnochemistry::phosphorus_fractionation", _ns_phosphorus_fractionation, _acc_phosphorus_fractionation)
    var _result_phosphorus_fractionation = phosphorus_fractionation(0.5, 0.5)
    var _summary_phosphorus_fractionation = _summary_float64(_result_phosphorus_fractionation)
    print("MOJO_RESULT limnochemistry::phosphorus_fractionation", _summary_phosphorus_fractionation)
    var _acc_nitrogen_speciation: Float64 = 0.0
    var _t0_nitrogen_speciation = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_speciation += nitrogen_speciation(0.5, 0.5, 0.5)
    var _t1_nitrogen_speciation = perf_counter_ns()
    var _ns_nitrogen_speciation = Float64(_t1_nitrogen_speciation - _t0_nitrogen_speciation) / Float64(N)
    print("MOJO_TIMING limnochemistry::nitrogen_speciation", _ns_nitrogen_speciation, _acc_nitrogen_speciation)
    var _result_nitrogen_speciation = nitrogen_speciation(0.5, 0.5, 0.5)
    var _summary_nitrogen_speciation = _summary_float64(_result_nitrogen_speciation)
    print("MOJO_RESULT limnochemistry::nitrogen_speciation", _summary_nitrogen_speciation)
    var _acc_doc_light_attenuation: Float64 = 0.0
    var _t0_doc_light_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_doc_light_attenuation += doc_light_attenuation(0.5, 0.5)
    var _t1_doc_light_attenuation = perf_counter_ns()
    var _ns_doc_light_attenuation = Float64(_t1_doc_light_attenuation - _t0_doc_light_attenuation) / Float64(N)
    print("MOJO_TIMING limnochemistry::doc_light_attenuation", _ns_doc_light_attenuation, _acc_doc_light_attenuation)
    var _result_doc_light_attenuation = doc_light_attenuation(0.5, 0.5)
    var _summary_doc_light_attenuation = _summary_float64(_result_doc_light_attenuation)
    print("MOJO_RESULT limnochemistry::doc_light_attenuation", _summary_doc_light_attenuation)
    var _acc_epilimnion_mixing_depth: Float64 = 0.0
    var _t0_epilimnion_mixing_depth = perf_counter_ns()
    for _ in range(N):
        _acc_epilimnion_mixing_depth += epilimnion_mixing_depth(0.5, 0.5, 0.5)
    var _t1_epilimnion_mixing_depth = perf_counter_ns()
    var _ns_epilimnion_mixing_depth = Float64(_t1_epilimnion_mixing_depth - _t0_epilimnion_mixing_depth) / Float64(N)
    print("MOJO_TIMING limnochemistry::epilimnion_mixing_depth", _ns_epilimnion_mixing_depth, _acc_epilimnion_mixing_depth)
    var _result_epilimnion_mixing_depth = epilimnion_mixing_depth(0.5, 0.5, 0.5)
    var _summary_epilimnion_mixing_depth = _summary_float64(_result_epilimnion_mixing_depth)
    print("MOJO_RESULT limnochemistry::epilimnion_mixing_depth", _summary_epilimnion_mixing_depth)
