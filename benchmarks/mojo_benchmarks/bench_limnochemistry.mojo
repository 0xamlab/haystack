"""bench_limnochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from limnochemistry import carbonate_alkalinity, ionic_strength, activity_coefficient_davies, pow_10, saturation_index_calcite, silicon_weathering_flux, redox_pe_eh, phosphorus_fractionation, nitrogen_speciation, doc_light_attenuation, epilimnion_mixing_depth
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

    var _acc_carbonate_alkalinity: Float64 = 0.0
    var _t0_carbonate_alkalinity = perf_counter_ns()
    for _ in range(N):
        _acc_carbonate_alkalinity += carbonate_alkalinity(0.5, 0.5, 0.5, 0.5)
    var _t1_carbonate_alkalinity = perf_counter_ns()
    var _ns_carbonate_alkalinity = Float64(_t1_carbonate_alkalinity - _t0_carbonate_alkalinity) / Float64(N)
    print("MOJO_TIMING limnochemistry::carbonate_alkalinity", _ns_carbonate_alkalinity, _acc_carbonate_alkalinity)
    var _acc_ionic_strength: Float64 = 0.0
    var _t0_ionic_strength = perf_counter_ns()
    for _ in range(N):
        _acc_ionic_strength += ionic_strength(0.5, 0.5)
    var _t1_ionic_strength = perf_counter_ns()
    var _ns_ionic_strength = Float64(_t1_ionic_strength - _t0_ionic_strength) / Float64(N)
    print("MOJO_TIMING limnochemistry::ionic_strength", _ns_ionic_strength, _acc_ionic_strength)
    var _acc_activity_coefficient_davies: Float64 = 0.0
    var _t0_activity_coefficient_davies = perf_counter_ns()
    for _ in range(N):
        _acc_activity_coefficient_davies += activity_coefficient_davies(0.5, 0.5)
    var _t1_activity_coefficient_davies = perf_counter_ns()
    var _ns_activity_coefficient_davies = Float64(_t1_activity_coefficient_davies - _t0_activity_coefficient_davies) / Float64(N)
    print("MOJO_TIMING limnochemistry::activity_coefficient_davies", _ns_activity_coefficient_davies, _acc_activity_coefficient_davies)
    var _acc_pow_10: Float64 = 0.0
    var _t0_pow_10 = perf_counter_ns()
    for _ in range(N):
        _acc_pow_10 += pow_10(0.5)
    var _t1_pow_10 = perf_counter_ns()
    var _ns_pow_10 = Float64(_t1_pow_10 - _t0_pow_10) / Float64(N)
    print("MOJO_TIMING limnochemistry::pow_10", _ns_pow_10, _acc_pow_10)
    var _acc_saturation_index_calcite: Float64 = 0.0
    var _t0_saturation_index_calcite = perf_counter_ns()
    for _ in range(N):
        _acc_saturation_index_calcite += saturation_index_calcite(0.5, 0.5, 0.5, 0.5)
    var _t1_saturation_index_calcite = perf_counter_ns()
    var _ns_saturation_index_calcite = Float64(_t1_saturation_index_calcite - _t0_saturation_index_calcite) / Float64(N)
    print("MOJO_TIMING limnochemistry::saturation_index_calcite", _ns_saturation_index_calcite, _acc_saturation_index_calcite)
    var _acc_silicon_weathering_flux: Float64 = 0.0
    var _t0_silicon_weathering_flux = perf_counter_ns()
    for _ in range(N):
        _acc_silicon_weathering_flux += silicon_weathering_flux(0.5, 0.5, 0.5)
    var _t1_silicon_weathering_flux = perf_counter_ns()
    var _ns_silicon_weathering_flux = Float64(_t1_silicon_weathering_flux - _t0_silicon_weathering_flux) / Float64(N)
    print("MOJO_TIMING limnochemistry::silicon_weathering_flux", _ns_silicon_weathering_flux, _acc_silicon_weathering_flux)
    var _acc_redox_pe_eh: Float64 = 0.0
    var _t0_redox_pe_eh = perf_counter_ns()
    for _ in range(N):
        _acc_redox_pe_eh += redox_pe_eh(0.5, 0.5)
    var _t1_redox_pe_eh = perf_counter_ns()
    var _ns_redox_pe_eh = Float64(_t1_redox_pe_eh - _t0_redox_pe_eh) / Float64(N)
    print("MOJO_TIMING limnochemistry::redox_pe_eh", _ns_redox_pe_eh, _acc_redox_pe_eh)
    var _acc_phosphorus_fractionation: Float64 = 0.0
    var _t0_phosphorus_fractionation = perf_counter_ns()
    for _ in range(N):
        _acc_phosphorus_fractionation += phosphorus_fractionation(0.5, 0.5)
    var _t1_phosphorus_fractionation = perf_counter_ns()
    var _ns_phosphorus_fractionation = Float64(_t1_phosphorus_fractionation - _t0_phosphorus_fractionation) / Float64(N)
    print("MOJO_TIMING limnochemistry::phosphorus_fractionation", _ns_phosphorus_fractionation, _acc_phosphorus_fractionation)
    var _acc_nitrogen_speciation: Float64 = 0.0
    var _t0_nitrogen_speciation = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_speciation += nitrogen_speciation(0.5, 0.5, 0.5)
    var _t1_nitrogen_speciation = perf_counter_ns()
    var _ns_nitrogen_speciation = Float64(_t1_nitrogen_speciation - _t0_nitrogen_speciation) / Float64(N)
    print("MOJO_TIMING limnochemistry::nitrogen_speciation", _ns_nitrogen_speciation, _acc_nitrogen_speciation)
    var _acc_doc_light_attenuation: Float64 = 0.0
    var _t0_doc_light_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_doc_light_attenuation += doc_light_attenuation(0.5, 0.5)
    var _t1_doc_light_attenuation = perf_counter_ns()
    var _ns_doc_light_attenuation = Float64(_t1_doc_light_attenuation - _t0_doc_light_attenuation) / Float64(N)
    print("MOJO_TIMING limnochemistry::doc_light_attenuation", _ns_doc_light_attenuation, _acc_doc_light_attenuation)
    var _acc_epilimnion_mixing_depth: Float64 = 0.0
    var _t0_epilimnion_mixing_depth = perf_counter_ns()
    for _ in range(N):
        _acc_epilimnion_mixing_depth += epilimnion_mixing_depth(0.5, 0.5, 0.5)
    var _t1_epilimnion_mixing_depth = perf_counter_ns()
    var _ns_epilimnion_mixing_depth = Float64(_t1_epilimnion_mixing_depth - _t0_epilimnion_mixing_depth) / Float64(N)
    print("MOJO_TIMING limnochemistry::epilimnion_mixing_depth", _ns_epilimnion_mixing_depth, _acc_epilimnion_mixing_depth)
