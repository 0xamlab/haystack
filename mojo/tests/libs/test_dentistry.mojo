"""test_dentistry.mojo — auto-generated tests for dentistry library."""
from std.math import isnan, isinf
from dentistry import dmft_index, dmft_prevalence, plaque_index_score, gingival_index, attachment_loss, bone_loss_percentage, fluoride_concentration_ppm, anesthesia_dose_mg, max_anesthesia_dose, restoration_longevity_estimate, tooth_surface_area_estimate, treatment_cost_estimate

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

    _ = dmft_index(5, 5, 5)
    passed += 1; print("  ✅ dentistry::dmft_index")
    var _v_dmft_prevalence = dmft_prevalence(5, 5)
    if is_finite(_v_dmft_prevalence): passed += 1; print("  ✅ dentistry::dmft_prevalence =", _v_dmft_prevalence)
    else: failed += 1; print("  ❌ dentistry::dmft_prevalence → non-finite:", _v_dmft_prevalence)
    var _v_plaque_index_score = plaque_index_score(0.5, 5)
    if is_finite(_v_plaque_index_score): passed += 1; print("  ✅ dentistry::plaque_index_score =", _v_plaque_index_score)
    else: failed += 1; print("  ❌ dentistry::plaque_index_score → non-finite:", _v_plaque_index_score)
    var _v_gingival_index = gingival_index(0.5, 5)
    if is_finite(_v_gingival_index): passed += 1; print("  ✅ dentistry::gingival_index =", _v_gingival_index)
    else: failed += 1; print("  ❌ dentistry::gingival_index → non-finite:", _v_gingival_index)
    var _v_attachment_loss = attachment_loss(0.5, 0.5)
    if is_finite(_v_attachment_loss): passed += 1; print("  ✅ dentistry::attachment_loss =", _v_attachment_loss)
    else: failed += 1; print("  ❌ dentistry::attachment_loss → non-finite:", _v_attachment_loss)
    var _v_bone_loss_percentage = bone_loss_percentage(0.5, 0.5)
    if is_finite(_v_bone_loss_percentage): passed += 1; print("  ✅ dentistry::bone_loss_percentage =", _v_bone_loss_percentage)
    else: failed += 1; print("  ❌ dentistry::bone_loss_percentage → non-finite:", _v_bone_loss_percentage)
    var _v_fluoride_concentration_ppm = fluoride_concentration_ppm(0.5, 0.5)
    if is_finite(_v_fluoride_concentration_ppm): passed += 1; print("  ✅ dentistry::fluoride_concentration_ppm =", _v_fluoride_concentration_ppm)
    else: failed += 1; print("  ❌ dentistry::fluoride_concentration_ppm → non-finite:", _v_fluoride_concentration_ppm)
    var _v_anesthesia_dose_mg = anesthesia_dose_mg(0.5, 0.5, 0.5)
    if is_finite(_v_anesthesia_dose_mg): passed += 1; print("  ✅ dentistry::anesthesia_dose_mg =", _v_anesthesia_dose_mg)
    else: failed += 1; print("  ❌ dentistry::anesthesia_dose_mg → non-finite:", _v_anesthesia_dose_mg)
    var _v_max_anesthesia_dose = max_anesthesia_dose(0.5, 0.5)
    if is_finite(_v_max_anesthesia_dose): passed += 1; print("  ✅ dentistry::max_anesthesia_dose =", _v_max_anesthesia_dose)
    else: failed += 1; print("  ❌ dentistry::max_anesthesia_dose → non-finite:", _v_max_anesthesia_dose)
    var _v_restoration_longevity_estimate = restoration_longevity_estimate(0.5, 0.5)
    if is_finite(_v_restoration_longevity_estimate): passed += 1; print("  ✅ dentistry::restoration_longevity_estimate =", _v_restoration_longevity_estimate)
    else: failed += 1; print("  ❌ dentistry::restoration_longevity_estimate → non-finite:", _v_restoration_longevity_estimate)
    var _v_tooth_surface_area_estimate = tooth_surface_area_estimate(5, 0.5)
    if is_finite(_v_tooth_surface_area_estimate): passed += 1; print("  ✅ dentistry::tooth_surface_area_estimate =", _v_tooth_surface_area_estimate)
    else: failed += 1; print("  ❌ dentistry::tooth_surface_area_estimate → non-finite:", _v_tooth_surface_area_estimate)
    var _v_treatment_cost_estimate = treatment_cost_estimate(5, 0.5, 0.5)
    if is_finite(_v_treatment_cost_estimate): passed += 1; print("  ✅ dentistry::treatment_cost_estimate =", _v_treatment_cost_estimate)
    else: failed += 1; print("  ❌ dentistry::treatment_cost_estimate → non-finite:", _v_treatment_cost_estimate)

    print("  [dentistry] Passed:", passed, "Failed:", failed)
