"""bench_seismology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from seismology import richter_magnitude, moment_magnitude, seismic_moment, energy_from_magnitude, peak_ground_acceleration, travel_time_p_wave, travel_time_s_wave, ts_tp_difference, epicenter_distance_from_ts_tp, intensity_mmi_from_pga, gutenberg_richter_rate, recurrence_interval
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

    var _acc_richter_magnitude: Float64 = 0.0
    var _t0_richter_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_richter_magnitude += richter_magnitude(0.5, 0.5)
    var _t1_richter_magnitude = perf_counter_ns()
    var _ns_richter_magnitude = Float64(_t1_richter_magnitude - _t0_richter_magnitude) / Float64(N)
    print("MOJO_TIMING seismology::richter_magnitude", _ns_richter_magnitude, _acc_richter_magnitude)
    var _result_richter_magnitude = richter_magnitude(0.5, 0.5)
    var _summary_richter_magnitude = _summary_float64(_result_richter_magnitude)
    print("MOJO_RESULT seismology::richter_magnitude", _summary_richter_magnitude)
    var _acc_moment_magnitude: Float64 = 0.0
    var _t0_moment_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_moment_magnitude += moment_magnitude(0.5)
    var _t1_moment_magnitude = perf_counter_ns()
    var _ns_moment_magnitude = Float64(_t1_moment_magnitude - _t0_moment_magnitude) / Float64(N)
    print("MOJO_TIMING seismology::moment_magnitude", _ns_moment_magnitude, _acc_moment_magnitude)
    var _result_moment_magnitude = moment_magnitude(0.5)
    var _summary_moment_magnitude = _summary_float64(_result_moment_magnitude)
    print("MOJO_RESULT seismology::moment_magnitude", _summary_moment_magnitude)
    var _acc_seismic_moment: Float64 = 0.0
    var _t0_seismic_moment = perf_counter_ns()
    for _ in range(N):
        _acc_seismic_moment += seismic_moment(0.5)
    var _t1_seismic_moment = perf_counter_ns()
    var _ns_seismic_moment = Float64(_t1_seismic_moment - _t0_seismic_moment) / Float64(N)
    print("MOJO_TIMING seismology::seismic_moment", _ns_seismic_moment, _acc_seismic_moment)
    var _result_seismic_moment = seismic_moment(0.5)
    var _summary_seismic_moment = _summary_float64(_result_seismic_moment)
    print("MOJO_RESULT seismology::seismic_moment", _summary_seismic_moment)
    var _acc_energy_from_magnitude: Float64 = 0.0
    var _t0_energy_from_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_energy_from_magnitude += energy_from_magnitude(0.5)
    var _t1_energy_from_magnitude = perf_counter_ns()
    var _ns_energy_from_magnitude = Float64(_t1_energy_from_magnitude - _t0_energy_from_magnitude) / Float64(N)
    print("MOJO_TIMING seismology::energy_from_magnitude", _ns_energy_from_magnitude, _acc_energy_from_magnitude)
    var _result_energy_from_magnitude = energy_from_magnitude(0.5)
    var _summary_energy_from_magnitude = _summary_float64(_result_energy_from_magnitude)
    print("MOJO_RESULT seismology::energy_from_magnitude", _summary_energy_from_magnitude)
    var _acc_peak_ground_acceleration: Float64 = 0.0
    var _t0_peak_ground_acceleration = perf_counter_ns()
    for _ in range(N):
        _acc_peak_ground_acceleration += peak_ground_acceleration(0.5, 0.5, 0.5)
    var _t1_peak_ground_acceleration = perf_counter_ns()
    var _ns_peak_ground_acceleration = Float64(_t1_peak_ground_acceleration - _t0_peak_ground_acceleration) / Float64(N)
    print("MOJO_TIMING seismology::peak_ground_acceleration", _ns_peak_ground_acceleration, _acc_peak_ground_acceleration)
    var _result_peak_ground_acceleration = peak_ground_acceleration(0.5, 0.5, 0.5)
    var _summary_peak_ground_acceleration = _summary_float64(_result_peak_ground_acceleration)
    print("MOJO_RESULT seismology::peak_ground_acceleration", _summary_peak_ground_acceleration)
    var _acc_travel_time_p_wave: Float64 = 0.0
    var _t0_travel_time_p_wave = perf_counter_ns()
    for _ in range(N):
        _acc_travel_time_p_wave += travel_time_p_wave(0.5, 0.5)
    var _t1_travel_time_p_wave = perf_counter_ns()
    var _ns_travel_time_p_wave = Float64(_t1_travel_time_p_wave - _t0_travel_time_p_wave) / Float64(N)
    print("MOJO_TIMING seismology::travel_time_p_wave", _ns_travel_time_p_wave, _acc_travel_time_p_wave)
    var _result_travel_time_p_wave = travel_time_p_wave(0.5, 0.5)
    var _summary_travel_time_p_wave = _summary_float64(_result_travel_time_p_wave)
    print("MOJO_RESULT seismology::travel_time_p_wave", _summary_travel_time_p_wave)
    var _acc_travel_time_s_wave: Float64 = 0.0
    var _t0_travel_time_s_wave = perf_counter_ns()
    for _ in range(N):
        _acc_travel_time_s_wave += travel_time_s_wave(0.5, 0.5)
    var _t1_travel_time_s_wave = perf_counter_ns()
    var _ns_travel_time_s_wave = Float64(_t1_travel_time_s_wave - _t0_travel_time_s_wave) / Float64(N)
    print("MOJO_TIMING seismology::travel_time_s_wave", _ns_travel_time_s_wave, _acc_travel_time_s_wave)
    var _result_travel_time_s_wave = travel_time_s_wave(0.5, 0.5)
    var _summary_travel_time_s_wave = _summary_float64(_result_travel_time_s_wave)
    print("MOJO_RESULT seismology::travel_time_s_wave", _summary_travel_time_s_wave)
    var _acc_ts_tp_difference: Float64 = 0.0
    var _t0_ts_tp_difference = perf_counter_ns()
    for _ in range(N):
        _acc_ts_tp_difference += ts_tp_difference(0.5, 0.5, 0.5)
    var _t1_ts_tp_difference = perf_counter_ns()
    var _ns_ts_tp_difference = Float64(_t1_ts_tp_difference - _t0_ts_tp_difference) / Float64(N)
    print("MOJO_TIMING seismology::ts_tp_difference", _ns_ts_tp_difference, _acc_ts_tp_difference)
    var _result_ts_tp_difference = ts_tp_difference(0.5, 0.5, 0.5)
    var _summary_ts_tp_difference = _summary_float64(_result_ts_tp_difference)
    print("MOJO_RESULT seismology::ts_tp_difference", _summary_ts_tp_difference)
    var _acc_epicenter_distance_from_ts_tp: Float64 = 0.0
    var _t0_epicenter_distance_from_ts_tp = perf_counter_ns()
    for _ in range(N):
        _acc_epicenter_distance_from_ts_tp += epicenter_distance_from_ts_tp(2.0, 3.5, 6.0)
    var _t1_epicenter_distance_from_ts_tp = perf_counter_ns()
    var _ns_epicenter_distance_from_ts_tp = Float64(_t1_epicenter_distance_from_ts_tp - _t0_epicenter_distance_from_ts_tp) / Float64(N)
    print("MOJO_TIMING seismology::epicenter_distance_from_ts_tp", _ns_epicenter_distance_from_ts_tp, _acc_epicenter_distance_from_ts_tp)
    var _result_epicenter_distance_from_ts_tp = epicenter_distance_from_ts_tp(2.0, 3.5, 6.0)
    var _summary_epicenter_distance_from_ts_tp = _summary_float64(_result_epicenter_distance_from_ts_tp)
    print("MOJO_RESULT seismology::epicenter_distance_from_ts_tp", _summary_epicenter_distance_from_ts_tp)
    var _acc_intensity_mmi_from_pga: Float64 = 0.0
    var _t0_intensity_mmi_from_pga = perf_counter_ns()
    for _ in range(N):
        _acc_intensity_mmi_from_pga += intensity_mmi_from_pga(0.5)
    var _t1_intensity_mmi_from_pga = perf_counter_ns()
    var _ns_intensity_mmi_from_pga = Float64(_t1_intensity_mmi_from_pga - _t0_intensity_mmi_from_pga) / Float64(N)
    print("MOJO_TIMING seismology::intensity_mmi_from_pga", _ns_intensity_mmi_from_pga, _acc_intensity_mmi_from_pga)
    var _result_intensity_mmi_from_pga = intensity_mmi_from_pga(0.5)
    var _summary_intensity_mmi_from_pga = _summary_float64(_result_intensity_mmi_from_pga)
    print("MOJO_RESULT seismology::intensity_mmi_from_pga", _summary_intensity_mmi_from_pga)
    var _acc_gutenberg_richter_rate: Float64 = 0.0
    var _t0_gutenberg_richter_rate = perf_counter_ns()
    for _ in range(N):
        _acc_gutenberg_richter_rate += gutenberg_richter_rate(0.5, 0.5, 0.5)
    var _t1_gutenberg_richter_rate = perf_counter_ns()
    var _ns_gutenberg_richter_rate = Float64(_t1_gutenberg_richter_rate - _t0_gutenberg_richter_rate) / Float64(N)
    print("MOJO_TIMING seismology::gutenberg_richter_rate", _ns_gutenberg_richter_rate, _acc_gutenberg_richter_rate)
    var _result_gutenberg_richter_rate = gutenberg_richter_rate(0.5, 0.5, 0.5)
    var _summary_gutenberg_richter_rate = _summary_float64(_result_gutenberg_richter_rate)
    print("MOJO_RESULT seismology::gutenberg_richter_rate", _summary_gutenberg_richter_rate)
    var _acc_recurrence_interval: Float64 = 0.0
    var _t0_recurrence_interval = perf_counter_ns()
    for _ in range(N):
        _acc_recurrence_interval += recurrence_interval(0.5)
    var _t1_recurrence_interval = perf_counter_ns()
    var _ns_recurrence_interval = Float64(_t1_recurrence_interval - _t0_recurrence_interval) / Float64(N)
    print("MOJO_TIMING seismology::recurrence_interval", _ns_recurrence_interval, _acc_recurrence_interval)
    var _result_recurrence_interval = recurrence_interval(0.5)
    var _summary_recurrence_interval = _summary_float64(_result_recurrence_interval)
    print("MOJO_RESULT seismology::recurrence_interval", _summary_recurrence_interval)
