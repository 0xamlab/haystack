"""bench_hybrid_reasoning.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hybrid_reasoning import ml_simulation_blend, optimization_objective_gate, rule_violation_penalty, simulation_rollout_value, ml_confidence_simulation_cost, counterfactual_reasoning_score, symbolic_constraint_score, reasoning_chain_coherence, hybrid_uncertainty_estimate, meta_reasoning_switch
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

    var _acc_ml_simulation_blend: Float64 = 0.0
    var _t0_ml_simulation_blend = perf_counter_ns()
    for _ in range(N):
        _acc_ml_simulation_blend += ml_simulation_blend(0.5, 0.5, 0.5)
    var _t1_ml_simulation_blend = perf_counter_ns()
    var _ns_ml_simulation_blend = Float64(_t1_ml_simulation_blend - _t0_ml_simulation_blend) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::ml_simulation_blend", _ns_ml_simulation_blend, _acc_ml_simulation_blend)
    var _acc_optimization_objective_gate: Float64 = 0.0
    var _t0_optimization_objective_gate = perf_counter_ns()
    for _ in range(N):
        _acc_optimization_objective_gate += optimization_objective_gate(0.5, 0.5, 0.5)
    var _t1_optimization_objective_gate = perf_counter_ns()
    var _ns_optimization_objective_gate = Float64(_t1_optimization_objective_gate - _t0_optimization_objective_gate) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::optimization_objective_gate", _ns_optimization_objective_gate, _acc_optimization_objective_gate)
    var _acc_rule_violation_penalty: Float64 = 0.0
    var _t0_rule_violation_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_rule_violation_penalty += rule_violation_penalty(0.5, 0.5, 0.5)
    var _t1_rule_violation_penalty = perf_counter_ns()
    var _ns_rule_violation_penalty = Float64(_t1_rule_violation_penalty - _t0_rule_violation_penalty) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::rule_violation_penalty", _ns_rule_violation_penalty, _acc_rule_violation_penalty)
    var _acc_simulation_rollout_value: Float64 = 0.0
    var _t0_simulation_rollout_value = perf_counter_ns()
    for _ in range(N):
        _acc_simulation_rollout_value += simulation_rollout_value(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_simulation_rollout_value = perf_counter_ns()
    var _ns_simulation_rollout_value = Float64(_t1_simulation_rollout_value - _t0_simulation_rollout_value) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::simulation_rollout_value", _ns_simulation_rollout_value, _acc_simulation_rollout_value)
    var _acc_ml_confidence_simulation_cost: Float64 = 0.0
    var _t0_ml_confidence_simulation_cost = perf_counter_ns()
    for _ in range(N):
        _acc_ml_confidence_simulation_cost += ml_confidence_simulation_cost(0.5, 0.5, 0.5)
    var _t1_ml_confidence_simulation_cost = perf_counter_ns()
    var _ns_ml_confidence_simulation_cost = Float64(_t1_ml_confidence_simulation_cost - _t0_ml_confidence_simulation_cost) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::ml_confidence_simulation_cost", _ns_ml_confidence_simulation_cost, _acc_ml_confidence_simulation_cost)
    var _acc_counterfactual_reasoning_score: Float64 = 0.0
    var _t0_counterfactual_reasoning_score = perf_counter_ns()
    for _ in range(N):
        _acc_counterfactual_reasoning_score += counterfactual_reasoning_score(0.5, 0.5, 0.5)
    var _t1_counterfactual_reasoning_score = perf_counter_ns()
    var _ns_counterfactual_reasoning_score = Float64(_t1_counterfactual_reasoning_score - _t0_counterfactual_reasoning_score) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::counterfactual_reasoning_score", _ns_counterfactual_reasoning_score, _acc_counterfactual_reasoning_score)
    var _acc_symbolic_constraint_score: Float64 = 0.0
    var _t0_symbolic_constraint_score = perf_counter_ns()
    for _ in range(N):
        _acc_symbolic_constraint_score += symbolic_constraint_score(0.5, 0.5, 0.5)
    var _t1_symbolic_constraint_score = perf_counter_ns()
    var _ns_symbolic_constraint_score = Float64(_t1_symbolic_constraint_score - _t0_symbolic_constraint_score) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::symbolic_constraint_score", _ns_symbolic_constraint_score, _acc_symbolic_constraint_score)
    var _acc_reasoning_chain_coherence: Float64 = 0.0
    var _t0_reasoning_chain_coherence = perf_counter_ns()
    for _ in range(N):
        _acc_reasoning_chain_coherence += reasoning_chain_coherence(0.5, 0.5, 0.5)
    var _t1_reasoning_chain_coherence = perf_counter_ns()
    var _ns_reasoning_chain_coherence = Float64(_t1_reasoning_chain_coherence - _t0_reasoning_chain_coherence) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::reasoning_chain_coherence", _ns_reasoning_chain_coherence, _acc_reasoning_chain_coherence)
    var _acc_hybrid_uncertainty_estimate: Float64 = 0.0
    var _t0_hybrid_uncertainty_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_hybrid_uncertainty_estimate += hybrid_uncertainty_estimate(0.5, 0.5, 0.5)
    var _t1_hybrid_uncertainty_estimate = perf_counter_ns()
    var _ns_hybrid_uncertainty_estimate = Float64(_t1_hybrid_uncertainty_estimate - _t0_hybrid_uncertainty_estimate) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::hybrid_uncertainty_estimate", _ns_hybrid_uncertainty_estimate, _acc_hybrid_uncertainty_estimate)
    var _acc_meta_reasoning_switch: Float64 = 0.0
    var _t0_meta_reasoning_switch = perf_counter_ns()
    for _ in range(N):
        _acc_meta_reasoning_switch += meta_reasoning_switch(0.5, 0.5, 0.5, 0.5)
    var _t1_meta_reasoning_switch = perf_counter_ns()
    var _ns_meta_reasoning_switch = Float64(_t1_meta_reasoning_switch - _t0_meta_reasoning_switch) / Float64(N)
    print("MOJO_TIMING hybrid_reasoning::meta_reasoning_switch", _ns_meta_reasoning_switch, _acc_meta_reasoning_switch)
