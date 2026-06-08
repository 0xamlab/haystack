"""bench_fisheries.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fisheries import catch_per_unit_effort, maximum_sustainable_yield, biomass_at_msy, schaefer_surplus_production, fishing_mortality, total_mortality, exploitation_rate, survival_rate, von_bertalanffy_length, condition_factor, gonadosomatic_index, stock_recruitment_bevholt
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

    var _acc_catch_per_unit_effort: Float64 = 0.0
    var _t0_catch_per_unit_effort = perf_counter_ns()
    for _ in range(N):
        _acc_catch_per_unit_effort += catch_per_unit_effort(0.5, 0.5)
    var _t1_catch_per_unit_effort = perf_counter_ns()
    var _ns_catch_per_unit_effort = Float64(_t1_catch_per_unit_effort - _t0_catch_per_unit_effort) / Float64(N)
    print("MOJO_TIMING fisheries::catch_per_unit_effort", _ns_catch_per_unit_effort, _acc_catch_per_unit_effort)
    var _result_catch_per_unit_effort = catch_per_unit_effort(0.5, 0.5)
    var _summary_catch_per_unit_effort = _summary_float64(_result_catch_per_unit_effort)
    print("MOJO_RESULT fisheries::catch_per_unit_effort", _summary_catch_per_unit_effort)
    var _acc_maximum_sustainable_yield: Float64 = 0.0
    var _t0_maximum_sustainable_yield = perf_counter_ns()
    for _ in range(N):
        _acc_maximum_sustainable_yield += maximum_sustainable_yield(0.5, 0.5)
    var _t1_maximum_sustainable_yield = perf_counter_ns()
    var _ns_maximum_sustainable_yield = Float64(_t1_maximum_sustainable_yield - _t0_maximum_sustainable_yield) / Float64(N)
    print("MOJO_TIMING fisheries::maximum_sustainable_yield", _ns_maximum_sustainable_yield, _acc_maximum_sustainable_yield)
    var _result_maximum_sustainable_yield = maximum_sustainable_yield(0.5, 0.5)
    var _summary_maximum_sustainable_yield = _summary_float64(_result_maximum_sustainable_yield)
    print("MOJO_RESULT fisheries::maximum_sustainable_yield", _summary_maximum_sustainable_yield)
    var _acc_biomass_at_msy: Float64 = 0.0
    var _t0_biomass_at_msy = perf_counter_ns()
    for _ in range(N):
        _acc_biomass_at_msy += biomass_at_msy(0.5)
    var _t1_biomass_at_msy = perf_counter_ns()
    var _ns_biomass_at_msy = Float64(_t1_biomass_at_msy - _t0_biomass_at_msy) / Float64(N)
    print("MOJO_TIMING fisheries::biomass_at_msy", _ns_biomass_at_msy, _acc_biomass_at_msy)
    var _result_biomass_at_msy = biomass_at_msy(0.5)
    var _summary_biomass_at_msy = _summary_float64(_result_biomass_at_msy)
    print("MOJO_RESULT fisheries::biomass_at_msy", _summary_biomass_at_msy)
    var _acc_schaefer_surplus_production: Float64 = 0.0
    var _t0_schaefer_surplus_production = perf_counter_ns()
    for _ in range(N):
        _acc_schaefer_surplus_production += schaefer_surplus_production(0.5, 0.5, 0.5)
    var _t1_schaefer_surplus_production = perf_counter_ns()
    var _ns_schaefer_surplus_production = Float64(_t1_schaefer_surplus_production - _t0_schaefer_surplus_production) / Float64(N)
    print("MOJO_TIMING fisheries::schaefer_surplus_production", _ns_schaefer_surplus_production, _acc_schaefer_surplus_production)
    var _result_schaefer_surplus_production = schaefer_surplus_production(0.5, 0.5, 0.5)
    var _summary_schaefer_surplus_production = _summary_float64(_result_schaefer_surplus_production)
    print("MOJO_RESULT fisheries::schaefer_surplus_production", _summary_schaefer_surplus_production)
    var _acc_fishing_mortality: Float64 = 0.0
    var _t0_fishing_mortality = perf_counter_ns()
    for _ in range(N):
        _acc_fishing_mortality += fishing_mortality(0.5, 0.5)
    var _t1_fishing_mortality = perf_counter_ns()
    var _ns_fishing_mortality = Float64(_t1_fishing_mortality - _t0_fishing_mortality) / Float64(N)
    print("MOJO_TIMING fisheries::fishing_mortality", _ns_fishing_mortality, _acc_fishing_mortality)
    var _result_fishing_mortality = fishing_mortality(0.5, 0.5)
    var _summary_fishing_mortality = _summary_float64(_result_fishing_mortality)
    print("MOJO_RESULT fisheries::fishing_mortality", _summary_fishing_mortality)
    var _acc_total_mortality: Float64 = 0.0
    var _t0_total_mortality = perf_counter_ns()
    for _ in range(N):
        _acc_total_mortality += total_mortality(0.5, 0.5)
    var _t1_total_mortality = perf_counter_ns()
    var _ns_total_mortality = Float64(_t1_total_mortality - _t0_total_mortality) / Float64(N)
    print("MOJO_TIMING fisheries::total_mortality", _ns_total_mortality, _acc_total_mortality)
    var _result_total_mortality = total_mortality(0.5, 0.5)
    var _summary_total_mortality = _summary_float64(_result_total_mortality)
    print("MOJO_RESULT fisheries::total_mortality", _summary_total_mortality)
    var _acc_exploitation_rate: Float64 = 0.0
    var _t0_exploitation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_exploitation_rate += exploitation_rate(0.5, 0.5)
    var _t1_exploitation_rate = perf_counter_ns()
    var _ns_exploitation_rate = Float64(_t1_exploitation_rate - _t0_exploitation_rate) / Float64(N)
    print("MOJO_TIMING fisheries::exploitation_rate", _ns_exploitation_rate, _acc_exploitation_rate)
    var _result_exploitation_rate = exploitation_rate(0.5, 0.5)
    var _summary_exploitation_rate = _summary_float64(_result_exploitation_rate)
    print("MOJO_RESULT fisheries::exploitation_rate", _summary_exploitation_rate)
    var _acc_survival_rate: Float64 = 0.0
    var _t0_survival_rate = perf_counter_ns()
    for _ in range(N):
        _acc_survival_rate += survival_rate(0.5)
    var _t1_survival_rate = perf_counter_ns()
    var _ns_survival_rate = Float64(_t1_survival_rate - _t0_survival_rate) / Float64(N)
    print("MOJO_TIMING fisheries::survival_rate", _ns_survival_rate, _acc_survival_rate)
    var _result_survival_rate = survival_rate(0.5)
    var _summary_survival_rate = _summary_float64(_result_survival_rate)
    print("MOJO_RESULT fisheries::survival_rate", _summary_survival_rate)
    var _acc_von_bertalanffy_length: Float64 = 0.0
    var _t0_von_bertalanffy_length = perf_counter_ns()
    for _ in range(N):
        _acc_von_bertalanffy_length += von_bertalanffy_length(0.5, 0.5, 0.5, 0.5)
    var _t1_von_bertalanffy_length = perf_counter_ns()
    var _ns_von_bertalanffy_length = Float64(_t1_von_bertalanffy_length - _t0_von_bertalanffy_length) / Float64(N)
    print("MOJO_TIMING fisheries::von_bertalanffy_length", _ns_von_bertalanffy_length, _acc_von_bertalanffy_length)
    var _result_von_bertalanffy_length = von_bertalanffy_length(0.5, 0.5, 0.5, 0.5)
    var _summary_von_bertalanffy_length = _summary_float64(_result_von_bertalanffy_length)
    print("MOJO_RESULT fisheries::von_bertalanffy_length", _summary_von_bertalanffy_length)
    var _acc_condition_factor: Float64 = 0.0
    var _t0_condition_factor = perf_counter_ns()
    for _ in range(N):
        _acc_condition_factor += condition_factor(0.5, 0.5)
    var _t1_condition_factor = perf_counter_ns()
    var _ns_condition_factor = Float64(_t1_condition_factor - _t0_condition_factor) / Float64(N)
    print("MOJO_TIMING fisheries::condition_factor", _ns_condition_factor, _acc_condition_factor)
    var _result_condition_factor = condition_factor(0.5, 0.5)
    var _summary_condition_factor = _summary_float64(_result_condition_factor)
    print("MOJO_RESULT fisheries::condition_factor", _summary_condition_factor)
    var _acc_gonadosomatic_index: Float64 = 0.0
    var _t0_gonadosomatic_index = perf_counter_ns()
    for _ in range(N):
        _acc_gonadosomatic_index += gonadosomatic_index(0.5, 0.5)
    var _t1_gonadosomatic_index = perf_counter_ns()
    var _ns_gonadosomatic_index = Float64(_t1_gonadosomatic_index - _t0_gonadosomatic_index) / Float64(N)
    print("MOJO_TIMING fisheries::gonadosomatic_index", _ns_gonadosomatic_index, _acc_gonadosomatic_index)
    var _result_gonadosomatic_index = gonadosomatic_index(0.5, 0.5)
    var _summary_gonadosomatic_index = _summary_float64(_result_gonadosomatic_index)
    print("MOJO_RESULT fisheries::gonadosomatic_index", _summary_gonadosomatic_index)
    var _acc_stock_recruitment_bevholt: Float64 = 0.0
    var _t0_stock_recruitment_bevholt = perf_counter_ns()
    for _ in range(N):
        _acc_stock_recruitment_bevholt += stock_recruitment_bevholt(0.5, 0.5, 0.5)
    var _t1_stock_recruitment_bevholt = perf_counter_ns()
    var _ns_stock_recruitment_bevholt = Float64(_t1_stock_recruitment_bevholt - _t0_stock_recruitment_bevholt) / Float64(N)
    print("MOJO_TIMING fisheries::stock_recruitment_bevholt", _ns_stock_recruitment_bevholt, _acc_stock_recruitment_bevholt)
    var _result_stock_recruitment_bevholt = stock_recruitment_bevholt(0.5, 0.5, 0.5)
    var _summary_stock_recruitment_bevholt = _summary_float64(_result_stock_recruitment_bevholt)
    print("MOJO_RESULT fisheries::stock_recruitment_bevholt", _summary_stock_recruitment_bevholt)
