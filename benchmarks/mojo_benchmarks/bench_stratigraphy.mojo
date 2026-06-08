"""bench_stratigraphy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from stratigraphy import sedimentation_rate, age_from_depth, radiometric_age, radiocarbon_age, stratigraphic_column_depth, isotope_fractionation, unconformity_gap, thermal_maturity_vitrinite, compaction_correction, sea_level_proxy
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

    var _acc_sedimentation_rate: Float64 = 0.0
    var _t0_sedimentation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_sedimentation_rate += sedimentation_rate(0.5, 0.5)
    var _t1_sedimentation_rate = perf_counter_ns()
    var _ns_sedimentation_rate = Float64(_t1_sedimentation_rate - _t0_sedimentation_rate) / Float64(N)
    print("MOJO_TIMING stratigraphy::sedimentation_rate", _ns_sedimentation_rate, _acc_sedimentation_rate)
    var _result_sedimentation_rate = sedimentation_rate(0.5, 0.5)
    var _summary_sedimentation_rate = _summary_float64(_result_sedimentation_rate)
    print("MOJO_RESULT stratigraphy::sedimentation_rate", _summary_sedimentation_rate)
    var _acc_age_from_depth: Float64 = 0.0
    var _t0_age_from_depth = perf_counter_ns()
    for _ in range(N):
        _acc_age_from_depth += age_from_depth(0.5, 0.5, 0.5)
    var _t1_age_from_depth = perf_counter_ns()
    var _ns_age_from_depth = Float64(_t1_age_from_depth - _t0_age_from_depth) / Float64(N)
    print("MOJO_TIMING stratigraphy::age_from_depth", _ns_age_from_depth, _acc_age_from_depth)
    var _result_age_from_depth = age_from_depth(0.5, 0.5, 0.5)
    var _summary_age_from_depth = _summary_float64(_result_age_from_depth)
    print("MOJO_RESULT stratigraphy::age_from_depth", _summary_age_from_depth)
    var _acc_radiometric_age: Float64 = 0.0
    var _t0_radiometric_age = perf_counter_ns()
    for _ in range(N):
        _acc_radiometric_age += radiometric_age(0.5, 0.5)
    var _t1_radiometric_age = perf_counter_ns()
    var _ns_radiometric_age = Float64(_t1_radiometric_age - _t0_radiometric_age) / Float64(N)
    print("MOJO_TIMING stratigraphy::radiometric_age", _ns_radiometric_age, _acc_radiometric_age)
    var _result_radiometric_age = radiometric_age(0.5, 0.5)
    var _summary_radiometric_age = _summary_float64(_result_radiometric_age)
    print("MOJO_RESULT stratigraphy::radiometric_age", _summary_radiometric_age)
    var _acc_radiocarbon_age: Float64 = 0.0
    var _t0_radiocarbon_age = perf_counter_ns()
    for _ in range(N):
        _acc_radiocarbon_age += radiocarbon_age(0.5)
    var _t1_radiocarbon_age = perf_counter_ns()
    var _ns_radiocarbon_age = Float64(_t1_radiocarbon_age - _t0_radiocarbon_age) / Float64(N)
    print("MOJO_TIMING stratigraphy::radiocarbon_age", _ns_radiocarbon_age, _acc_radiocarbon_age)
    var _result_radiocarbon_age = radiocarbon_age(0.5)
    var _summary_radiocarbon_age = _summary_float64(_result_radiocarbon_age)
    print("MOJO_RESULT stratigraphy::radiocarbon_age", _summary_radiocarbon_age)
    var _acc_stratigraphic_column_depth: Float64 = 0.0
    var _t0_stratigraphic_column_depth = perf_counter_ns()
    for _ in range(N):
        _acc_stratigraphic_column_depth += stratigraphic_column_depth(0.5, 0.5, 0.5)
    var _t1_stratigraphic_column_depth = perf_counter_ns()
    var _ns_stratigraphic_column_depth = Float64(_t1_stratigraphic_column_depth - _t0_stratigraphic_column_depth) / Float64(N)
    print("MOJO_TIMING stratigraphy::stratigraphic_column_depth", _ns_stratigraphic_column_depth, _acc_stratigraphic_column_depth)
    var _result_stratigraphic_column_depth = stratigraphic_column_depth(0.5, 0.5, 0.5)
    var _summary_stratigraphic_column_depth = _summary_float64(_result_stratigraphic_column_depth)
    print("MOJO_RESULT stratigraphy::stratigraphic_column_depth", _summary_stratigraphic_column_depth)
    var _acc_isotope_fractionation: Float64 = 0.0
    var _t0_isotope_fractionation = perf_counter_ns()
    for _ in range(N):
        _acc_isotope_fractionation += isotope_fractionation(0.5, 0.5)
    var _t1_isotope_fractionation = perf_counter_ns()
    var _ns_isotope_fractionation = Float64(_t1_isotope_fractionation - _t0_isotope_fractionation) / Float64(N)
    print("MOJO_TIMING stratigraphy::isotope_fractionation", _ns_isotope_fractionation, _acc_isotope_fractionation)
    var _result_isotope_fractionation = isotope_fractionation(0.5, 0.5)
    var _summary_isotope_fractionation = _summary_float64(_result_isotope_fractionation)
    print("MOJO_RESULT stratigraphy::isotope_fractionation", _summary_isotope_fractionation)
    var _acc_unconformity_gap: Float64 = 0.0
    var _t0_unconformity_gap = perf_counter_ns()
    for _ in range(N):
        _acc_unconformity_gap += unconformity_gap(0.5, 0.5)
    var _t1_unconformity_gap = perf_counter_ns()
    var _ns_unconformity_gap = Float64(_t1_unconformity_gap - _t0_unconformity_gap) / Float64(N)
    print("MOJO_TIMING stratigraphy::unconformity_gap", _ns_unconformity_gap, _acc_unconformity_gap)
    var _result_unconformity_gap = unconformity_gap(0.5, 0.5)
    var _summary_unconformity_gap = _summary_float64(_result_unconformity_gap)
    print("MOJO_RESULT stratigraphy::unconformity_gap", _summary_unconformity_gap)
    var _acc_thermal_maturity_vitrinite: Float64 = 0.0
    var _t0_thermal_maturity_vitrinite = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_maturity_vitrinite += thermal_maturity_vitrinite(0.5, 0.5)
    var _t1_thermal_maturity_vitrinite = perf_counter_ns()
    var _ns_thermal_maturity_vitrinite = Float64(_t1_thermal_maturity_vitrinite - _t0_thermal_maturity_vitrinite) / Float64(N)
    print("MOJO_TIMING stratigraphy::thermal_maturity_vitrinite", _ns_thermal_maturity_vitrinite, _acc_thermal_maturity_vitrinite)
    var _result_thermal_maturity_vitrinite = thermal_maturity_vitrinite(0.5, 0.5)
    var _summary_thermal_maturity_vitrinite = _summary_float64(_result_thermal_maturity_vitrinite)
    print("MOJO_RESULT stratigraphy::thermal_maturity_vitrinite", _summary_thermal_maturity_vitrinite)
    var _acc_compaction_correction: Float64 = 0.0
    var _t0_compaction_correction = perf_counter_ns()
    for _ in range(N):
        _acc_compaction_correction += compaction_correction(0.5, 0.5, 0.5)
    var _t1_compaction_correction = perf_counter_ns()
    var _ns_compaction_correction = Float64(_t1_compaction_correction - _t0_compaction_correction) / Float64(N)
    print("MOJO_TIMING stratigraphy::compaction_correction", _ns_compaction_correction, _acc_compaction_correction)
    var _result_compaction_correction = compaction_correction(0.5, 0.5, 0.5)
    var _summary_compaction_correction = _summary_float64(_result_compaction_correction)
    print("MOJO_RESULT stratigraphy::compaction_correction", _summary_compaction_correction)
    var _acc_sea_level_proxy: Float64 = 0.0
    var _t0_sea_level_proxy = perf_counter_ns()
    for _ in range(N):
        _acc_sea_level_proxy += sea_level_proxy(0.5, 0.5, 0.5)
    var _t1_sea_level_proxy = perf_counter_ns()
    var _ns_sea_level_proxy = Float64(_t1_sea_level_proxy - _t0_sea_level_proxy) / Float64(N)
    print("MOJO_TIMING stratigraphy::sea_level_proxy", _ns_sea_level_proxy, _acc_sea_level_proxy)
    var _result_sea_level_proxy = sea_level_proxy(0.5, 0.5, 0.5)
    var _summary_sea_level_proxy = _summary_float64(_result_sea_level_proxy)
    print("MOJO_RESULT stratigraphy::sea_level_proxy", _summary_sea_level_proxy)
