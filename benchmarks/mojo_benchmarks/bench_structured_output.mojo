"""bench_structured_output.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from structured_output import json_next_token_valid, schema_field_confidence, sql_clause_transition, xml_nesting_depth_valid, output_repair_edit_distance, regex_constraint_match, type_coercion_score, field_extraction_recall, output_diversity_score, format_compliance_rate
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

    var _acc_json_next_token_valid: Float64 = 0.0
    var _t0_json_next_token_valid = perf_counter_ns()
    for _ in range(N):
        _acc_json_next_token_valid += json_next_token_valid(0.5, 0.5)
    var _t1_json_next_token_valid = perf_counter_ns()
    var _ns_json_next_token_valid = Float64(_t1_json_next_token_valid - _t0_json_next_token_valid) / Float64(N)
    print("MOJO_TIMING structured_output::json_next_token_valid", _ns_json_next_token_valid, _acc_json_next_token_valid)
    var _acc_schema_field_confidence: Float64 = 0.0
    var _t0_schema_field_confidence = perf_counter_ns()
    for _ in range(N):
        _acc_schema_field_confidence += schema_field_confidence(0.5, 0.5)
    var _t1_schema_field_confidence = perf_counter_ns()
    var _ns_schema_field_confidence = Float64(_t1_schema_field_confidence - _t0_schema_field_confidence) / Float64(N)
    print("MOJO_TIMING structured_output::schema_field_confidence", _ns_schema_field_confidence, _acc_schema_field_confidence)
    var _acc_sql_clause_transition: Float64 = 0.0
    var _t0_sql_clause_transition = perf_counter_ns()
    for _ in range(N):
        _acc_sql_clause_transition += sql_clause_transition(0.5, 0.5)
    var _t1_sql_clause_transition = perf_counter_ns()
    var _ns_sql_clause_transition = Float64(_t1_sql_clause_transition - _t0_sql_clause_transition) / Float64(N)
    print("MOJO_TIMING structured_output::sql_clause_transition", _ns_sql_clause_transition, _acc_sql_clause_transition)
    var _acc_xml_nesting_depth_valid: Float64 = 0.0
    var _t0_xml_nesting_depth_valid = perf_counter_ns()
    for _ in range(N):
        _acc_xml_nesting_depth_valid += xml_nesting_depth_valid(0.5, 0.5)
    var _t1_xml_nesting_depth_valid = perf_counter_ns()
    var _ns_xml_nesting_depth_valid = Float64(_t1_xml_nesting_depth_valid - _t0_xml_nesting_depth_valid) / Float64(N)
    print("MOJO_TIMING structured_output::xml_nesting_depth_valid", _ns_xml_nesting_depth_valid, _acc_xml_nesting_depth_valid)
    var _acc_output_repair_edit_distance: Float64 = 0.0
    var _t0_output_repair_edit_distance = perf_counter_ns()
    for _ in range(N):
        _acc_output_repair_edit_distance += output_repair_edit_distance(0.5, 0.5)
    var _t1_output_repair_edit_distance = perf_counter_ns()
    var _ns_output_repair_edit_distance = Float64(_t1_output_repair_edit_distance - _t0_output_repair_edit_distance) / Float64(N)
    print("MOJO_TIMING structured_output::output_repair_edit_distance", _ns_output_repair_edit_distance, _acc_output_repair_edit_distance)
    var _acc_regex_constraint_match: Float64 = 0.0
    var _t0_regex_constraint_match = perf_counter_ns()
    for _ in range(N):
        _acc_regex_constraint_match += regex_constraint_match(0.5, 0.5, 0.5)
    var _t1_regex_constraint_match = perf_counter_ns()
    var _ns_regex_constraint_match = Float64(_t1_regex_constraint_match - _t0_regex_constraint_match) / Float64(N)
    print("MOJO_TIMING structured_output::regex_constraint_match", _ns_regex_constraint_match, _acc_regex_constraint_match)
    var _acc_type_coercion_score: Float64 = 0.0
    var _t0_type_coercion_score = perf_counter_ns()
    for _ in range(N):
        _acc_type_coercion_score += type_coercion_score(0.5, 0.5)
    var _t1_type_coercion_score = perf_counter_ns()
    var _ns_type_coercion_score = Float64(_t1_type_coercion_score - _t0_type_coercion_score) / Float64(N)
    print("MOJO_TIMING structured_output::type_coercion_score", _ns_type_coercion_score, _acc_type_coercion_score)
    var _acc_field_extraction_recall: Float64 = 0.0
    var _t0_field_extraction_recall = perf_counter_ns()
    for _ in range(N):
        _acc_field_extraction_recall += field_extraction_recall(0.5, 0.5)
    var _t1_field_extraction_recall = perf_counter_ns()
    var _ns_field_extraction_recall = Float64(_t1_field_extraction_recall - _t0_field_extraction_recall) / Float64(N)
    print("MOJO_TIMING structured_output::field_extraction_recall", _ns_field_extraction_recall, _acc_field_extraction_recall)
    var _acc_output_diversity_score: Float64 = 0.0
    var _t0_output_diversity_score = perf_counter_ns()
    for _ in range(N):
        _acc_output_diversity_score += output_diversity_score(0.5, 0.5)
    var _t1_output_diversity_score = perf_counter_ns()
    var _ns_output_diversity_score = Float64(_t1_output_diversity_score - _t0_output_diversity_score) / Float64(N)
    print("MOJO_TIMING structured_output::output_diversity_score", _ns_output_diversity_score, _acc_output_diversity_score)
    var _acc_format_compliance_rate: Float64 = 0.0
    var _t0_format_compliance_rate = perf_counter_ns()
    for _ in range(N):
        _acc_format_compliance_rate += format_compliance_rate(0.5, 0.5)
    var _t1_format_compliance_rate = perf_counter_ns()
    var _ns_format_compliance_rate = Float64(_t1_format_compliance_rate - _t0_format_compliance_rate) / Float64(N)
    print("MOJO_TIMING structured_output::format_compliance_rate", _ns_format_compliance_rate, _acc_format_compliance_rate)
