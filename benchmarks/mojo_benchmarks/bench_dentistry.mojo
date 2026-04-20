"""bench_dentistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dentistry import dmft_index, dmft_prevalence, plaque_index_score, gingival_index, attachment_loss, bone_loss_percentage, fluoride_concentration_ppm, anesthesia_dose_mg, max_anesthesia_dose, restoration_longevity_estimate, tooth_surface_area_estimate, treatment_cost_estimate
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

    var _acc_dmft_index: Float64 = 0.0
    var _t0_dmft_index = perf_counter_ns()
    for _ in range(N):
        _acc_dmft_index += Float64(dmft_index(5, 5, 5))
    var _t1_dmft_index = perf_counter_ns()
    var _ns_dmft_index = Float64(_t1_dmft_index - _t0_dmft_index) / Float64(N)
    print("MOJO_TIMING dentistry::dmft_index", _ns_dmft_index, _acc_dmft_index)
    var _acc_dmft_prevalence: Float64 = 0.0
    var _t0_dmft_prevalence = perf_counter_ns()
    for _ in range(N):
        _acc_dmft_prevalence += dmft_prevalence(5, 5)
    var _t1_dmft_prevalence = perf_counter_ns()
    var _ns_dmft_prevalence = Float64(_t1_dmft_prevalence - _t0_dmft_prevalence) / Float64(N)
    print("MOJO_TIMING dentistry::dmft_prevalence", _ns_dmft_prevalence, _acc_dmft_prevalence)
    var _acc_plaque_index_score: Float64 = 0.0
    var _t0_plaque_index_score = perf_counter_ns()
    for _ in range(N):
        _acc_plaque_index_score += plaque_index_score(0.5, 5)
    var _t1_plaque_index_score = perf_counter_ns()
    var _ns_plaque_index_score = Float64(_t1_plaque_index_score - _t0_plaque_index_score) / Float64(N)
    print("MOJO_TIMING dentistry::plaque_index_score", _ns_plaque_index_score, _acc_plaque_index_score)
    var _acc_gingival_index: Float64 = 0.0
    var _t0_gingival_index = perf_counter_ns()
    for _ in range(N):
        _acc_gingival_index += gingival_index(0.5, 5)
    var _t1_gingival_index = perf_counter_ns()
    var _ns_gingival_index = Float64(_t1_gingival_index - _t0_gingival_index) / Float64(N)
    print("MOJO_TIMING dentistry::gingival_index", _ns_gingival_index, _acc_gingival_index)
    var _acc_attachment_loss: Float64 = 0.0
    var _t0_attachment_loss = perf_counter_ns()
    for _ in range(N):
        _acc_attachment_loss += attachment_loss(0.5, 0.5)
    var _t1_attachment_loss = perf_counter_ns()
    var _ns_attachment_loss = Float64(_t1_attachment_loss - _t0_attachment_loss) / Float64(N)
    print("MOJO_TIMING dentistry::attachment_loss", _ns_attachment_loss, _acc_attachment_loss)
    var _acc_bone_loss_percentage: Float64 = 0.0
    var _t0_bone_loss_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_bone_loss_percentage += bone_loss_percentage(0.5, 0.5)
    var _t1_bone_loss_percentage = perf_counter_ns()
    var _ns_bone_loss_percentage = Float64(_t1_bone_loss_percentage - _t0_bone_loss_percentage) / Float64(N)
    print("MOJO_TIMING dentistry::bone_loss_percentage", _ns_bone_loss_percentage, _acc_bone_loss_percentage)
    var _acc_fluoride_concentration_ppm: Float64 = 0.0
    var _t0_fluoride_concentration_ppm = perf_counter_ns()
    for _ in range(N):
        _acc_fluoride_concentration_ppm += fluoride_concentration_ppm(0.5, 0.5)
    var _t1_fluoride_concentration_ppm = perf_counter_ns()
    var _ns_fluoride_concentration_ppm = Float64(_t1_fluoride_concentration_ppm - _t0_fluoride_concentration_ppm) / Float64(N)
    print("MOJO_TIMING dentistry::fluoride_concentration_ppm", _ns_fluoride_concentration_ppm, _acc_fluoride_concentration_ppm)
    var _acc_anesthesia_dose_mg: Float64 = 0.0
    var _t0_anesthesia_dose_mg = perf_counter_ns()
    for _ in range(N):
        _acc_anesthesia_dose_mg += anesthesia_dose_mg(0.5, 0.5, 0.5)
    var _t1_anesthesia_dose_mg = perf_counter_ns()
    var _ns_anesthesia_dose_mg = Float64(_t1_anesthesia_dose_mg - _t0_anesthesia_dose_mg) / Float64(N)
    print("MOJO_TIMING dentistry::anesthesia_dose_mg", _ns_anesthesia_dose_mg, _acc_anesthesia_dose_mg)
    var _acc_max_anesthesia_dose: Float64 = 0.0
    var _t0_max_anesthesia_dose = perf_counter_ns()
    for _ in range(N):
        _acc_max_anesthesia_dose += max_anesthesia_dose(0.5, 0.5)
    var _t1_max_anesthesia_dose = perf_counter_ns()
    var _ns_max_anesthesia_dose = Float64(_t1_max_anesthesia_dose - _t0_max_anesthesia_dose) / Float64(N)
    print("MOJO_TIMING dentistry::max_anesthesia_dose", _ns_max_anesthesia_dose, _acc_max_anesthesia_dose)
    var _acc_restoration_longevity_estimate: Float64 = 0.0
    var _t0_restoration_longevity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_restoration_longevity_estimate += restoration_longevity_estimate(0.5, 0.5)
    var _t1_restoration_longevity_estimate = perf_counter_ns()
    var _ns_restoration_longevity_estimate = Float64(_t1_restoration_longevity_estimate - _t0_restoration_longevity_estimate) / Float64(N)
    print("MOJO_TIMING dentistry::restoration_longevity_estimate", _ns_restoration_longevity_estimate, _acc_restoration_longevity_estimate)
    var _acc_tooth_surface_area_estimate: Float64 = 0.0
    var _t0_tooth_surface_area_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_tooth_surface_area_estimate += tooth_surface_area_estimate(5, 0.5)
    var _t1_tooth_surface_area_estimate = perf_counter_ns()
    var _ns_tooth_surface_area_estimate = Float64(_t1_tooth_surface_area_estimate - _t0_tooth_surface_area_estimate) / Float64(N)
    print("MOJO_TIMING dentistry::tooth_surface_area_estimate", _ns_tooth_surface_area_estimate, _acc_tooth_surface_area_estimate)
    var _acc_treatment_cost_estimate: Float64 = 0.0
    var _t0_treatment_cost_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_treatment_cost_estimate += treatment_cost_estimate(5, 0.5, 0.5)
    var _t1_treatment_cost_estimate = perf_counter_ns()
    var _ns_treatment_cost_estimate = Float64(_t1_treatment_cost_estimate - _t0_treatment_cost_estimate) / Float64(N)
    print("MOJO_TIMING dentistry::treatment_cost_estimate", _ns_treatment_cost_estimate, _acc_treatment_cost_estimate)
