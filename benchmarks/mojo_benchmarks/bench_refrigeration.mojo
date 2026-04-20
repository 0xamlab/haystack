"""bench_refrigeration.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from refrigeration import cop_refrigeration, cop_heat_pump, carnot_cop_refrigeration, carnot_cop_heat_pump, refrigeration_capacity_tons, superheat, subcooling, mass_flow_rate, compressor_work, energy_efficiency_ratio, seer_to_cop, refrigerant_charge_estimate
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

    var _acc_cop_refrigeration: Float64 = 0.0
    var _t0_cop_refrigeration = perf_counter_ns()
    for _ in range(N):
        _acc_cop_refrigeration += cop_refrigeration(0.5, 0.5)
    var _t1_cop_refrigeration = perf_counter_ns()
    var _ns_cop_refrigeration = Float64(_t1_cop_refrigeration - _t0_cop_refrigeration) / Float64(N)
    print("MOJO_TIMING refrigeration::cop_refrigeration", _ns_cop_refrigeration, _acc_cop_refrigeration)
    var _acc_cop_heat_pump: Float64 = 0.0
    var _t0_cop_heat_pump = perf_counter_ns()
    for _ in range(N):
        _acc_cop_heat_pump += cop_heat_pump(0.5, 0.5)
    var _t1_cop_heat_pump = perf_counter_ns()
    var _ns_cop_heat_pump = Float64(_t1_cop_heat_pump - _t0_cop_heat_pump) / Float64(N)
    print("MOJO_TIMING refrigeration::cop_heat_pump", _ns_cop_heat_pump, _acc_cop_heat_pump)
    var _acc_carnot_cop_refrigeration: Float64 = 0.0
    var _t0_carnot_cop_refrigeration = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_cop_refrigeration += carnot_cop_refrigeration(0.5, 0.5)
    var _t1_carnot_cop_refrigeration = perf_counter_ns()
    var _ns_carnot_cop_refrigeration = Float64(_t1_carnot_cop_refrigeration - _t0_carnot_cop_refrigeration) / Float64(N)
    print("MOJO_TIMING refrigeration::carnot_cop_refrigeration", _ns_carnot_cop_refrigeration, _acc_carnot_cop_refrigeration)
    var _acc_carnot_cop_heat_pump: Float64 = 0.0
    var _t0_carnot_cop_heat_pump = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_cop_heat_pump += carnot_cop_heat_pump(0.5, 0.5)
    var _t1_carnot_cop_heat_pump = perf_counter_ns()
    var _ns_carnot_cop_heat_pump = Float64(_t1_carnot_cop_heat_pump - _t0_carnot_cop_heat_pump) / Float64(N)
    print("MOJO_TIMING refrigeration::carnot_cop_heat_pump", _ns_carnot_cop_heat_pump, _acc_carnot_cop_heat_pump)
    var _acc_refrigeration_capacity_tons: Float64 = 0.0
    var _t0_refrigeration_capacity_tons = perf_counter_ns()
    for _ in range(N):
        _acc_refrigeration_capacity_tons += refrigeration_capacity_tons(0.5)
    var _t1_refrigeration_capacity_tons = perf_counter_ns()
    var _ns_refrigeration_capacity_tons = Float64(_t1_refrigeration_capacity_tons - _t0_refrigeration_capacity_tons) / Float64(N)
    print("MOJO_TIMING refrigeration::refrigeration_capacity_tons", _ns_refrigeration_capacity_tons, _acc_refrigeration_capacity_tons)
    var _acc_superheat: Float64 = 0.0
    var _t0_superheat = perf_counter_ns()
    for _ in range(N):
        _acc_superheat += superheat(0.5, 0.5)
    var _t1_superheat = perf_counter_ns()
    var _ns_superheat = Float64(_t1_superheat - _t0_superheat) / Float64(N)
    print("MOJO_TIMING refrigeration::superheat", _ns_superheat, _acc_superheat)
    var _acc_subcooling: Float64 = 0.0
    var _t0_subcooling = perf_counter_ns()
    for _ in range(N):
        _acc_subcooling += subcooling(0.5, 0.5)
    var _t1_subcooling = perf_counter_ns()
    var _ns_subcooling = Float64(_t1_subcooling - _t0_subcooling) / Float64(N)
    print("MOJO_TIMING refrigeration::subcooling", _ns_subcooling, _acc_subcooling)
    var _acc_mass_flow_rate: Float64 = 0.0
    var _t0_mass_flow_rate = perf_counter_ns()
    for _ in range(N):
        _acc_mass_flow_rate += mass_flow_rate(0.5, 0.5)
    var _t1_mass_flow_rate = perf_counter_ns()
    var _ns_mass_flow_rate = Float64(_t1_mass_flow_rate - _t0_mass_flow_rate) / Float64(N)
    print("MOJO_TIMING refrigeration::mass_flow_rate", _ns_mass_flow_rate, _acc_mass_flow_rate)
    var _acc_compressor_work: Float64 = 0.0
    var _t0_compressor_work = perf_counter_ns()
    for _ in range(N):
        _acc_compressor_work += compressor_work(0.5, 0.5, 0.5)
    var _t1_compressor_work = perf_counter_ns()
    var _ns_compressor_work = Float64(_t1_compressor_work - _t0_compressor_work) / Float64(N)
    print("MOJO_TIMING refrigeration::compressor_work", _ns_compressor_work, _acc_compressor_work)
    var _acc_energy_efficiency_ratio: Float64 = 0.0
    var _t0_energy_efficiency_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_energy_efficiency_ratio += energy_efficiency_ratio(0.5, 0.5)
    var _t1_energy_efficiency_ratio = perf_counter_ns()
    var _ns_energy_efficiency_ratio = Float64(_t1_energy_efficiency_ratio - _t0_energy_efficiency_ratio) / Float64(N)
    print("MOJO_TIMING refrigeration::energy_efficiency_ratio", _ns_energy_efficiency_ratio, _acc_energy_efficiency_ratio)
    var _acc_seer_to_cop: Float64 = 0.0
    var _t0_seer_to_cop = perf_counter_ns()
    for _ in range(N):
        _acc_seer_to_cop += seer_to_cop(0.5)
    var _t1_seer_to_cop = perf_counter_ns()
    var _ns_seer_to_cop = Float64(_t1_seer_to_cop - _t0_seer_to_cop) / Float64(N)
    print("MOJO_TIMING refrigeration::seer_to_cop", _ns_seer_to_cop, _acc_seer_to_cop)
    var _acc_refrigerant_charge_estimate: Float64 = 0.0
    var _t0_refrigerant_charge_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_refrigerant_charge_estimate += refrigerant_charge_estimate(0.5, 0.5)
    var _t1_refrigerant_charge_estimate = perf_counter_ns()
    var _ns_refrigerant_charge_estimate = Float64(_t1_refrigerant_charge_estimate - _t0_refrigerant_charge_estimate) / Float64(N)
    print("MOJO_TIMING refrigeration::refrigerant_charge_estimate", _ns_refrigerant_charge_estimate, _acc_refrigerant_charge_estimate)
