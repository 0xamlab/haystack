"""bench_fisheries.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fisheries import catch_per_unit_effort, maximum_sustainable_yield, biomass_at_msy, schaefer_surplus_production, fishing_mortality, total_mortality, exploitation_rate, survival_rate, von_bertalanffy_length, condition_factor, gonadosomatic_index, stock_recruitment_bevholt
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

    var _acc_catch_per_unit_effort: Float64 = 0.0
    var _t0_catch_per_unit_effort = perf_counter_ns()
    for _ in range(N):
        _acc_catch_per_unit_effort += catch_per_unit_effort(0.5, 0.5)
    var _t1_catch_per_unit_effort = perf_counter_ns()
    var _ns_catch_per_unit_effort = Float64(_t1_catch_per_unit_effort - _t0_catch_per_unit_effort) / Float64(N)
    print("MOJO_TIMING fisheries::catch_per_unit_effort", _ns_catch_per_unit_effort, _acc_catch_per_unit_effort)
    var _acc_maximum_sustainable_yield: Float64 = 0.0
    var _t0_maximum_sustainable_yield = perf_counter_ns()
    for _ in range(N):
        _acc_maximum_sustainable_yield += maximum_sustainable_yield(0.5, 0.5)
    var _t1_maximum_sustainable_yield = perf_counter_ns()
    var _ns_maximum_sustainable_yield = Float64(_t1_maximum_sustainable_yield - _t0_maximum_sustainable_yield) / Float64(N)
    print("MOJO_TIMING fisheries::maximum_sustainable_yield", _ns_maximum_sustainable_yield, _acc_maximum_sustainable_yield)
    var _acc_biomass_at_msy: Float64 = 0.0
    var _t0_biomass_at_msy = perf_counter_ns()
    for _ in range(N):
        _acc_biomass_at_msy += biomass_at_msy(0.5)
    var _t1_biomass_at_msy = perf_counter_ns()
    var _ns_biomass_at_msy = Float64(_t1_biomass_at_msy - _t0_biomass_at_msy) / Float64(N)
    print("MOJO_TIMING fisheries::biomass_at_msy", _ns_biomass_at_msy, _acc_biomass_at_msy)
    var _acc_schaefer_surplus_production: Float64 = 0.0
    var _t0_schaefer_surplus_production = perf_counter_ns()
    for _ in range(N):
        _acc_schaefer_surplus_production += schaefer_surplus_production(0.5, 0.5, 0.5)
    var _t1_schaefer_surplus_production = perf_counter_ns()
    var _ns_schaefer_surplus_production = Float64(_t1_schaefer_surplus_production - _t0_schaefer_surplus_production) / Float64(N)
    print("MOJO_TIMING fisheries::schaefer_surplus_production", _ns_schaefer_surplus_production, _acc_schaefer_surplus_production)
    var _acc_fishing_mortality: Float64 = 0.0
    var _t0_fishing_mortality = perf_counter_ns()
    for _ in range(N):
        _acc_fishing_mortality += fishing_mortality(0.5, 0.5)
    var _t1_fishing_mortality = perf_counter_ns()
    var _ns_fishing_mortality = Float64(_t1_fishing_mortality - _t0_fishing_mortality) / Float64(N)
    print("MOJO_TIMING fisheries::fishing_mortality", _ns_fishing_mortality, _acc_fishing_mortality)
    var _acc_total_mortality: Float64 = 0.0
    var _t0_total_mortality = perf_counter_ns()
    for _ in range(N):
        _acc_total_mortality += total_mortality(0.5, 0.5)
    var _t1_total_mortality = perf_counter_ns()
    var _ns_total_mortality = Float64(_t1_total_mortality - _t0_total_mortality) / Float64(N)
    print("MOJO_TIMING fisheries::total_mortality", _ns_total_mortality, _acc_total_mortality)
    var _acc_exploitation_rate: Float64 = 0.0
    var _t0_exploitation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_exploitation_rate += exploitation_rate(0.5, 0.5)
    var _t1_exploitation_rate = perf_counter_ns()
    var _ns_exploitation_rate = Float64(_t1_exploitation_rate - _t0_exploitation_rate) / Float64(N)
    print("MOJO_TIMING fisheries::exploitation_rate", _ns_exploitation_rate, _acc_exploitation_rate)
    var _acc_survival_rate: Float64 = 0.0
    var _t0_survival_rate = perf_counter_ns()
    for _ in range(N):
        _acc_survival_rate += survival_rate(0.5)
    var _t1_survival_rate = perf_counter_ns()
    var _ns_survival_rate = Float64(_t1_survival_rate - _t0_survival_rate) / Float64(N)
    print("MOJO_TIMING fisheries::survival_rate", _ns_survival_rate, _acc_survival_rate)
    var _acc_von_bertalanffy_length: Float64 = 0.0
    var _t0_von_bertalanffy_length = perf_counter_ns()
    for _ in range(N):
        _acc_von_bertalanffy_length += von_bertalanffy_length(0.5, 0.5, 0.5, 0.5)
    var _t1_von_bertalanffy_length = perf_counter_ns()
    var _ns_von_bertalanffy_length = Float64(_t1_von_bertalanffy_length - _t0_von_bertalanffy_length) / Float64(N)
    print("MOJO_TIMING fisheries::von_bertalanffy_length", _ns_von_bertalanffy_length, _acc_von_bertalanffy_length)
    var _acc_condition_factor: Float64 = 0.0
    var _t0_condition_factor = perf_counter_ns()
    for _ in range(N):
        _acc_condition_factor += condition_factor(0.5, 0.5)
    var _t1_condition_factor = perf_counter_ns()
    var _ns_condition_factor = Float64(_t1_condition_factor - _t0_condition_factor) / Float64(N)
    print("MOJO_TIMING fisheries::condition_factor", _ns_condition_factor, _acc_condition_factor)
    var _acc_gonadosomatic_index: Float64 = 0.0
    var _t0_gonadosomatic_index = perf_counter_ns()
    for _ in range(N):
        _acc_gonadosomatic_index += gonadosomatic_index(0.5, 0.5)
    var _t1_gonadosomatic_index = perf_counter_ns()
    var _ns_gonadosomatic_index = Float64(_t1_gonadosomatic_index - _t0_gonadosomatic_index) / Float64(N)
    print("MOJO_TIMING fisheries::gonadosomatic_index", _ns_gonadosomatic_index, _acc_gonadosomatic_index)
    var _acc_stock_recruitment_bevholt: Float64 = 0.0
    var _t0_stock_recruitment_bevholt = perf_counter_ns()
    for _ in range(N):
        _acc_stock_recruitment_bevholt += stock_recruitment_bevholt(0.5, 0.5, 0.5)
    var _t1_stock_recruitment_bevholt = perf_counter_ns()
    var _ns_stock_recruitment_bevholt = Float64(_t1_stock_recruitment_bevholt - _t0_stock_recruitment_bevholt) / Float64(N)
    print("MOJO_TIMING fisheries::stock_recruitment_bevholt", _ns_stock_recruitment_bevholt, _acc_stock_recruitment_bevholt)
