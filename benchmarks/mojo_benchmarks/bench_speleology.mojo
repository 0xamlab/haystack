"""bench_speleology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from speleology import cave_passage_volume, stalactite_growth_rate, drip_water_calcite_saturation, cave_climate_temperature, turbulent_flow_cave, karst_spring_discharge, cave_radio_signal_depth, dissolution_rate_limestone, age_uranium_series, radon_in_cave_air
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

    var _acc_cave_passage_volume: Float64 = 0.0
    var _t0_cave_passage_volume = perf_counter_ns()
    for _ in range(N):
        _acc_cave_passage_volume += cave_passage_volume(0.5, 0.5, 0.5)
    var _t1_cave_passage_volume = perf_counter_ns()
    var _ns_cave_passage_volume = Float64(_t1_cave_passage_volume - _t0_cave_passage_volume) / Float64(N)
    print("MOJO_TIMING speleology::cave_passage_volume", _ns_cave_passage_volume, _acc_cave_passage_volume)
    var _acc_stalactite_growth_rate: Float64 = 0.0
    var _t0_stalactite_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_stalactite_growth_rate += stalactite_growth_rate(0.5, 0.5, 0.5)
    var _t1_stalactite_growth_rate = perf_counter_ns()
    var _ns_stalactite_growth_rate = Float64(_t1_stalactite_growth_rate - _t0_stalactite_growth_rate) / Float64(N)
    print("MOJO_TIMING speleology::stalactite_growth_rate", _ns_stalactite_growth_rate, _acc_stalactite_growth_rate)
    var _acc_drip_water_calcite_saturation: Float64 = 0.0
    var _t0_drip_water_calcite_saturation = perf_counter_ns()
    for _ in range(N):
        _acc_drip_water_calcite_saturation += drip_water_calcite_saturation(0.5, 0.5, 0.5)
    var _t1_drip_water_calcite_saturation = perf_counter_ns()
    var _ns_drip_water_calcite_saturation = Float64(_t1_drip_water_calcite_saturation - _t0_drip_water_calcite_saturation) / Float64(N)
    print("MOJO_TIMING speleology::drip_water_calcite_saturation", _ns_drip_water_calcite_saturation, _acc_drip_water_calcite_saturation)
    var _acc_cave_climate_temperature: Float64 = 0.0
    var _t0_cave_climate_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_cave_climate_temperature += cave_climate_temperature(0.5, 0.5, 0.5)
    var _t1_cave_climate_temperature = perf_counter_ns()
    var _ns_cave_climate_temperature = Float64(_t1_cave_climate_temperature - _t0_cave_climate_temperature) / Float64(N)
    print("MOJO_TIMING speleology::cave_climate_temperature", _ns_cave_climate_temperature, _acc_cave_climate_temperature)
    var _acc_turbulent_flow_cave: Float64 = 0.0
    var _t0_turbulent_flow_cave = perf_counter_ns()
    for _ in range(N):
        _acc_turbulent_flow_cave += turbulent_flow_cave(0.5, 0.5, 0.5)
    var _t1_turbulent_flow_cave = perf_counter_ns()
    var _ns_turbulent_flow_cave = Float64(_t1_turbulent_flow_cave - _t0_turbulent_flow_cave) / Float64(N)
    print("MOJO_TIMING speleology::turbulent_flow_cave", _ns_turbulent_flow_cave, _acc_turbulent_flow_cave)
    var _acc_karst_spring_discharge: Float64 = 0.0
    var _t0_karst_spring_discharge = perf_counter_ns()
    for _ in range(N):
        _acc_karst_spring_discharge += karst_spring_discharge(0.5, 0.5)
    var _t1_karst_spring_discharge = perf_counter_ns()
    var _ns_karst_spring_discharge = Float64(_t1_karst_spring_discharge - _t0_karst_spring_discharge) / Float64(N)
    print("MOJO_TIMING speleology::karst_spring_discharge", _ns_karst_spring_discharge, _acc_karst_spring_discharge)
    var _acc_cave_radio_signal_depth: Float64 = 0.0
    var _t0_cave_radio_signal_depth = perf_counter_ns()
    for _ in range(N):
        _acc_cave_radio_signal_depth += cave_radio_signal_depth(0.5, 0.5)
    var _t1_cave_radio_signal_depth = perf_counter_ns()
    var _ns_cave_radio_signal_depth = Float64(_t1_cave_radio_signal_depth - _t0_cave_radio_signal_depth) / Float64(N)
    print("MOJO_TIMING speleology::cave_radio_signal_depth", _ns_cave_radio_signal_depth, _acc_cave_radio_signal_depth)
    var _acc_dissolution_rate_limestone: Float64 = 0.0
    var _t0_dissolution_rate_limestone = perf_counter_ns()
    for _ in range(N):
        _acc_dissolution_rate_limestone += dissolution_rate_limestone(0.5, 0.5)
    var _t1_dissolution_rate_limestone = perf_counter_ns()
    var _ns_dissolution_rate_limestone = Float64(_t1_dissolution_rate_limestone - _t0_dissolution_rate_limestone) / Float64(N)
    print("MOJO_TIMING speleology::dissolution_rate_limestone", _ns_dissolution_rate_limestone, _acc_dissolution_rate_limestone)
    var _acc_age_uranium_series: Float64 = 0.0
    var _t0_age_uranium_series = perf_counter_ns()
    for _ in range(N):
        _acc_age_uranium_series += age_uranium_series(0.5)
    var _t1_age_uranium_series = perf_counter_ns()
    var _ns_age_uranium_series = Float64(_t1_age_uranium_series - _t0_age_uranium_series) / Float64(N)
    print("MOJO_TIMING speleology::age_uranium_series", _ns_age_uranium_series, _acc_age_uranium_series)
    var _acc_radon_in_cave_air: Float64 = 0.0
    var _t0_radon_in_cave_air = perf_counter_ns()
    for _ in range(N):
        _acc_radon_in_cave_air += radon_in_cave_air(0.5, 0.5, 0.5)
    var _t1_radon_in_cave_air = perf_counter_ns()
    var _ns_radon_in_cave_air = Float64(_t1_radon_in_cave_air - _t0_radon_in_cave_air) / Float64(N)
    print("MOJO_TIMING speleology::radon_in_cave_air", _ns_radon_in_cave_air, _acc_radon_in_cave_air)
