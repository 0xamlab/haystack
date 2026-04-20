"""bench_silviculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from silviculture import basal_area, stand_basal_area, site_index, volume_scribner, timber_yield_per_ha, relative_density_index, reineke_sdi, mean_annual_increment, current_annual_increment, thinning_ratio
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

    var _acc_basal_area: Float64 = 0.0
    var _t0_basal_area = perf_counter_ns()
    for _ in range(N):
        _acc_basal_area += basal_area(0.5)
    var _t1_basal_area = perf_counter_ns()
    var _ns_basal_area = Float64(_t1_basal_area - _t0_basal_area) / Float64(N)
    print("MOJO_TIMING silviculture::basal_area", _ns_basal_area, _acc_basal_area)
    var _acc_stand_basal_area: Float64 = 0.0
    var _t0_stand_basal_area = perf_counter_ns()
    for _ in range(N):
        _acc_stand_basal_area += stand_basal_area(0.5, 0.5)
    var _t1_stand_basal_area = perf_counter_ns()
    var _ns_stand_basal_area = Float64(_t1_stand_basal_area - _t0_stand_basal_area) / Float64(N)
    print("MOJO_TIMING silviculture::stand_basal_area", _ns_stand_basal_area, _acc_stand_basal_area)
    var _acc_site_index: Float64 = 0.0
    var _t0_site_index = perf_counter_ns()
    for _ in range(N):
        _acc_site_index += site_index(0.5, 0.5, 0.5)
    var _t1_site_index = perf_counter_ns()
    var _ns_site_index = Float64(_t1_site_index - _t0_site_index) / Float64(N)
    print("MOJO_TIMING silviculture::site_index", _ns_site_index, _acc_site_index)
    var _acc_volume_scribner: Float64 = 0.0
    var _t0_volume_scribner = perf_counter_ns()
    for _ in range(N):
        _acc_volume_scribner += volume_scribner(0.5, 0.5)
    var _t1_volume_scribner = perf_counter_ns()
    var _ns_volume_scribner = Float64(_t1_volume_scribner - _t0_volume_scribner) / Float64(N)
    print("MOJO_TIMING silviculture::volume_scribner", _ns_volume_scribner, _acc_volume_scribner)
    var _acc_timber_yield_per_ha: Float64 = 0.0
    var _t0_timber_yield_per_ha = perf_counter_ns()
    for _ in range(N):
        _acc_timber_yield_per_ha += timber_yield_per_ha(0.5, 0.5)
    var _t1_timber_yield_per_ha = perf_counter_ns()
    var _ns_timber_yield_per_ha = Float64(_t1_timber_yield_per_ha - _t0_timber_yield_per_ha) / Float64(N)
    print("MOJO_TIMING silviculture::timber_yield_per_ha", _ns_timber_yield_per_ha, _acc_timber_yield_per_ha)
    var _acc_relative_density_index: Float64 = 0.0
    var _t0_relative_density_index = perf_counter_ns()
    for _ in range(N):
        _acc_relative_density_index += relative_density_index(0.5, 0.5)
    var _t1_relative_density_index = perf_counter_ns()
    var _ns_relative_density_index = Float64(_t1_relative_density_index - _t0_relative_density_index) / Float64(N)
    print("MOJO_TIMING silviculture::relative_density_index", _ns_relative_density_index, _acc_relative_density_index)
    var _acc_reineke_sdi: Float64 = 0.0
    var _t0_reineke_sdi = perf_counter_ns()
    for _ in range(N):
        _acc_reineke_sdi += reineke_sdi(0.5, 0.5)
    var _t1_reineke_sdi = perf_counter_ns()
    var _ns_reineke_sdi = Float64(_t1_reineke_sdi - _t0_reineke_sdi) / Float64(N)
    print("MOJO_TIMING silviculture::reineke_sdi", _ns_reineke_sdi, _acc_reineke_sdi)
    var _acc_mean_annual_increment: Float64 = 0.0
    var _t0_mean_annual_increment = perf_counter_ns()
    for _ in range(N):
        _acc_mean_annual_increment += mean_annual_increment(0.5, 0.5)
    var _t1_mean_annual_increment = perf_counter_ns()
    var _ns_mean_annual_increment = Float64(_t1_mean_annual_increment - _t0_mean_annual_increment) / Float64(N)
    print("MOJO_TIMING silviculture::mean_annual_increment", _ns_mean_annual_increment, _acc_mean_annual_increment)
    var _acc_current_annual_increment: Float64 = 0.0
    var _t0_current_annual_increment = perf_counter_ns()
    for _ in range(N):
        _acc_current_annual_increment += current_annual_increment(0.5, 0.5, 0.5)
    var _t1_current_annual_increment = perf_counter_ns()
    var _ns_current_annual_increment = Float64(_t1_current_annual_increment - _t0_current_annual_increment) / Float64(N)
    print("MOJO_TIMING silviculture::current_annual_increment", _ns_current_annual_increment, _acc_current_annual_increment)
    var _acc_thinning_ratio: Float64 = 0.0
    var _t0_thinning_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_thinning_ratio += thinning_ratio(0.5, 0.5)
    var _t1_thinning_ratio = perf_counter_ns()
    var _ns_thinning_ratio = Float64(_t1_thinning_ratio - _t0_thinning_ratio) / Float64(N)
    print("MOJO_TIMING silviculture::thinning_ratio", _ns_thinning_ratio, _acc_thinning_ratio)
