"""bench_structured_output.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from structured_output import json_next_token_valid, schema_field_confidence, sql_clause_transition, xml_nesting_depth_valid, output_repair_edit_distance, regex_constraint_match, type_coercion_score, field_extraction_recall, output_diversity_score, format_compliance_rate
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_json_next_token_valid: Float64 = 0.0
    var _t0_json_next_token_valid = perf_counter_ns()
    for _ in range(N):
        _acc_json_next_token_valid += json_next_token_valid(0.5, 0.5)
    var _t1_json_next_token_valid = perf_counter_ns()
    var _ns_json_next_token_valid = Float64(_t1_json_next_token_valid - _t0_json_next_token_valid) / Float64(N)
    print("MOJO_TIMING structured_output::json_next_token_valid", _ns_json_next_token_valid, _acc_json_next_token_valid)
    var _result_json_next_token_valid = json_next_token_valid(0.5, 0.5)
    var _summary_json_next_token_valid = _summary_float64(_result_json_next_token_valid)
    print("MOJO_RESULT structured_output::json_next_token_valid", _summary_json_next_token_valid)
    var _acc_schema_field_confidence: Float64 = 0.0
    var _t0_schema_field_confidence = perf_counter_ns()
    for _ in range(N):
        _acc_schema_field_confidence += schema_field_confidence(0.5, 0.5)
    var _t1_schema_field_confidence = perf_counter_ns()
    var _ns_schema_field_confidence = Float64(_t1_schema_field_confidence - _t0_schema_field_confidence) / Float64(N)
    print("MOJO_TIMING structured_output::schema_field_confidence", _ns_schema_field_confidence, _acc_schema_field_confidence)
    var _result_schema_field_confidence = schema_field_confidence(0.5, 0.5)
    var _summary_schema_field_confidence = _summary_float64(_result_schema_field_confidence)
    print("MOJO_RESULT structured_output::schema_field_confidence", _summary_schema_field_confidence)
    var _acc_sql_clause_transition: Float64 = 0.0
    var _t0_sql_clause_transition = perf_counter_ns()
    for _ in range(N):
        _acc_sql_clause_transition += sql_clause_transition(0.5, 0.5)
    var _t1_sql_clause_transition = perf_counter_ns()
    var _ns_sql_clause_transition = Float64(_t1_sql_clause_transition - _t0_sql_clause_transition) / Float64(N)
    print("MOJO_TIMING structured_output::sql_clause_transition", _ns_sql_clause_transition, _acc_sql_clause_transition)
    var _result_sql_clause_transition = sql_clause_transition(0.5, 0.5)
    var _summary_sql_clause_transition = _summary_float64(_result_sql_clause_transition)
    print("MOJO_RESULT structured_output::sql_clause_transition", _summary_sql_clause_transition)
    var _acc_xml_nesting_depth_valid: Float64 = 0.0
    var _t0_xml_nesting_depth_valid = perf_counter_ns()
    for _ in range(N):
        _acc_xml_nesting_depth_valid += xml_nesting_depth_valid(0.5, 0.5)
    var _t1_xml_nesting_depth_valid = perf_counter_ns()
    var _ns_xml_nesting_depth_valid = Float64(_t1_xml_nesting_depth_valid - _t0_xml_nesting_depth_valid) / Float64(N)
    print("MOJO_TIMING structured_output::xml_nesting_depth_valid", _ns_xml_nesting_depth_valid, _acc_xml_nesting_depth_valid)
    var _result_xml_nesting_depth_valid = xml_nesting_depth_valid(0.5, 0.5)
    var _summary_xml_nesting_depth_valid = _summary_float64(_result_xml_nesting_depth_valid)
    print("MOJO_RESULT structured_output::xml_nesting_depth_valid", _summary_xml_nesting_depth_valid)
    var _acc_output_repair_edit_distance: Float64 = 0.0
    var _t0_output_repair_edit_distance = perf_counter_ns()
    for _ in range(N):
        _acc_output_repair_edit_distance += output_repair_edit_distance(0.5, 0.5)
    var _t1_output_repair_edit_distance = perf_counter_ns()
    var _ns_output_repair_edit_distance = Float64(_t1_output_repair_edit_distance - _t0_output_repair_edit_distance) / Float64(N)
    print("MOJO_TIMING structured_output::output_repair_edit_distance", _ns_output_repair_edit_distance, _acc_output_repair_edit_distance)
    var _result_output_repair_edit_distance = output_repair_edit_distance(0.5, 0.5)
    var _summary_output_repair_edit_distance = _summary_float64(_result_output_repair_edit_distance)
    print("MOJO_RESULT structured_output::output_repair_edit_distance", _summary_output_repair_edit_distance)
    var _acc_regex_constraint_match: Float64 = 0.0
    var _t0_regex_constraint_match = perf_counter_ns()
    for _ in range(N):
        _acc_regex_constraint_match += regex_constraint_match(0.5, 0.5, 0.5)
    var _t1_regex_constraint_match = perf_counter_ns()
    var _ns_regex_constraint_match = Float64(_t1_regex_constraint_match - _t0_regex_constraint_match) / Float64(N)
    print("MOJO_TIMING structured_output::regex_constraint_match", _ns_regex_constraint_match, _acc_regex_constraint_match)
    var _result_regex_constraint_match = regex_constraint_match(0.5, 0.5, 0.5)
    var _summary_regex_constraint_match = _summary_float64(_result_regex_constraint_match)
    print("MOJO_RESULT structured_output::regex_constraint_match", _summary_regex_constraint_match)
    var _acc_type_coercion_score: Float64 = 0.0
    var _t0_type_coercion_score = perf_counter_ns()
    for _ in range(N):
        _acc_type_coercion_score += type_coercion_score(0.5, 0.5)
    var _t1_type_coercion_score = perf_counter_ns()
    var _ns_type_coercion_score = Float64(_t1_type_coercion_score - _t0_type_coercion_score) / Float64(N)
    print("MOJO_TIMING structured_output::type_coercion_score", _ns_type_coercion_score, _acc_type_coercion_score)
    var _result_type_coercion_score = type_coercion_score(0.5, 0.5)
    var _summary_type_coercion_score = _summary_float64(_result_type_coercion_score)
    print("MOJO_RESULT structured_output::type_coercion_score", _summary_type_coercion_score)
    var _acc_field_extraction_recall: Float64 = 0.0
    var _t0_field_extraction_recall = perf_counter_ns()
    for _ in range(N):
        _acc_field_extraction_recall += field_extraction_recall(0.5, 0.5)
    var _t1_field_extraction_recall = perf_counter_ns()
    var _ns_field_extraction_recall = Float64(_t1_field_extraction_recall - _t0_field_extraction_recall) / Float64(N)
    print("MOJO_TIMING structured_output::field_extraction_recall", _ns_field_extraction_recall, _acc_field_extraction_recall)
    var _result_field_extraction_recall = field_extraction_recall(0.5, 0.5)
    var _summary_field_extraction_recall = _summary_float64(_result_field_extraction_recall)
    print("MOJO_RESULT structured_output::field_extraction_recall", _summary_field_extraction_recall)
    var _acc_output_diversity_score: Float64 = 0.0
    var _t0_output_diversity_score = perf_counter_ns()
    for _ in range(N):
        _acc_output_diversity_score += output_diversity_score(0.5, 0.5)
    var _t1_output_diversity_score = perf_counter_ns()
    var _ns_output_diversity_score = Float64(_t1_output_diversity_score - _t0_output_diversity_score) / Float64(N)
    print("MOJO_TIMING structured_output::output_diversity_score", _ns_output_diversity_score, _acc_output_diversity_score)
    var _result_output_diversity_score = output_diversity_score(0.5, 0.5)
    var _summary_output_diversity_score = _summary_float64(_result_output_diversity_score)
    print("MOJO_RESULT structured_output::output_diversity_score", _summary_output_diversity_score)
    var _acc_format_compliance_rate: Float64 = 0.0
    var _t0_format_compliance_rate = perf_counter_ns()
    for _ in range(N):
        _acc_format_compliance_rate += format_compliance_rate(0.5, 0.5)
    var _t1_format_compliance_rate = perf_counter_ns()
    var _ns_format_compliance_rate = Float64(_t1_format_compliance_rate - _t0_format_compliance_rate) / Float64(N)
    print("MOJO_TIMING structured_output::format_compliance_rate", _ns_format_compliance_rate, _acc_format_compliance_rate)
    var _result_format_compliance_rate = format_compliance_rate(0.5, 0.5)
    var _summary_format_compliance_rate = _summary_float64(_result_format_compliance_rate)
    print("MOJO_RESULT structured_output::format_compliance_rate", _summary_format_compliance_rate)
