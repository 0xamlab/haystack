"""bench_atmospheric_chemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from atmospheric_chemistry import ozone_column_dobson, photolysis_rate, hydroxyl_steady_state, aerosol_optical_depth, mixing_ratio_to_conc, residence_time, smog_formation_index, acid_rain_ph, greenhouse_forcing, lifetime_from_oh
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

    var _acc_ozone_column_dobson: Float64 = 0.0
    var _t0_ozone_column_dobson = perf_counter_ns()
    for _ in range(N):
        _acc_ozone_column_dobson += ozone_column_dobson(0.5)
    var _t1_ozone_column_dobson = perf_counter_ns()
    var _ns_ozone_column_dobson = Float64(_t1_ozone_column_dobson - _t0_ozone_column_dobson) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::ozone_column_dobson", _ns_ozone_column_dobson, _acc_ozone_column_dobson)
    var _acc_photolysis_rate: Float64 = 0.0
    var _t0_photolysis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_photolysis_rate += photolysis_rate(0.5, 0.5, 0.5)
    var _t1_photolysis_rate = perf_counter_ns()
    var _ns_photolysis_rate = Float64(_t1_photolysis_rate - _t0_photolysis_rate) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::photolysis_rate", _ns_photolysis_rate, _acc_photolysis_rate)
    var _acc_hydroxyl_steady_state: Float64 = 0.0
    var _t0_hydroxyl_steady_state = perf_counter_ns()
    for _ in range(N):
        _acc_hydroxyl_steady_state += hydroxyl_steady_state(0.5, 0.5, 0.5)
    var _t1_hydroxyl_steady_state = perf_counter_ns()
    var _ns_hydroxyl_steady_state = Float64(_t1_hydroxyl_steady_state - _t0_hydroxyl_steady_state) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::hydroxyl_steady_state", _ns_hydroxyl_steady_state, _acc_hydroxyl_steady_state)
    var _acc_aerosol_optical_depth: Float64 = 0.0
    var _t0_aerosol_optical_depth = perf_counter_ns()
    for _ in range(N):
        _acc_aerosol_optical_depth += aerosol_optical_depth(0.5, 0.5)
    var _t1_aerosol_optical_depth = perf_counter_ns()
    var _ns_aerosol_optical_depth = Float64(_t1_aerosol_optical_depth - _t0_aerosol_optical_depth) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::aerosol_optical_depth", _ns_aerosol_optical_depth, _acc_aerosol_optical_depth)
    var _acc_mixing_ratio_to_conc: Float64 = 0.0
    var _t0_mixing_ratio_to_conc = perf_counter_ns()
    for _ in range(N):
        _acc_mixing_ratio_to_conc += mixing_ratio_to_conc(0.5, 0.5, 0.5)
    var _t1_mixing_ratio_to_conc = perf_counter_ns()
    var _ns_mixing_ratio_to_conc = Float64(_t1_mixing_ratio_to_conc - _t0_mixing_ratio_to_conc) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::mixing_ratio_to_conc", _ns_mixing_ratio_to_conc, _acc_mixing_ratio_to_conc)
    var _acc_residence_time: Float64 = 0.0
    var _t0_residence_time = perf_counter_ns()
    for _ in range(N):
        _acc_residence_time += residence_time(0.5, 0.5)
    var _t1_residence_time = perf_counter_ns()
    var _ns_residence_time = Float64(_t1_residence_time - _t0_residence_time) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::residence_time", _ns_residence_time, _acc_residence_time)
    var _acc_smog_formation_index: Float64 = 0.0
    var _t0_smog_formation_index = perf_counter_ns()
    for _ in range(N):
        _acc_smog_formation_index += smog_formation_index(0.5, 0.5)
    var _t1_smog_formation_index = perf_counter_ns()
    var _ns_smog_formation_index = Float64(_t1_smog_formation_index - _t0_smog_formation_index) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::smog_formation_index", _ns_smog_formation_index, _acc_smog_formation_index)
    var _acc_acid_rain_ph: Float64 = 0.0
    var _t0_acid_rain_ph = perf_counter_ns()
    for _ in range(N):
        _acc_acid_rain_ph += acid_rain_ph(0.5, 0.5)
    var _t1_acid_rain_ph = perf_counter_ns()
    var _ns_acid_rain_ph = Float64(_t1_acid_rain_ph - _t0_acid_rain_ph) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::acid_rain_ph", _ns_acid_rain_ph, _acc_acid_rain_ph)
    var _acc_greenhouse_forcing: Float64 = 0.0
    var _t0_greenhouse_forcing = perf_counter_ns()
    for _ in range(N):
        _acc_greenhouse_forcing += greenhouse_forcing(0.5, 0.5)
    var _t1_greenhouse_forcing = perf_counter_ns()
    var _ns_greenhouse_forcing = Float64(_t1_greenhouse_forcing - _t0_greenhouse_forcing) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::greenhouse_forcing", _ns_greenhouse_forcing, _acc_greenhouse_forcing)
    var _acc_lifetime_from_oh: Float64 = 0.0
    var _t0_lifetime_from_oh = perf_counter_ns()
    for _ in range(N):
        _acc_lifetime_from_oh += lifetime_from_oh(0.5, 0.5)
    var _t1_lifetime_from_oh = perf_counter_ns()
    var _ns_lifetime_from_oh = Float64(_t1_lifetime_from_oh - _t0_lifetime_from_oh) / Float64(N)
    print("MOJO_TIMING atmospheric_chemistry::lifetime_from_oh", _ns_lifetime_from_oh, _acc_lifetime_from_oh)
