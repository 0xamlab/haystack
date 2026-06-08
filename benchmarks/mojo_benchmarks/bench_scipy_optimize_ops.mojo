"""bench_scipy_optimize_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scipy_optimize_ops import bfgs_hessian_update_term, conjugate_gradient_beta_fr, conjugate_gradient_beta_pr, armijo_condition, wolfe_curvature_condition, golden_section_midpoint, newton_step, secant_step, bisection_midpoint, trust_region_step_norm
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

    var _acc_bfgs_hessian_update_term: Float64 = 0.0
    var _t0_bfgs_hessian_update_term = perf_counter_ns()
    for _ in range(N):
        _acc_bfgs_hessian_update_term += bfgs_hessian_update_term(0.5, 0.5, 0.5)
    var _t1_bfgs_hessian_update_term = perf_counter_ns()
    var _ns_bfgs_hessian_update_term = Float64(_t1_bfgs_hessian_update_term - _t0_bfgs_hessian_update_term) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::bfgs_hessian_update_term", _ns_bfgs_hessian_update_term, _acc_bfgs_hessian_update_term)
    var _result_bfgs_hessian_update_term = bfgs_hessian_update_term(0.5, 0.5, 0.5)
    var _summary_bfgs_hessian_update_term = _summary_float64(_result_bfgs_hessian_update_term)
    print("MOJO_RESULT scipy_optimize_ops::bfgs_hessian_update_term", _summary_bfgs_hessian_update_term)
    var _acc_conjugate_gradient_beta_fr: Float64 = 0.0
    var _t0_conjugate_gradient_beta_fr = perf_counter_ns()
    for _ in range(N):
        _acc_conjugate_gradient_beta_fr += conjugate_gradient_beta_fr(0.5, 0.5)
    var _t1_conjugate_gradient_beta_fr = perf_counter_ns()
    var _ns_conjugate_gradient_beta_fr = Float64(_t1_conjugate_gradient_beta_fr - _t0_conjugate_gradient_beta_fr) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::conjugate_gradient_beta_fr", _ns_conjugate_gradient_beta_fr, _acc_conjugate_gradient_beta_fr)
    var _result_conjugate_gradient_beta_fr = conjugate_gradient_beta_fr(0.5, 0.5)
    var _summary_conjugate_gradient_beta_fr = _summary_float64(_result_conjugate_gradient_beta_fr)
    print("MOJO_RESULT scipy_optimize_ops::conjugate_gradient_beta_fr", _summary_conjugate_gradient_beta_fr)
    var _acc_conjugate_gradient_beta_pr: Float64 = 0.0
    var _t0_conjugate_gradient_beta_pr = perf_counter_ns()
    for _ in range(N):
        _acc_conjugate_gradient_beta_pr += conjugate_gradient_beta_pr(0.5, 0.5, 0.5)
    var _t1_conjugate_gradient_beta_pr = perf_counter_ns()
    var _ns_conjugate_gradient_beta_pr = Float64(_t1_conjugate_gradient_beta_pr - _t0_conjugate_gradient_beta_pr) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::conjugate_gradient_beta_pr", _ns_conjugate_gradient_beta_pr, _acc_conjugate_gradient_beta_pr)
    var _result_conjugate_gradient_beta_pr = conjugate_gradient_beta_pr(0.5, 0.5, 0.5)
    var _summary_conjugate_gradient_beta_pr = _summary_float64(_result_conjugate_gradient_beta_pr)
    print("MOJO_RESULT scipy_optimize_ops::conjugate_gradient_beta_pr", _summary_conjugate_gradient_beta_pr)
    var _acc_armijo_condition: Float64 = 0.0
    var _t0_armijo_condition = perf_counter_ns()
    for _ in range(N):
        _acc_armijo_condition += armijo_condition(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_armijo_condition = perf_counter_ns()
    var _ns_armijo_condition = Float64(_t1_armijo_condition - _t0_armijo_condition) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::armijo_condition", _ns_armijo_condition, _acc_armijo_condition)
    var _result_armijo_condition = armijo_condition(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_armijo_condition = _summary_float64(_result_armijo_condition)
    print("MOJO_RESULT scipy_optimize_ops::armijo_condition", _summary_armijo_condition)
    var _acc_wolfe_curvature_condition: Float64 = 0.0
    var _t0_wolfe_curvature_condition = perf_counter_ns()
    for _ in range(N):
        _acc_wolfe_curvature_condition += wolfe_curvature_condition(0.5, 0.5, 0.5)
    var _t1_wolfe_curvature_condition = perf_counter_ns()
    var _ns_wolfe_curvature_condition = Float64(_t1_wolfe_curvature_condition - _t0_wolfe_curvature_condition) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::wolfe_curvature_condition", _ns_wolfe_curvature_condition, _acc_wolfe_curvature_condition)
    var _result_wolfe_curvature_condition = wolfe_curvature_condition(0.5, 0.5, 0.5)
    var _summary_wolfe_curvature_condition = _summary_float64(_result_wolfe_curvature_condition)
    print("MOJO_RESULT scipy_optimize_ops::wolfe_curvature_condition", _summary_wolfe_curvature_condition)
    var _acc_golden_section_midpoint: Float64 = 0.0
    var _t0_golden_section_midpoint = perf_counter_ns()
    for _ in range(N):
        _acc_golden_section_midpoint += golden_section_midpoint(0.5, 0.5, 0.5)
    var _t1_golden_section_midpoint = perf_counter_ns()
    var _ns_golden_section_midpoint = Float64(_t1_golden_section_midpoint - _t0_golden_section_midpoint) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::golden_section_midpoint", _ns_golden_section_midpoint, _acc_golden_section_midpoint)
    var _result_golden_section_midpoint = golden_section_midpoint(0.5, 0.5, 0.5)
    var _summary_golden_section_midpoint = _summary_float64(_result_golden_section_midpoint)
    print("MOJO_RESULT scipy_optimize_ops::golden_section_midpoint", _summary_golden_section_midpoint)
    var _acc_newton_step: Float64 = 0.0
    var _t0_newton_step = perf_counter_ns()
    for _ in range(N):
        _acc_newton_step += newton_step(0.5, 0.5)
    var _t1_newton_step = perf_counter_ns()
    var _ns_newton_step = Float64(_t1_newton_step - _t0_newton_step) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::newton_step", _ns_newton_step, _acc_newton_step)
    var _result_newton_step = newton_step(0.5, 0.5)
    var _summary_newton_step = _summary_float64(_result_newton_step)
    print("MOJO_RESULT scipy_optimize_ops::newton_step", _summary_newton_step)
    var _acc_secant_step: Float64 = 0.0
    var _t0_secant_step = perf_counter_ns()
    for _ in range(N):
        _acc_secant_step += secant_step(0.5, 0.5, 0.5, 0.5)
    var _t1_secant_step = perf_counter_ns()
    var _ns_secant_step = Float64(_t1_secant_step - _t0_secant_step) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::secant_step", _ns_secant_step, _acc_secant_step)
    var _result_secant_step = secant_step(0.5, 0.5, 0.5, 0.5)
    var _summary_secant_step = _summary_float64(_result_secant_step)
    print("MOJO_RESULT scipy_optimize_ops::secant_step", _summary_secant_step)
    var _acc_bisection_midpoint: Float64 = 0.0
    var _t0_bisection_midpoint = perf_counter_ns()
    for _ in range(N):
        _acc_bisection_midpoint += bisection_midpoint(0.5, 0.5)
    var _t1_bisection_midpoint = perf_counter_ns()
    var _ns_bisection_midpoint = Float64(_t1_bisection_midpoint - _t0_bisection_midpoint) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::bisection_midpoint", _ns_bisection_midpoint, _acc_bisection_midpoint)
    var _result_bisection_midpoint = bisection_midpoint(0.5, 0.5)
    var _summary_bisection_midpoint = _summary_float64(_result_bisection_midpoint)
    print("MOJO_RESULT scipy_optimize_ops::bisection_midpoint", _summary_bisection_midpoint)
    var _acc_trust_region_step_norm: Float64 = 0.0
    var _t0_trust_region_step_norm = perf_counter_ns()
    for _ in range(N):
        _acc_trust_region_step_norm += trust_region_step_norm(0.5, 0.5, 0.5)
    var _t1_trust_region_step_norm = perf_counter_ns()
    var _ns_trust_region_step_norm = Float64(_t1_trust_region_step_norm - _t0_trust_region_step_norm) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::trust_region_step_norm", _ns_trust_region_step_norm, _acc_trust_region_step_norm)
    var _result_trust_region_step_norm = trust_region_step_norm(0.5, 0.5, 0.5)
    var _summary_trust_region_step_norm = _summary_float64(_result_trust_region_step_norm)
    print("MOJO_RESULT scipy_optimize_ops::trust_region_step_norm", _summary_trust_region_step_norm)
