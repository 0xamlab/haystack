"""bench_security_governance.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from security_governance import model_provenance_hash, prompt_policy_score, output_safety_score, tenant_quota_remaining, audit_log_hash, pii_sensitivity_score, differential_privacy_noise, permission_access_check, data_retention_decay, governance_compliance_score
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

    var _acc_model_provenance_hash: Float64 = 0.0
    var _t0_model_provenance_hash = perf_counter_ns()
    for _ in range(N):
        _acc_model_provenance_hash += model_provenance_hash(0.5, 0.5, 0.5, 0.5)
    var _t1_model_provenance_hash = perf_counter_ns()
    var _ns_model_provenance_hash = Float64(_t1_model_provenance_hash - _t0_model_provenance_hash) / Float64(N)
    print("MOJO_TIMING security_governance::model_provenance_hash", _ns_model_provenance_hash, _acc_model_provenance_hash)
    var _acc_prompt_policy_score: Float64 = 0.0
    var _t0_prompt_policy_score = perf_counter_ns()
    for _ in range(N):
        _acc_prompt_policy_score += prompt_policy_score(0.5, 0.5, 0.5)
    var _t1_prompt_policy_score = perf_counter_ns()
    var _ns_prompt_policy_score = Float64(_t1_prompt_policy_score - _t0_prompt_policy_score) / Float64(N)
    print("MOJO_TIMING security_governance::prompt_policy_score", _ns_prompt_policy_score, _acc_prompt_policy_score)
    var _acc_output_safety_score: Float64 = 0.0
    var _t0_output_safety_score = perf_counter_ns()
    for _ in range(N):
        _acc_output_safety_score += output_safety_score(0.5, 0.5, 0.5)
    var _t1_output_safety_score = perf_counter_ns()
    var _ns_output_safety_score = Float64(_t1_output_safety_score - _t0_output_safety_score) / Float64(N)
    print("MOJO_TIMING security_governance::output_safety_score", _ns_output_safety_score, _acc_output_safety_score)
    var _acc_tenant_quota_remaining: Float64 = 0.0
    var _t0_tenant_quota_remaining = perf_counter_ns()
    for _ in range(N):
        _acc_tenant_quota_remaining += tenant_quota_remaining(0.5, 0.5, 0.5, 0.5)
    var _t1_tenant_quota_remaining = perf_counter_ns()
    var _ns_tenant_quota_remaining = Float64(_t1_tenant_quota_remaining - _t0_tenant_quota_remaining) / Float64(N)
    print("MOJO_TIMING security_governance::tenant_quota_remaining", _ns_tenant_quota_remaining, _acc_tenant_quota_remaining)
    var _acc_audit_log_hash: Float64 = 0.0
    var _t0_audit_log_hash = perf_counter_ns()
    for _ in range(N):
        _acc_audit_log_hash += audit_log_hash(0.5, 0.5, 0.5, 0.5)
    var _t1_audit_log_hash = perf_counter_ns()
    var _ns_audit_log_hash = Float64(_t1_audit_log_hash - _t0_audit_log_hash) / Float64(N)
    print("MOJO_TIMING security_governance::audit_log_hash", _ns_audit_log_hash, _acc_audit_log_hash)
    var _acc_pii_sensitivity_score: Float64 = 0.0
    var _t0_pii_sensitivity_score = perf_counter_ns()
    for _ in range(N):
        _acc_pii_sensitivity_score += pii_sensitivity_score(0.5, 0.5, 0.5, 0.5)
    var _t1_pii_sensitivity_score = perf_counter_ns()
    var _ns_pii_sensitivity_score = Float64(_t1_pii_sensitivity_score - _t0_pii_sensitivity_score) / Float64(N)
    print("MOJO_TIMING security_governance::pii_sensitivity_score", _ns_pii_sensitivity_score, _acc_pii_sensitivity_score)
    var _acc_differential_privacy_noise: Float64 = 0.0
    var _t0_differential_privacy_noise = perf_counter_ns()
    for _ in range(N):
        _acc_differential_privacy_noise += differential_privacy_noise(0.5, 0.5, 0.5)
    var _t1_differential_privacy_noise = perf_counter_ns()
    var _ns_differential_privacy_noise = Float64(_t1_differential_privacy_noise - _t0_differential_privacy_noise) / Float64(N)
    print("MOJO_TIMING security_governance::differential_privacy_noise", _ns_differential_privacy_noise, _acc_differential_privacy_noise)
    var _acc_permission_access_check: Float64 = 0.0
    var _t0_permission_access_check = perf_counter_ns()
    for _ in range(N):
        _acc_permission_access_check += permission_access_check(0.5, 0.5, 0.5)
    var _t1_permission_access_check = perf_counter_ns()
    var _ns_permission_access_check = Float64(_t1_permission_access_check - _t0_permission_access_check) / Float64(N)
    print("MOJO_TIMING security_governance::permission_access_check", _ns_permission_access_check, _acc_permission_access_check)
    var _acc_data_retention_decay: Float64 = 0.0
    var _t0_data_retention_decay = perf_counter_ns()
    for _ in range(N):
        _acc_data_retention_decay += data_retention_decay(0.5, 0.5)
    var _t1_data_retention_decay = perf_counter_ns()
    var _ns_data_retention_decay = Float64(_t1_data_retention_decay - _t0_data_retention_decay) / Float64(N)
    print("MOJO_TIMING security_governance::data_retention_decay", _ns_data_retention_decay, _acc_data_retention_decay)
    var _acc_governance_compliance_score: Float64 = 0.0
    var _t0_governance_compliance_score = perf_counter_ns()
    for _ in range(N):
        _acc_governance_compliance_score += governance_compliance_score(0.5, 0.5, 0.5, 0.5)
    var _t1_governance_compliance_score = perf_counter_ns()
    var _ns_governance_compliance_score = Float64(_t1_governance_compliance_score - _t0_governance_compliance_score) / Float64(N)
    print("MOJO_TIMING security_governance::governance_compliance_score", _ns_governance_compliance_score, _acc_governance_compliance_score)
