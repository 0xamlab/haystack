"""bench_ecophysiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ecophysiology import metabolic_rate_kleiber, thermal_conductance, q10_temperature_coefficient, evaporative_water_loss, aerobic_scope, hypoxia_tolerance, osmoregulation_cost, heart_rate_fick, oxygen_consumption_rate, field_metabolic_rate
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

    var _acc_metabolic_rate_kleiber: Float64 = 0.0
    var _t0_metabolic_rate_kleiber = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_rate_kleiber += metabolic_rate_kleiber(0.5)
    var _t1_metabolic_rate_kleiber = perf_counter_ns()
    var _ns_metabolic_rate_kleiber = Float64(_t1_metabolic_rate_kleiber - _t0_metabolic_rate_kleiber) / Float64(N)
    print("MOJO_TIMING ecophysiology::metabolic_rate_kleiber", _ns_metabolic_rate_kleiber, _acc_metabolic_rate_kleiber)
    var _acc_thermal_conductance: Float64 = 0.0
    var _t0_thermal_conductance = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductance += thermal_conductance(0.5, 0.5, 0.5)
    var _t1_thermal_conductance = perf_counter_ns()
    var _ns_thermal_conductance = Float64(_t1_thermal_conductance - _t0_thermal_conductance) / Float64(N)
    print("MOJO_TIMING ecophysiology::thermal_conductance", _ns_thermal_conductance, _acc_thermal_conductance)
    var _acc_q10_temperature_coefficient: Float64 = 0.0
    var _t0_q10_temperature_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_q10_temperature_coefficient += q10_temperature_coefficient(0.5, 0.5, 0.5, 0.5)
    var _t1_q10_temperature_coefficient = perf_counter_ns()
    var _ns_q10_temperature_coefficient = Float64(_t1_q10_temperature_coefficient - _t0_q10_temperature_coefficient) / Float64(N)
    print("MOJO_TIMING ecophysiology::q10_temperature_coefficient", _ns_q10_temperature_coefficient, _acc_q10_temperature_coefficient)
    var _acc_evaporative_water_loss: Float64 = 0.0
    var _t0_evaporative_water_loss = perf_counter_ns()
    for _ in range(N):
        _acc_evaporative_water_loss += evaporative_water_loss(0.5, 0.5, 0.5)
    var _t1_evaporative_water_loss = perf_counter_ns()
    var _ns_evaporative_water_loss = Float64(_t1_evaporative_water_loss - _t0_evaporative_water_loss) / Float64(N)
    print("MOJO_TIMING ecophysiology::evaporative_water_loss", _ns_evaporative_water_loss, _acc_evaporative_water_loss)
    var _acc_aerobic_scope: Float64 = 0.0
    var _t0_aerobic_scope = perf_counter_ns()
    for _ in range(N):
        _acc_aerobic_scope += aerobic_scope(0.5, 0.5)
    var _t1_aerobic_scope = perf_counter_ns()
    var _ns_aerobic_scope = Float64(_t1_aerobic_scope - _t0_aerobic_scope) / Float64(N)
    print("MOJO_TIMING ecophysiology::aerobic_scope", _ns_aerobic_scope, _acc_aerobic_scope)
    var _acc_hypoxia_tolerance: Float64 = 0.0
    var _t0_hypoxia_tolerance = perf_counter_ns()
    for _ in range(N):
        _acc_hypoxia_tolerance += hypoxia_tolerance(0.5, 0.5)
    var _t1_hypoxia_tolerance = perf_counter_ns()
    var _ns_hypoxia_tolerance = Float64(_t1_hypoxia_tolerance - _t0_hypoxia_tolerance) / Float64(N)
    print("MOJO_TIMING ecophysiology::hypoxia_tolerance", _ns_hypoxia_tolerance, _acc_hypoxia_tolerance)
    var _acc_osmoregulation_cost: Float64 = 0.0
    var _t0_osmoregulation_cost = perf_counter_ns()
    for _ in range(N):
        _acc_osmoregulation_cost += osmoregulation_cost(0.5, 0.5, 0.5)
    var _t1_osmoregulation_cost = perf_counter_ns()
    var _ns_osmoregulation_cost = Float64(_t1_osmoregulation_cost - _t0_osmoregulation_cost) / Float64(N)
    print("MOJO_TIMING ecophysiology::osmoregulation_cost", _ns_osmoregulation_cost, _acc_osmoregulation_cost)
    var _acc_heart_rate_fick: Float64 = 0.0
    var _t0_heart_rate_fick = perf_counter_ns()
    for _ in range(N):
        _acc_heart_rate_fick += heart_rate_fick(0.5, 0.5, 0.5)
    var _t1_heart_rate_fick = perf_counter_ns()
    var _ns_heart_rate_fick = Float64(_t1_heart_rate_fick - _t0_heart_rate_fick) / Float64(N)
    print("MOJO_TIMING ecophysiology::heart_rate_fick", _ns_heart_rate_fick, _acc_heart_rate_fick)
    var _acc_oxygen_consumption_rate: Float64 = 0.0
    var _t0_oxygen_consumption_rate = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_consumption_rate += oxygen_consumption_rate(0.5, 0.5, 0.5)
    var _t1_oxygen_consumption_rate = perf_counter_ns()
    var _ns_oxygen_consumption_rate = Float64(_t1_oxygen_consumption_rate - _t0_oxygen_consumption_rate) / Float64(N)
    print("MOJO_TIMING ecophysiology::oxygen_consumption_rate", _ns_oxygen_consumption_rate, _acc_oxygen_consumption_rate)
    var _acc_field_metabolic_rate: Float64 = 0.0
    var _t0_field_metabolic_rate = perf_counter_ns()
    for _ in range(N):
        _acc_field_metabolic_rate += field_metabolic_rate(0.5, 0.5, 0.5)
    var _t1_field_metabolic_rate = perf_counter_ns()
    var _ns_field_metabolic_rate = Float64(_t1_field_metabolic_rate - _t0_field_metabolic_rate) / Float64(N)
    print("MOJO_TIMING ecophysiology::field_metabolic_rate", _ns_field_metabolic_rate, _acc_field_metabolic_rate)
