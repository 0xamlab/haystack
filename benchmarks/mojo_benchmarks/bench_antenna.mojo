"""bench_antenna.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from antenna import dipole_length, wavelength_from_freq, friis_path_loss, eirp, received_power, directivity_from_beamwidths, antenna_efficiency, effective_aperture, link_budget_margin, noise_figure_to_noise_temp, free_space_loss_db, beamwidth_from_aperture
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

    var _acc_dipole_length: Float64 = 0.0
    var _t0_dipole_length = perf_counter_ns()
    for _ in range(N):
        _acc_dipole_length += dipole_length(0.5)
    var _t1_dipole_length = perf_counter_ns()
    var _ns_dipole_length = Float64(_t1_dipole_length - _t0_dipole_length) / Float64(N)
    print("MOJO_TIMING antenna::dipole_length", _ns_dipole_length, _acc_dipole_length)
    var _result_dipole_length = dipole_length(0.5)
    var _summary_dipole_length = _summary_float64(_result_dipole_length)
    print("MOJO_RESULT antenna::dipole_length", _summary_dipole_length)
    var _acc_wavelength_from_freq: Float64 = 0.0
    var _t0_wavelength_from_freq = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_from_freq += wavelength_from_freq(0.5, 0.5)
    var _t1_wavelength_from_freq = perf_counter_ns()
    var _ns_wavelength_from_freq = Float64(_t1_wavelength_from_freq - _t0_wavelength_from_freq) / Float64(N)
    print("MOJO_TIMING antenna::wavelength_from_freq", _ns_wavelength_from_freq, _acc_wavelength_from_freq)
    var _result_wavelength_from_freq = wavelength_from_freq(0.5, 0.5)
    var _summary_wavelength_from_freq = _summary_float64(_result_wavelength_from_freq)
    print("MOJO_RESULT antenna::wavelength_from_freq", _summary_wavelength_from_freq)
    var _acc_friis_path_loss: Float64 = 0.0
    var _t0_friis_path_loss = perf_counter_ns()
    for _ in range(N):
        _acc_friis_path_loss += friis_path_loss(0.5, 0.5)
    var _t1_friis_path_loss = perf_counter_ns()
    var _ns_friis_path_loss = Float64(_t1_friis_path_loss - _t0_friis_path_loss) / Float64(N)
    print("MOJO_TIMING antenna::friis_path_loss", _ns_friis_path_loss, _acc_friis_path_loss)
    var _result_friis_path_loss = friis_path_loss(0.5, 0.5)
    var _summary_friis_path_loss = _summary_float64(_result_friis_path_loss)
    print("MOJO_RESULT antenna::friis_path_loss", _summary_friis_path_loss)
    var _acc_eirp: Float64 = 0.0
    var _t0_eirp = perf_counter_ns()
    for _ in range(N):
        _acc_eirp += eirp(0.5, 0.5)
    var _t1_eirp = perf_counter_ns()
    var _ns_eirp = Float64(_t1_eirp - _t0_eirp) / Float64(N)
    print("MOJO_TIMING antenna::eirp", _ns_eirp, _acc_eirp)
    var _result_eirp = eirp(0.5, 0.5)
    var _summary_eirp = _summary_float64(_result_eirp)
    print("MOJO_RESULT antenna::eirp", _summary_eirp)
    var _acc_received_power: Float64 = 0.0
    var _t0_received_power = perf_counter_ns()
    for _ in range(N):
        _acc_received_power += received_power(0.5, 0.5, 0.5)
    var _t1_received_power = perf_counter_ns()
    var _ns_received_power = Float64(_t1_received_power - _t0_received_power) / Float64(N)
    print("MOJO_TIMING antenna::received_power", _ns_received_power, _acc_received_power)
    var _result_received_power = received_power(0.5, 0.5, 0.5)
    var _summary_received_power = _summary_float64(_result_received_power)
    print("MOJO_RESULT antenna::received_power", _summary_received_power)
    var _acc_directivity_from_beamwidths: Float64 = 0.0
    var _t0_directivity_from_beamwidths = perf_counter_ns()
    for _ in range(N):
        _acc_directivity_from_beamwidths += directivity_from_beamwidths(0.5, 0.5)
    var _t1_directivity_from_beamwidths = perf_counter_ns()
    var _ns_directivity_from_beamwidths = Float64(_t1_directivity_from_beamwidths - _t0_directivity_from_beamwidths) / Float64(N)
    print("MOJO_TIMING antenna::directivity_from_beamwidths", _ns_directivity_from_beamwidths, _acc_directivity_from_beamwidths)
    var _result_directivity_from_beamwidths = directivity_from_beamwidths(0.5, 0.5)
    var _summary_directivity_from_beamwidths = _summary_float64(_result_directivity_from_beamwidths)
    print("MOJO_RESULT antenna::directivity_from_beamwidths", _summary_directivity_from_beamwidths)
    var _acc_antenna_efficiency: Float64 = 0.0
    var _t0_antenna_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_antenna_efficiency += antenna_efficiency(0.5, 0.5)
    var _t1_antenna_efficiency = perf_counter_ns()
    var _ns_antenna_efficiency = Float64(_t1_antenna_efficiency - _t0_antenna_efficiency) / Float64(N)
    print("MOJO_TIMING antenna::antenna_efficiency", _ns_antenna_efficiency, _acc_antenna_efficiency)
    var _result_antenna_efficiency = antenna_efficiency(0.5, 0.5)
    var _summary_antenna_efficiency = _summary_float64(_result_antenna_efficiency)
    print("MOJO_RESULT antenna::antenna_efficiency", _summary_antenna_efficiency)
    var _acc_effective_aperture: Float64 = 0.0
    var _t0_effective_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_effective_aperture += effective_aperture(0.5, 0.5)
    var _t1_effective_aperture = perf_counter_ns()
    var _ns_effective_aperture = Float64(_t1_effective_aperture - _t0_effective_aperture) / Float64(N)
    print("MOJO_TIMING antenna::effective_aperture", _ns_effective_aperture, _acc_effective_aperture)
    var _result_effective_aperture = effective_aperture(0.5, 0.5)
    var _summary_effective_aperture = _summary_float64(_result_effective_aperture)
    print("MOJO_RESULT antenna::effective_aperture", _summary_effective_aperture)
    var _acc_link_budget_margin: Float64 = 0.0
    var _t0_link_budget_margin = perf_counter_ns()
    for _ in range(N):
        _acc_link_budget_margin += link_budget_margin(0.5, 0.5)
    var _t1_link_budget_margin = perf_counter_ns()
    var _ns_link_budget_margin = Float64(_t1_link_budget_margin - _t0_link_budget_margin) / Float64(N)
    print("MOJO_TIMING antenna::link_budget_margin", _ns_link_budget_margin, _acc_link_budget_margin)
    var _result_link_budget_margin = link_budget_margin(0.5, 0.5)
    var _summary_link_budget_margin = _summary_float64(_result_link_budget_margin)
    print("MOJO_RESULT antenna::link_budget_margin", _summary_link_budget_margin)
    var _acc_noise_figure_to_noise_temp: Float64 = 0.0
    var _t0_noise_figure_to_noise_temp = perf_counter_ns()
    for _ in range(N):
        _acc_noise_figure_to_noise_temp += noise_figure_to_noise_temp(0.5, 0.5)
    var _t1_noise_figure_to_noise_temp = perf_counter_ns()
    var _ns_noise_figure_to_noise_temp = Float64(_t1_noise_figure_to_noise_temp - _t0_noise_figure_to_noise_temp) / Float64(N)
    print("MOJO_TIMING antenna::noise_figure_to_noise_temp", _ns_noise_figure_to_noise_temp, _acc_noise_figure_to_noise_temp)
    var _result_noise_figure_to_noise_temp = noise_figure_to_noise_temp(0.5, 0.5)
    var _summary_noise_figure_to_noise_temp = _summary_float64(_result_noise_figure_to_noise_temp)
    print("MOJO_RESULT antenna::noise_figure_to_noise_temp", _summary_noise_figure_to_noise_temp)
    var _acc_free_space_loss_db: Float64 = 0.0
    var _t0_free_space_loss_db = perf_counter_ns()
    for _ in range(N):
        _acc_free_space_loss_db += free_space_loss_db(0.5, 0.5)
    var _t1_free_space_loss_db = perf_counter_ns()
    var _ns_free_space_loss_db = Float64(_t1_free_space_loss_db - _t0_free_space_loss_db) / Float64(N)
    print("MOJO_TIMING antenna::free_space_loss_db", _ns_free_space_loss_db, _acc_free_space_loss_db)
    var _result_free_space_loss_db = free_space_loss_db(0.5, 0.5)
    var _summary_free_space_loss_db = _summary_float64(_result_free_space_loss_db)
    print("MOJO_RESULT antenna::free_space_loss_db", _summary_free_space_loss_db)
    var _acc_beamwidth_from_aperture: Float64 = 0.0
    var _t0_beamwidth_from_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_beamwidth_from_aperture += beamwidth_from_aperture(0.5, 0.5)
    var _t1_beamwidth_from_aperture = perf_counter_ns()
    var _ns_beamwidth_from_aperture = Float64(_t1_beamwidth_from_aperture - _t0_beamwidth_from_aperture) / Float64(N)
    print("MOJO_TIMING antenna::beamwidth_from_aperture", _ns_beamwidth_from_aperture, _acc_beamwidth_from_aperture)
    var _result_beamwidth_from_aperture = beamwidth_from_aperture(0.5, 0.5)
    var _summary_beamwidth_from_aperture = _summary_float64(_result_beamwidth_from_aperture)
    print("MOJO_RESULT antenna::beamwidth_from_aperture", _summary_beamwidth_from_aperture)
