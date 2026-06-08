"""bench_dentistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dentistry import dmft_index, dmft_prevalence, plaque_index_score, gingival_index, attachment_loss, bone_loss_percentage, fluoride_concentration_ppm, anesthesia_dose_mg, max_anesthesia_dose, restoration_longevity_estimate, tooth_surface_area_estimate, treatment_cost_estimate
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

    var _acc_dmft_index: Float64 = 0.0
    var _t0_dmft_index = perf_counter_ns()
    for _ in range(N):
        _acc_dmft_index += Float64(dmft_index(5, 5, 5))
    var _t1_dmft_index = perf_counter_ns()
    var _ns_dmft_index = Float64(_t1_dmft_index - _t0_dmft_index) / Float64(N)
    print("MOJO_TIMING dentistry::dmft_index", _ns_dmft_index, _acc_dmft_index)
    var _result_dmft_index = dmft_index(5, 5, 5)
    var _summary_dmft_index = _summary_int(_result_dmft_index)
    print("MOJO_RESULT dentistry::dmft_index", _summary_dmft_index)
    var _acc_dmft_prevalence: Float64 = 0.0
    var _t0_dmft_prevalence = perf_counter_ns()
    for _ in range(N):
        _acc_dmft_prevalence += dmft_prevalence(5, 5)
    var _t1_dmft_prevalence = perf_counter_ns()
    var _ns_dmft_prevalence = Float64(_t1_dmft_prevalence - _t0_dmft_prevalence) / Float64(N)
    print("MOJO_TIMING dentistry::dmft_prevalence", _ns_dmft_prevalence, _acc_dmft_prevalence)
    var _result_dmft_prevalence = dmft_prevalence(5, 5)
    var _summary_dmft_prevalence = _summary_float64(_result_dmft_prevalence)
    print("MOJO_RESULT dentistry::dmft_prevalence", _summary_dmft_prevalence)
    var _acc_plaque_index_score: Float64 = 0.0
    var _t0_plaque_index_score = perf_counter_ns()
    for _ in range(N):
        _acc_plaque_index_score += plaque_index_score(0.5, 5)
    var _t1_plaque_index_score = perf_counter_ns()
    var _ns_plaque_index_score = Float64(_t1_plaque_index_score - _t0_plaque_index_score) / Float64(N)
    print("MOJO_TIMING dentistry::plaque_index_score", _ns_plaque_index_score, _acc_plaque_index_score)
    var _result_plaque_index_score = plaque_index_score(0.5, 5)
    var _summary_plaque_index_score = _summary_float64(_result_plaque_index_score)
    print("MOJO_RESULT dentistry::plaque_index_score", _summary_plaque_index_score)
    var _acc_gingival_index: Float64 = 0.0
    var _t0_gingival_index = perf_counter_ns()
    for _ in range(N):
        _acc_gingival_index += gingival_index(0.5, 5)
    var _t1_gingival_index = perf_counter_ns()
    var _ns_gingival_index = Float64(_t1_gingival_index - _t0_gingival_index) / Float64(N)
    print("MOJO_TIMING dentistry::gingival_index", _ns_gingival_index, _acc_gingival_index)
    var _result_gingival_index = gingival_index(0.5, 5)
    var _summary_gingival_index = _summary_float64(_result_gingival_index)
    print("MOJO_RESULT dentistry::gingival_index", _summary_gingival_index)
    var _acc_attachment_loss: Float64 = 0.0
    var _t0_attachment_loss = perf_counter_ns()
    for _ in range(N):
        _acc_attachment_loss += attachment_loss(0.5, 0.5)
    var _t1_attachment_loss = perf_counter_ns()
    var _ns_attachment_loss = Float64(_t1_attachment_loss - _t0_attachment_loss) / Float64(N)
    print("MOJO_TIMING dentistry::attachment_loss", _ns_attachment_loss, _acc_attachment_loss)
    var _result_attachment_loss = attachment_loss(0.5, 0.5)
    var _summary_attachment_loss = _summary_float64(_result_attachment_loss)
    print("MOJO_RESULT dentistry::attachment_loss", _summary_attachment_loss)
    var _acc_bone_loss_percentage: Float64 = 0.0
    var _t0_bone_loss_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_bone_loss_percentage += bone_loss_percentage(0.5, 0.5)
    var _t1_bone_loss_percentage = perf_counter_ns()
    var _ns_bone_loss_percentage = Float64(_t1_bone_loss_percentage - _t0_bone_loss_percentage) / Float64(N)
    print("MOJO_TIMING dentistry::bone_loss_percentage", _ns_bone_loss_percentage, _acc_bone_loss_percentage)
    var _result_bone_loss_percentage = bone_loss_percentage(0.5, 0.5)
    var _summary_bone_loss_percentage = _summary_float64(_result_bone_loss_percentage)
    print("MOJO_RESULT dentistry::bone_loss_percentage", _summary_bone_loss_percentage)
    var _acc_fluoride_concentration_ppm: Float64 = 0.0
    var _t0_fluoride_concentration_ppm = perf_counter_ns()
    for _ in range(N):
        _acc_fluoride_concentration_ppm += fluoride_concentration_ppm(0.5, 0.5)
    var _t1_fluoride_concentration_ppm = perf_counter_ns()
    var _ns_fluoride_concentration_ppm = Float64(_t1_fluoride_concentration_ppm - _t0_fluoride_concentration_ppm) / Float64(N)
    print("MOJO_TIMING dentistry::fluoride_concentration_ppm", _ns_fluoride_concentration_ppm, _acc_fluoride_concentration_ppm)
    var _result_fluoride_concentration_ppm = fluoride_concentration_ppm(0.5, 0.5)
    var _summary_fluoride_concentration_ppm = _summary_float64(_result_fluoride_concentration_ppm)
    print("MOJO_RESULT dentistry::fluoride_concentration_ppm", _summary_fluoride_concentration_ppm)
    var _acc_anesthesia_dose_mg: Float64 = 0.0
    var _t0_anesthesia_dose_mg = perf_counter_ns()
    for _ in range(N):
        _acc_anesthesia_dose_mg += anesthesia_dose_mg(0.5, 0.5, 0.5)
    var _t1_anesthesia_dose_mg = perf_counter_ns()
    var _ns_anesthesia_dose_mg = Float64(_t1_anesthesia_dose_mg - _t0_anesthesia_dose_mg) / Float64(N)
    print("MOJO_TIMING dentistry::anesthesia_dose_mg", _ns_anesthesia_dose_mg, _acc_anesthesia_dose_mg)
    var _result_anesthesia_dose_mg = anesthesia_dose_mg(0.5, 0.5, 0.5)
    var _summary_anesthesia_dose_mg = _summary_float64(_result_anesthesia_dose_mg)
    print("MOJO_RESULT dentistry::anesthesia_dose_mg", _summary_anesthesia_dose_mg)
    var _acc_max_anesthesia_dose: Float64 = 0.0
    var _t0_max_anesthesia_dose = perf_counter_ns()
    for _ in range(N):
        _acc_max_anesthesia_dose += max_anesthesia_dose(0.5, 0.5)
    var _t1_max_anesthesia_dose = perf_counter_ns()
    var _ns_max_anesthesia_dose = Float64(_t1_max_anesthesia_dose - _t0_max_anesthesia_dose) / Float64(N)
    print("MOJO_TIMING dentistry::max_anesthesia_dose", _ns_max_anesthesia_dose, _acc_max_anesthesia_dose)
    var _result_max_anesthesia_dose = max_anesthesia_dose(0.5, 0.5)
    var _summary_max_anesthesia_dose = _summary_float64(_result_max_anesthesia_dose)
    print("MOJO_RESULT dentistry::max_anesthesia_dose", _summary_max_anesthesia_dose)
    var _acc_restoration_longevity_estimate: Float64 = 0.0
    var _t0_restoration_longevity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_restoration_longevity_estimate += restoration_longevity_estimate(0.5, 0.5)
    var _t1_restoration_longevity_estimate = perf_counter_ns()
    var _ns_restoration_longevity_estimate = Float64(_t1_restoration_longevity_estimate - _t0_restoration_longevity_estimate) / Float64(N)
    print("MOJO_TIMING dentistry::restoration_longevity_estimate", _ns_restoration_longevity_estimate, _acc_restoration_longevity_estimate)
    var _result_restoration_longevity_estimate = restoration_longevity_estimate(0.5, 0.5)
    var _summary_restoration_longevity_estimate = _summary_float64(_result_restoration_longevity_estimate)
    print("MOJO_RESULT dentistry::restoration_longevity_estimate", _summary_restoration_longevity_estimate)
    var _acc_tooth_surface_area_estimate: Float64 = 0.0
    var _t0_tooth_surface_area_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_tooth_surface_area_estimate += tooth_surface_area_estimate(5, 0.5)
    var _t1_tooth_surface_area_estimate = perf_counter_ns()
    var _ns_tooth_surface_area_estimate = Float64(_t1_tooth_surface_area_estimate - _t0_tooth_surface_area_estimate) / Float64(N)
    print("MOJO_TIMING dentistry::tooth_surface_area_estimate", _ns_tooth_surface_area_estimate, _acc_tooth_surface_area_estimate)
    var _result_tooth_surface_area_estimate = tooth_surface_area_estimate(5, 0.5)
    var _summary_tooth_surface_area_estimate = _summary_float64(_result_tooth_surface_area_estimate)
    print("MOJO_RESULT dentistry::tooth_surface_area_estimate", _summary_tooth_surface_area_estimate)
    var _acc_treatment_cost_estimate: Float64 = 0.0
    var _t0_treatment_cost_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_treatment_cost_estimate += treatment_cost_estimate(5, 0.5, 0.5)
    var _t1_treatment_cost_estimate = perf_counter_ns()
    var _ns_treatment_cost_estimate = Float64(_t1_treatment_cost_estimate - _t0_treatment_cost_estimate) / Float64(N)
    print("MOJO_TIMING dentistry::treatment_cost_estimate", _ns_treatment_cost_estimate, _acc_treatment_cost_estimate)
    var _result_treatment_cost_estimate = treatment_cost_estimate(5, 0.5, 0.5)
    var _summary_treatment_cost_estimate = _summary_float64(_result_treatment_cost_estimate)
    print("MOJO_RESULT dentistry::treatment_cost_estimate", _summary_treatment_cost_estimate)
