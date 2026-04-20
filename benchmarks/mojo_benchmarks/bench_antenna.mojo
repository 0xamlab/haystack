"""bench_antenna.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from antenna import dipole_length, wavelength_from_freq, friis_path_loss, eirp, received_power, directivity_from_beamwidths, antenna_efficiency, effective_aperture, link_budget_margin, noise_figure_to_noise_temp, free_space_loss_db, beamwidth_from_aperture
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

    var _acc_dipole_length: Float64 = 0.0
    var _t0_dipole_length = perf_counter_ns()
    for _ in range(N):
        _acc_dipole_length += dipole_length(0.5)
    var _t1_dipole_length = perf_counter_ns()
    var _ns_dipole_length = Float64(_t1_dipole_length - _t0_dipole_length) / Float64(N)
    print("MOJO_TIMING antenna::dipole_length", _ns_dipole_length, _acc_dipole_length)
    var _acc_wavelength_from_freq: Float64 = 0.0
    var _t0_wavelength_from_freq = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_from_freq += wavelength_from_freq(0.5, 0.5)
    var _t1_wavelength_from_freq = perf_counter_ns()
    var _ns_wavelength_from_freq = Float64(_t1_wavelength_from_freq - _t0_wavelength_from_freq) / Float64(N)
    print("MOJO_TIMING antenna::wavelength_from_freq", _ns_wavelength_from_freq, _acc_wavelength_from_freq)
    var _acc_friis_path_loss: Float64 = 0.0
    var _t0_friis_path_loss = perf_counter_ns()
    for _ in range(N):
        _acc_friis_path_loss += friis_path_loss(0.5, 0.5)
    var _t1_friis_path_loss = perf_counter_ns()
    var _ns_friis_path_loss = Float64(_t1_friis_path_loss - _t0_friis_path_loss) / Float64(N)
    print("MOJO_TIMING antenna::friis_path_loss", _ns_friis_path_loss, _acc_friis_path_loss)
    var _acc_eirp: Float64 = 0.0
    var _t0_eirp = perf_counter_ns()
    for _ in range(N):
        _acc_eirp += eirp(0.5, 0.5)
    var _t1_eirp = perf_counter_ns()
    var _ns_eirp = Float64(_t1_eirp - _t0_eirp) / Float64(N)
    print("MOJO_TIMING antenna::eirp", _ns_eirp, _acc_eirp)
    var _acc_received_power: Float64 = 0.0
    var _t0_received_power = perf_counter_ns()
    for _ in range(N):
        _acc_received_power += received_power(0.5, 0.5, 0.5)
    var _t1_received_power = perf_counter_ns()
    var _ns_received_power = Float64(_t1_received_power - _t0_received_power) / Float64(N)
    print("MOJO_TIMING antenna::received_power", _ns_received_power, _acc_received_power)
    var _acc_directivity_from_beamwidths: Float64 = 0.0
    var _t0_directivity_from_beamwidths = perf_counter_ns()
    for _ in range(N):
        _acc_directivity_from_beamwidths += directivity_from_beamwidths(0.5, 0.5)
    var _t1_directivity_from_beamwidths = perf_counter_ns()
    var _ns_directivity_from_beamwidths = Float64(_t1_directivity_from_beamwidths - _t0_directivity_from_beamwidths) / Float64(N)
    print("MOJO_TIMING antenna::directivity_from_beamwidths", _ns_directivity_from_beamwidths, _acc_directivity_from_beamwidths)
    var _acc_antenna_efficiency: Float64 = 0.0
    var _t0_antenna_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_antenna_efficiency += antenna_efficiency(0.5, 0.5)
    var _t1_antenna_efficiency = perf_counter_ns()
    var _ns_antenna_efficiency = Float64(_t1_antenna_efficiency - _t0_antenna_efficiency) / Float64(N)
    print("MOJO_TIMING antenna::antenna_efficiency", _ns_antenna_efficiency, _acc_antenna_efficiency)
    var _acc_effective_aperture: Float64 = 0.0
    var _t0_effective_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_effective_aperture += effective_aperture(0.5, 0.5)
    var _t1_effective_aperture = perf_counter_ns()
    var _ns_effective_aperture = Float64(_t1_effective_aperture - _t0_effective_aperture) / Float64(N)
    print("MOJO_TIMING antenna::effective_aperture", _ns_effective_aperture, _acc_effective_aperture)
    var _acc_link_budget_margin: Float64 = 0.0
    var _t0_link_budget_margin = perf_counter_ns()
    for _ in range(N):
        _acc_link_budget_margin += link_budget_margin(0.5, 0.5)
    var _t1_link_budget_margin = perf_counter_ns()
    var _ns_link_budget_margin = Float64(_t1_link_budget_margin - _t0_link_budget_margin) / Float64(N)
    print("MOJO_TIMING antenna::link_budget_margin", _ns_link_budget_margin, _acc_link_budget_margin)
    var _acc_noise_figure_to_noise_temp: Float64 = 0.0
    var _t0_noise_figure_to_noise_temp = perf_counter_ns()
    for _ in range(N):
        _acc_noise_figure_to_noise_temp += noise_figure_to_noise_temp(0.5, 0.5)
    var _t1_noise_figure_to_noise_temp = perf_counter_ns()
    var _ns_noise_figure_to_noise_temp = Float64(_t1_noise_figure_to_noise_temp - _t0_noise_figure_to_noise_temp) / Float64(N)
    print("MOJO_TIMING antenna::noise_figure_to_noise_temp", _ns_noise_figure_to_noise_temp, _acc_noise_figure_to_noise_temp)
    var _acc_free_space_loss_db: Float64 = 0.0
    var _t0_free_space_loss_db = perf_counter_ns()
    for _ in range(N):
        _acc_free_space_loss_db += free_space_loss_db(0.5, 0.5)
    var _t1_free_space_loss_db = perf_counter_ns()
    var _ns_free_space_loss_db = Float64(_t1_free_space_loss_db - _t0_free_space_loss_db) / Float64(N)
    print("MOJO_TIMING antenna::free_space_loss_db", _ns_free_space_loss_db, _acc_free_space_loss_db)
    var _acc_beamwidth_from_aperture: Float64 = 0.0
    var _t0_beamwidth_from_aperture = perf_counter_ns()
    for _ in range(N):
        _acc_beamwidth_from_aperture += beamwidth_from_aperture(0.5, 0.5)
    var _t1_beamwidth_from_aperture = perf_counter_ns()
    var _ns_beamwidth_from_aperture = Float64(_t1_beamwidth_from_aperture - _t0_beamwidth_from_aperture) / Float64(N)
    print("MOJO_TIMING antenna::beamwidth_from_aperture", _ns_beamwidth_from_aperture, _acc_beamwidth_from_aperture)
