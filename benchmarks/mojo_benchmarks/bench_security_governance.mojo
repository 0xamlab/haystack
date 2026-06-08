"""bench_security_governance.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from security_governance import model_provenance_hash, prompt_policy_score, output_safety_score, tenant_quota_remaining, audit_log_hash, pii_sensitivity_score, differential_privacy_noise, permission_access_check, data_retention_decay, governance_compliance_score
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

    var _acc_model_provenance_hash: Float64 = 0.0
    var _t0_model_provenance_hash = perf_counter_ns()
    for _ in range(N):
        _acc_model_provenance_hash += model_provenance_hash(0.5, 0.5, 0.5, 0.5)
    var _t1_model_provenance_hash = perf_counter_ns()
    var _ns_model_provenance_hash = Float64(_t1_model_provenance_hash - _t0_model_provenance_hash) / Float64(N)
    print("MOJO_TIMING security_governance::model_provenance_hash", _ns_model_provenance_hash, _acc_model_provenance_hash)
    var _result_model_provenance_hash = model_provenance_hash(0.5, 0.5, 0.5, 0.5)
    var _summary_model_provenance_hash = _summary_float64(_result_model_provenance_hash)
    print("MOJO_RESULT security_governance::model_provenance_hash", _summary_model_provenance_hash)
    var _acc_prompt_policy_score: Float64 = 0.0
    var _t0_prompt_policy_score = perf_counter_ns()
    for _ in range(N):
        _acc_prompt_policy_score += prompt_policy_score(0.5, 0.5, 0.5)
    var _t1_prompt_policy_score = perf_counter_ns()
    var _ns_prompt_policy_score = Float64(_t1_prompt_policy_score - _t0_prompt_policy_score) / Float64(N)
    print("MOJO_TIMING security_governance::prompt_policy_score", _ns_prompt_policy_score, _acc_prompt_policy_score)
    var _result_prompt_policy_score = prompt_policy_score(0.5, 0.5, 0.5)
    var _summary_prompt_policy_score = _summary_float64(_result_prompt_policy_score)
    print("MOJO_RESULT security_governance::prompt_policy_score", _summary_prompt_policy_score)
    var _acc_output_safety_score: Float64 = 0.0
    var _t0_output_safety_score = perf_counter_ns()
    for _ in range(N):
        _acc_output_safety_score += output_safety_score(0.5, 0.5, 0.5)
    var _t1_output_safety_score = perf_counter_ns()
    var _ns_output_safety_score = Float64(_t1_output_safety_score - _t0_output_safety_score) / Float64(N)
    print("MOJO_TIMING security_governance::output_safety_score", _ns_output_safety_score, _acc_output_safety_score)
    var _result_output_safety_score = output_safety_score(0.5, 0.5, 0.5)
    var _summary_output_safety_score = _summary_float64(_result_output_safety_score)
    print("MOJO_RESULT security_governance::output_safety_score", _summary_output_safety_score)
    var _acc_tenant_quota_remaining: Float64 = 0.0
    var _t0_tenant_quota_remaining = perf_counter_ns()
    for _ in range(N):
        _acc_tenant_quota_remaining += tenant_quota_remaining(0.5, 0.5, 0.5, 0.5)
    var _t1_tenant_quota_remaining = perf_counter_ns()
    var _ns_tenant_quota_remaining = Float64(_t1_tenant_quota_remaining - _t0_tenant_quota_remaining) / Float64(N)
    print("MOJO_TIMING security_governance::tenant_quota_remaining", _ns_tenant_quota_remaining, _acc_tenant_quota_remaining)
    var _result_tenant_quota_remaining = tenant_quota_remaining(0.5, 0.5, 0.5, 0.5)
    var _summary_tenant_quota_remaining = _summary_float64(_result_tenant_quota_remaining)
    print("MOJO_RESULT security_governance::tenant_quota_remaining", _summary_tenant_quota_remaining)
    var _acc_audit_log_hash: Float64 = 0.0
    var _t0_audit_log_hash = perf_counter_ns()
    for _ in range(N):
        _acc_audit_log_hash += audit_log_hash(0.5, 0.5, 0.5, 0.5)
    var _t1_audit_log_hash = perf_counter_ns()
    var _ns_audit_log_hash = Float64(_t1_audit_log_hash - _t0_audit_log_hash) / Float64(N)
    print("MOJO_TIMING security_governance::audit_log_hash", _ns_audit_log_hash, _acc_audit_log_hash)
    var _result_audit_log_hash = audit_log_hash(0.5, 0.5, 0.5, 0.5)
    var _summary_audit_log_hash = _summary_float64(_result_audit_log_hash)
    print("MOJO_RESULT security_governance::audit_log_hash", _summary_audit_log_hash)
    var _acc_pii_sensitivity_score: Float64 = 0.0
    var _t0_pii_sensitivity_score = perf_counter_ns()
    for _ in range(N):
        _acc_pii_sensitivity_score += pii_sensitivity_score(0.5, 0.5, 0.5, 0.5)
    var _t1_pii_sensitivity_score = perf_counter_ns()
    var _ns_pii_sensitivity_score = Float64(_t1_pii_sensitivity_score - _t0_pii_sensitivity_score) / Float64(N)
    print("MOJO_TIMING security_governance::pii_sensitivity_score", _ns_pii_sensitivity_score, _acc_pii_sensitivity_score)
    var _result_pii_sensitivity_score = pii_sensitivity_score(0.5, 0.5, 0.5, 0.5)
    var _summary_pii_sensitivity_score = _summary_float64(_result_pii_sensitivity_score)
    print("MOJO_RESULT security_governance::pii_sensitivity_score", _summary_pii_sensitivity_score)
    var _acc_differential_privacy_noise: Float64 = 0.0
    var _t0_differential_privacy_noise = perf_counter_ns()
    for _ in range(N):
        _acc_differential_privacy_noise += differential_privacy_noise(0.5, 0.5, 0.5)
    var _t1_differential_privacy_noise = perf_counter_ns()
    var _ns_differential_privacy_noise = Float64(_t1_differential_privacy_noise - _t0_differential_privacy_noise) / Float64(N)
    print("MOJO_TIMING security_governance::differential_privacy_noise", _ns_differential_privacy_noise, _acc_differential_privacy_noise)
    var _result_differential_privacy_noise = differential_privacy_noise(0.5, 0.5, 0.5)
    var _summary_differential_privacy_noise = _summary_float64(_result_differential_privacy_noise)
    print("MOJO_RESULT security_governance::differential_privacy_noise", _summary_differential_privacy_noise)
    var _acc_permission_access_check: Float64 = 0.0
    var _t0_permission_access_check = perf_counter_ns()
    for _ in range(N):
        _acc_permission_access_check += permission_access_check(0.5, 0.5, 0.5)
    var _t1_permission_access_check = perf_counter_ns()
    var _ns_permission_access_check = Float64(_t1_permission_access_check - _t0_permission_access_check) / Float64(N)
    print("MOJO_TIMING security_governance::permission_access_check", _ns_permission_access_check, _acc_permission_access_check)
    var _result_permission_access_check = permission_access_check(0.5, 0.5, 0.5)
    var _summary_permission_access_check = _summary_float64(_result_permission_access_check)
    print("MOJO_RESULT security_governance::permission_access_check", _summary_permission_access_check)
    var _acc_data_retention_decay: Float64 = 0.0
    var _t0_data_retention_decay = perf_counter_ns()
    for _ in range(N):
        _acc_data_retention_decay += data_retention_decay(0.5, 0.5)
    var _t1_data_retention_decay = perf_counter_ns()
    var _ns_data_retention_decay = Float64(_t1_data_retention_decay - _t0_data_retention_decay) / Float64(N)
    print("MOJO_TIMING security_governance::data_retention_decay", _ns_data_retention_decay, _acc_data_retention_decay)
    var _result_data_retention_decay = data_retention_decay(0.5, 0.5)
    var _summary_data_retention_decay = _summary_float64(_result_data_retention_decay)
    print("MOJO_RESULT security_governance::data_retention_decay", _summary_data_retention_decay)
    var _acc_governance_compliance_score: Float64 = 0.0
    var _t0_governance_compliance_score = perf_counter_ns()
    for _ in range(N):
        _acc_governance_compliance_score += governance_compliance_score(0.5, 0.5, 0.5, 0.5)
    var _t1_governance_compliance_score = perf_counter_ns()
    var _ns_governance_compliance_score = Float64(_t1_governance_compliance_score - _t0_governance_compliance_score) / Float64(N)
    print("MOJO_TIMING security_governance::governance_compliance_score", _ns_governance_compliance_score, _acc_governance_compliance_score)
    var _result_governance_compliance_score = governance_compliance_score(0.5, 0.5, 0.5, 0.5)
    var _summary_governance_compliance_score = _summary_float64(_result_governance_compliance_score)
    print("MOJO_RESULT security_governance::governance_compliance_score", _summary_governance_compliance_score)
