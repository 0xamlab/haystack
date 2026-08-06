"""bench_silviculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from silviculture import basal_area, stand_basal_area, site_index, volume_scribner, timber_yield_per_ha, relative_density_index, reineke_sdi, mean_annual_increment, current_annual_increment, thinning_ratio
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

    var _acc_basal_area: Float64 = 0.0
    var _t0_basal_area = perf_counter_ns()
    for _ in range(N):
        _acc_basal_area += basal_area(0.5)
    var _t1_basal_area = perf_counter_ns()
    var _ns_basal_area = Float64(_t1_basal_area - _t0_basal_area) / Float64(N)
    print("MOJO_TIMING silviculture::basal_area", _ns_basal_area, _acc_basal_area)
    var _result_basal_area = basal_area(0.5)
    var _summary_basal_area = _summary_float64(_result_basal_area)
    print("MOJO_RESULT silviculture::basal_area", _summary_basal_area)
    var _acc_stand_basal_area: Float64 = 0.0
    var _t0_stand_basal_area = perf_counter_ns()
    for _ in range(N):
        _acc_stand_basal_area += stand_basal_area(0.5, 0.5)
    var _t1_stand_basal_area = perf_counter_ns()
    var _ns_stand_basal_area = Float64(_t1_stand_basal_area - _t0_stand_basal_area) / Float64(N)
    print("MOJO_TIMING silviculture::stand_basal_area", _ns_stand_basal_area, _acc_stand_basal_area)
    var _result_stand_basal_area = stand_basal_area(0.5, 0.5)
    var _summary_stand_basal_area = _summary_float64(_result_stand_basal_area)
    print("MOJO_RESULT silviculture::stand_basal_area", _summary_stand_basal_area)
    var _acc_site_index: Float64 = 0.0
    var _t0_site_index = perf_counter_ns()
    for _ in range(N):
        _acc_site_index += site_index(0.5, 0.5, 0.5)
    var _t1_site_index = perf_counter_ns()
    var _ns_site_index = Float64(_t1_site_index - _t0_site_index) / Float64(N)
    print("MOJO_TIMING silviculture::site_index", _ns_site_index, _acc_site_index)
    var _result_site_index = site_index(0.5, 0.5, 0.5)
    var _summary_site_index = _summary_float64(_result_site_index)
    print("MOJO_RESULT silviculture::site_index", _summary_site_index)
    var _acc_volume_scribner: Float64 = 0.0
    var _t0_volume_scribner = perf_counter_ns()
    for _ in range(N):
        _acc_volume_scribner += volume_scribner(0.5, 0.5)
    var _t1_volume_scribner = perf_counter_ns()
    var _ns_volume_scribner = Float64(_t1_volume_scribner - _t0_volume_scribner) / Float64(N)
    print("MOJO_TIMING silviculture::volume_scribner", _ns_volume_scribner, _acc_volume_scribner)
    var _result_volume_scribner = volume_scribner(0.5, 0.5)
    var _summary_volume_scribner = _summary_float64(_result_volume_scribner)
    print("MOJO_RESULT silviculture::volume_scribner", _summary_volume_scribner)
    var _acc_timber_yield_per_ha: Float64 = 0.0
    var _t0_timber_yield_per_ha = perf_counter_ns()
    for _ in range(N):
        _acc_timber_yield_per_ha += timber_yield_per_ha(0.5, 0.5)
    var _t1_timber_yield_per_ha = perf_counter_ns()
    var _ns_timber_yield_per_ha = Float64(_t1_timber_yield_per_ha - _t0_timber_yield_per_ha) / Float64(N)
    print("MOJO_TIMING silviculture::timber_yield_per_ha", _ns_timber_yield_per_ha, _acc_timber_yield_per_ha)
    var _result_timber_yield_per_ha = timber_yield_per_ha(0.5, 0.5)
    var _summary_timber_yield_per_ha = _summary_float64(_result_timber_yield_per_ha)
    print("MOJO_RESULT silviculture::timber_yield_per_ha", _summary_timber_yield_per_ha)
    var _acc_relative_density_index: Float64 = 0.0
    var _t0_relative_density_index = perf_counter_ns()
    for _ in range(N):
        _acc_relative_density_index += relative_density_index(0.5, 0.5)
    var _t1_relative_density_index = perf_counter_ns()
    var _ns_relative_density_index = Float64(_t1_relative_density_index - _t0_relative_density_index) / Float64(N)
    print("MOJO_TIMING silviculture::relative_density_index", _ns_relative_density_index, _acc_relative_density_index)
    var _result_relative_density_index = relative_density_index(0.5, 0.5)
    var _summary_relative_density_index = _summary_float64(_result_relative_density_index)
    print("MOJO_RESULT silviculture::relative_density_index", _summary_relative_density_index)
    var _acc_reineke_sdi: Float64 = 0.0
    var _t0_reineke_sdi = perf_counter_ns()
    for _ in range(N):
        _acc_reineke_sdi += reineke_sdi(0.5, 0.5)
    var _t1_reineke_sdi = perf_counter_ns()
    var _ns_reineke_sdi = Float64(_t1_reineke_sdi - _t0_reineke_sdi) / Float64(N)
    print("MOJO_TIMING silviculture::reineke_sdi", _ns_reineke_sdi, _acc_reineke_sdi)
    var _result_reineke_sdi = reineke_sdi(0.5, 0.5)
    var _summary_reineke_sdi = _summary_float64(_result_reineke_sdi)
    print("MOJO_RESULT silviculture::reineke_sdi", _summary_reineke_sdi)
    var _acc_mean_annual_increment: Float64 = 0.0
    var _t0_mean_annual_increment = perf_counter_ns()
    for _ in range(N):
        _acc_mean_annual_increment += mean_annual_increment(0.5, 0.5)
    var _t1_mean_annual_increment = perf_counter_ns()
    var _ns_mean_annual_increment = Float64(_t1_mean_annual_increment - _t0_mean_annual_increment) / Float64(N)
    print("MOJO_TIMING silviculture::mean_annual_increment", _ns_mean_annual_increment, _acc_mean_annual_increment)
    var _result_mean_annual_increment = mean_annual_increment(0.5, 0.5)
    var _summary_mean_annual_increment = _summary_float64(_result_mean_annual_increment)
    print("MOJO_RESULT silviculture::mean_annual_increment", _summary_mean_annual_increment)
    var _acc_current_annual_increment: Float64 = 0.0
    var _t0_current_annual_increment = perf_counter_ns()
    for _ in range(N):
        _acc_current_annual_increment += current_annual_increment(0.5, 0.5, 0.5)
    var _t1_current_annual_increment = perf_counter_ns()
    var _ns_current_annual_increment = Float64(_t1_current_annual_increment - _t0_current_annual_increment) / Float64(N)
    print("MOJO_TIMING silviculture::current_annual_increment", _ns_current_annual_increment, _acc_current_annual_increment)
    var _result_current_annual_increment = current_annual_increment(0.5, 0.5, 0.5)
    var _summary_current_annual_increment = _summary_float64(_result_current_annual_increment)
    print("MOJO_RESULT silviculture::current_annual_increment", _summary_current_annual_increment)
    var _acc_thinning_ratio: Float64 = 0.0
    var _t0_thinning_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_thinning_ratio += thinning_ratio(0.5, 0.5)
    var _t1_thinning_ratio = perf_counter_ns()
    var _ns_thinning_ratio = Float64(_t1_thinning_ratio - _t0_thinning_ratio) / Float64(N)
    print("MOJO_TIMING silviculture::thinning_ratio", _ns_thinning_ratio, _acc_thinning_ratio)
    var _result_thinning_ratio = thinning_ratio(0.5, 0.5)
    var _summary_thinning_ratio = _summary_float64(_result_thinning_ratio)
    print("MOJO_RESULT silviculture::thinning_ratio", _summary_thinning_ratio)
