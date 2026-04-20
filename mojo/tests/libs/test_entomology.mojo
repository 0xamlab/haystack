"""test_entomology.mojo — auto-generated tests for entomology library."""
from std.math import isnan, isinf
from entomology import degree_days, accumulated_degree_days, population_growth_intrinsic, net_reproductive_rate, generation_time, doubling_time_population, species_diversity_simpson, trap_catch_index, infestation_rate, biocontrol_efficacy, larval_mortality_rate, metabolic_rate_insect

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_degree_days = degree_days(0.5, 0.5, 0.5)
    if is_finite(_v_degree_days): passed += 1; print("  ✅ entomology::degree_days =", _v_degree_days)
    else: failed += 1; print("  ❌ entomology::degree_days → non-finite:", _v_degree_days)
    var _v_accumulated_degree_days = accumulated_degree_days(0.5, 0.5)
    if is_finite(_v_accumulated_degree_days): passed += 1; print("  ✅ entomology::accumulated_degree_days =", _v_accumulated_degree_days)
    else: failed += 1; print("  ❌ entomology::accumulated_degree_days → non-finite:", _v_accumulated_degree_days)
    var _v_population_growth_intrinsic = population_growth_intrinsic(0.5, 0.5, 0.5)
    if is_finite(_v_population_growth_intrinsic): passed += 1; print("  ✅ entomology::population_growth_intrinsic =", _v_population_growth_intrinsic)
    else: failed += 1; print("  ❌ entomology::population_growth_intrinsic → non-finite:", _v_population_growth_intrinsic)
    var _v_net_reproductive_rate = net_reproductive_rate(0.5, 0.5)
    if is_finite(_v_net_reproductive_rate): passed += 1; print("  ✅ entomology::net_reproductive_rate =", _v_net_reproductive_rate)
    else: failed += 1; print("  ❌ entomology::net_reproductive_rate → non-finite:", _v_net_reproductive_rate)
    var _v_generation_time = generation_time(0.5, 0.5)
    if is_finite(_v_generation_time): passed += 1; print("  ✅ entomology::generation_time =", _v_generation_time)
    else: failed += 1; print("  ❌ entomology::generation_time → non-finite:", _v_generation_time)
    var _v_doubling_time_population = doubling_time_population(0.5)
    if is_finite(_v_doubling_time_population): passed += 1; print("  ✅ entomology::doubling_time_population =", _v_doubling_time_population)
    else: failed += 1; print("  ❌ entomology::doubling_time_population → non-finite:", _v_doubling_time_population)
    var _v_species_diversity_simpson = species_diversity_simpson(0.5)
    if is_finite(_v_species_diversity_simpson): passed += 1; print("  ✅ entomology::species_diversity_simpson =", _v_species_diversity_simpson)
    else: failed += 1; print("  ❌ entomology::species_diversity_simpson → non-finite:", _v_species_diversity_simpson)
    var _v_trap_catch_index = trap_catch_index(0.5, 0.5, 0.5)
    if is_finite(_v_trap_catch_index): passed += 1; print("  ✅ entomology::trap_catch_index =", _v_trap_catch_index)
    else: failed += 1; print("  ❌ entomology::trap_catch_index → non-finite:", _v_trap_catch_index)
    var _v_infestation_rate = infestation_rate(0.5, 0.5)
    if is_finite(_v_infestation_rate): passed += 1; print("  ✅ entomology::infestation_rate =", _v_infestation_rate)
    else: failed += 1; print("  ❌ entomology::infestation_rate → non-finite:", _v_infestation_rate)
    var _v_biocontrol_efficacy = biocontrol_efficacy(0.5, 0.5)
    if is_finite(_v_biocontrol_efficacy): passed += 1; print("  ✅ entomology::biocontrol_efficacy =", _v_biocontrol_efficacy)
    else: failed += 1; print("  ❌ entomology::biocontrol_efficacy → non-finite:", _v_biocontrol_efficacy)
    var _v_larval_mortality_rate = larval_mortality_rate(0.5, 0.5)
    if is_finite(_v_larval_mortality_rate): passed += 1; print("  ✅ entomology::larval_mortality_rate =", _v_larval_mortality_rate)
    else: failed += 1; print("  ❌ entomology::larval_mortality_rate → non-finite:", _v_larval_mortality_rate)
    var _v_metabolic_rate_insect = metabolic_rate_insect(0.5, 0.5)
    if is_finite(_v_metabolic_rate_insect): passed += 1; print("  ✅ entomology::metabolic_rate_insect =", _v_metabolic_rate_insect)
    else: failed += 1; print("  ❌ entomology::metabolic_rate_insect → non-finite:", _v_metabolic_rate_insect)

    print("  [entomology] Passed:", passed, "Failed:", failed)
