"""bench_scipy_optimize_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scipy_optimize_ops import bfgs_hessian_update_term, conjugate_gradient_beta_fr, conjugate_gradient_beta_pr, armijo_condition, wolfe_curvature_condition, golden_section_midpoint, newton_step, secant_step, bisection_midpoint, trust_region_step_norm
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

    var _acc_bfgs_hessian_update_term: Float64 = 0.0
    var _t0_bfgs_hessian_update_term = perf_counter_ns()
    for _ in range(N):
        _acc_bfgs_hessian_update_term += bfgs_hessian_update_term(0.5, 0.5, 0.5)
    var _t1_bfgs_hessian_update_term = perf_counter_ns()
    var _ns_bfgs_hessian_update_term = Float64(_t1_bfgs_hessian_update_term - _t0_bfgs_hessian_update_term) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::bfgs_hessian_update_term", _ns_bfgs_hessian_update_term, _acc_bfgs_hessian_update_term)
    var _acc_conjugate_gradient_beta_fr: Float64 = 0.0
    var _t0_conjugate_gradient_beta_fr = perf_counter_ns()
    for _ in range(N):
        _acc_conjugate_gradient_beta_fr += conjugate_gradient_beta_fr(0.5, 0.5)
    var _t1_conjugate_gradient_beta_fr = perf_counter_ns()
    var _ns_conjugate_gradient_beta_fr = Float64(_t1_conjugate_gradient_beta_fr - _t0_conjugate_gradient_beta_fr) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::conjugate_gradient_beta_fr", _ns_conjugate_gradient_beta_fr, _acc_conjugate_gradient_beta_fr)
    var _acc_conjugate_gradient_beta_pr: Float64 = 0.0
    var _t0_conjugate_gradient_beta_pr = perf_counter_ns()
    for _ in range(N):
        _acc_conjugate_gradient_beta_pr += conjugate_gradient_beta_pr(0.5, 0.5, 0.5)
    var _t1_conjugate_gradient_beta_pr = perf_counter_ns()
    var _ns_conjugate_gradient_beta_pr = Float64(_t1_conjugate_gradient_beta_pr - _t0_conjugate_gradient_beta_pr) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::conjugate_gradient_beta_pr", _ns_conjugate_gradient_beta_pr, _acc_conjugate_gradient_beta_pr)
    var _acc_armijo_condition: Float64 = 0.0
    var _t0_armijo_condition = perf_counter_ns()
    for _ in range(N):
        _acc_armijo_condition += armijo_condition(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_armijo_condition = perf_counter_ns()
    var _ns_armijo_condition = Float64(_t1_armijo_condition - _t0_armijo_condition) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::armijo_condition", _ns_armijo_condition, _acc_armijo_condition)
    var _acc_wolfe_curvature_condition: Float64 = 0.0
    var _t0_wolfe_curvature_condition = perf_counter_ns()
    for _ in range(N):
        _acc_wolfe_curvature_condition += wolfe_curvature_condition(0.5, 0.5, 0.5)
    var _t1_wolfe_curvature_condition = perf_counter_ns()
    var _ns_wolfe_curvature_condition = Float64(_t1_wolfe_curvature_condition - _t0_wolfe_curvature_condition) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::wolfe_curvature_condition", _ns_wolfe_curvature_condition, _acc_wolfe_curvature_condition)
    var _acc_golden_section_midpoint: Float64 = 0.0
    var _t0_golden_section_midpoint = perf_counter_ns()
    for _ in range(N):
        _acc_golden_section_midpoint += golden_section_midpoint(0.5, 0.5, 0.5)
    var _t1_golden_section_midpoint = perf_counter_ns()
    var _ns_golden_section_midpoint = Float64(_t1_golden_section_midpoint - _t0_golden_section_midpoint) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::golden_section_midpoint", _ns_golden_section_midpoint, _acc_golden_section_midpoint)
    var _acc_newton_step: Float64 = 0.0
    var _t0_newton_step = perf_counter_ns()
    for _ in range(N):
        _acc_newton_step += newton_step(0.5, 0.5)
    var _t1_newton_step = perf_counter_ns()
    var _ns_newton_step = Float64(_t1_newton_step - _t0_newton_step) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::newton_step", _ns_newton_step, _acc_newton_step)
    var _acc_secant_step: Float64 = 0.0
    var _t0_secant_step = perf_counter_ns()
    for _ in range(N):
        _acc_secant_step += secant_step(0.5, 0.5, 0.5, 0.5)
    var _t1_secant_step = perf_counter_ns()
    var _ns_secant_step = Float64(_t1_secant_step - _t0_secant_step) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::secant_step", _ns_secant_step, _acc_secant_step)
    var _acc_bisection_midpoint: Float64 = 0.0
    var _t0_bisection_midpoint = perf_counter_ns()
    for _ in range(N):
        _acc_bisection_midpoint += bisection_midpoint(0.5, 0.5)
    var _t1_bisection_midpoint = perf_counter_ns()
    var _ns_bisection_midpoint = Float64(_t1_bisection_midpoint - _t0_bisection_midpoint) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::bisection_midpoint", _ns_bisection_midpoint, _acc_bisection_midpoint)
    var _acc_trust_region_step_norm: Float64 = 0.0
    var _t0_trust_region_step_norm = perf_counter_ns()
    for _ in range(N):
        _acc_trust_region_step_norm += trust_region_step_norm(0.5, 0.5, 0.5)
    var _t1_trust_region_step_norm = perf_counter_ns()
    var _ns_trust_region_step_norm = Float64(_t1_trust_region_step_norm - _t0_trust_region_step_norm) / Float64(N)
    print("MOJO_TIMING scipy_optimize_ops::trust_region_step_norm", _ns_trust_region_step_norm, _acc_trust_region_step_norm)
