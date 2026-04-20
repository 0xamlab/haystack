"""bench_bryology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bryology import sphagnum_water_holding, moss_growth_rate, carbon_accumulation_peatland, bryophyte_desiccation_recovery, nitrogen_deposition_effect, moss_photosynthesis_rate, peat_accumulation_rate, sphagnum_acidity, patch_colonisation_probability, biomass_to_litter_ratio
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

    var _acc_sphagnum_water_holding: Float64 = 0.0
    var _t0_sphagnum_water_holding = perf_counter_ns()
    for _ in range(N):
        _acc_sphagnum_water_holding += sphagnum_water_holding(0.5, 0.5)
    var _t1_sphagnum_water_holding = perf_counter_ns()
    var _ns_sphagnum_water_holding = Float64(_t1_sphagnum_water_holding - _t0_sphagnum_water_holding) / Float64(N)
    print("MOJO_TIMING bryology::sphagnum_water_holding", _ns_sphagnum_water_holding, _acc_sphagnum_water_holding)
    var _acc_moss_growth_rate: Float64 = 0.0
    var _t0_moss_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_moss_growth_rate += moss_growth_rate(0.5, 0.5, 0.5)
    var _t1_moss_growth_rate = perf_counter_ns()
    var _ns_moss_growth_rate = Float64(_t1_moss_growth_rate - _t0_moss_growth_rate) / Float64(N)
    print("MOJO_TIMING bryology::moss_growth_rate", _ns_moss_growth_rate, _acc_moss_growth_rate)
    var _acc_carbon_accumulation_peatland: Float64 = 0.0
    var _t0_carbon_accumulation_peatland = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_accumulation_peatland += carbon_accumulation_peatland(0.5, 0.5)
    var _t1_carbon_accumulation_peatland = perf_counter_ns()
    var _ns_carbon_accumulation_peatland = Float64(_t1_carbon_accumulation_peatland - _t0_carbon_accumulation_peatland) / Float64(N)
    print("MOJO_TIMING bryology::carbon_accumulation_peatland", _ns_carbon_accumulation_peatland, _acc_carbon_accumulation_peatland)
    var _acc_bryophyte_desiccation_recovery: Float64 = 0.0
    var _t0_bryophyte_desiccation_recovery = perf_counter_ns()
    for _ in range(N):
        _acc_bryophyte_desiccation_recovery += bryophyte_desiccation_recovery(0.5, 0.5, 0.5)
    var _t1_bryophyte_desiccation_recovery = perf_counter_ns()
    var _ns_bryophyte_desiccation_recovery = Float64(_t1_bryophyte_desiccation_recovery - _t0_bryophyte_desiccation_recovery) / Float64(N)
    print("MOJO_TIMING bryology::bryophyte_desiccation_recovery", _ns_bryophyte_desiccation_recovery, _acc_bryophyte_desiccation_recovery)
    var _acc_nitrogen_deposition_effect: Float64 = 0.0
    var _t0_nitrogen_deposition_effect = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_deposition_effect += nitrogen_deposition_effect(0.5, 0.5)
    var _t1_nitrogen_deposition_effect = perf_counter_ns()
    var _ns_nitrogen_deposition_effect = Float64(_t1_nitrogen_deposition_effect - _t0_nitrogen_deposition_effect) / Float64(N)
    print("MOJO_TIMING bryology::nitrogen_deposition_effect", _ns_nitrogen_deposition_effect, _acc_nitrogen_deposition_effect)
    var _acc_moss_photosynthesis_rate: Float64 = 0.0
    var _t0_moss_photosynthesis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_moss_photosynthesis_rate += moss_photosynthesis_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_moss_photosynthesis_rate = perf_counter_ns()
    var _ns_moss_photosynthesis_rate = Float64(_t1_moss_photosynthesis_rate - _t0_moss_photosynthesis_rate) / Float64(N)
    print("MOJO_TIMING bryology::moss_photosynthesis_rate", _ns_moss_photosynthesis_rate, _acc_moss_photosynthesis_rate)
    var _acc_peat_accumulation_rate: Float64 = 0.0
    var _t0_peat_accumulation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_peat_accumulation_rate += peat_accumulation_rate(0.5, 0.5)
    var _t1_peat_accumulation_rate = perf_counter_ns()
    var _ns_peat_accumulation_rate = Float64(_t1_peat_accumulation_rate - _t0_peat_accumulation_rate) / Float64(N)
    print("MOJO_TIMING bryology::peat_accumulation_rate", _ns_peat_accumulation_rate, _acc_peat_accumulation_rate)
    var _acc_sphagnum_acidity: Float64 = 0.0
    var _t0_sphagnum_acidity = perf_counter_ns()
    for _ in range(N):
        _acc_sphagnum_acidity += sphagnum_acidity(0.5, 0.5)
    var _t1_sphagnum_acidity = perf_counter_ns()
    var _ns_sphagnum_acidity = Float64(_t1_sphagnum_acidity - _t0_sphagnum_acidity) / Float64(N)
    print("MOJO_TIMING bryology::sphagnum_acidity", _ns_sphagnum_acidity, _acc_sphagnum_acidity)
    var _acc_patch_colonisation_probability: Float64 = 0.0
    var _t0_patch_colonisation_probability = perf_counter_ns()
    for _ in range(N):
        _acc_patch_colonisation_probability += patch_colonisation_probability(0.5, 0.5, 0.5)
    var _t1_patch_colonisation_probability = perf_counter_ns()
    var _ns_patch_colonisation_probability = Float64(_t1_patch_colonisation_probability - _t0_patch_colonisation_probability) / Float64(N)
    print("MOJO_TIMING bryology::patch_colonisation_probability", _ns_patch_colonisation_probability, _acc_patch_colonisation_probability)
    var _acc_biomass_to_litter_ratio: Float64 = 0.0
    var _t0_biomass_to_litter_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_biomass_to_litter_ratio += biomass_to_litter_ratio(0.5, 0.5)
    var _t1_biomass_to_litter_ratio = perf_counter_ns()
    var _ns_biomass_to_litter_ratio = Float64(_t1_biomass_to_litter_ratio - _t0_biomass_to_litter_ratio) / Float64(N)
    print("MOJO_TIMING bryology::biomass_to_litter_ratio", _ns_biomass_to_litter_ratio, _acc_biomass_to_litter_ratio)
