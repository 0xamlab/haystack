"""bench_decision_ml_fusion.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from decision_ml_fusion import ml_to_simulation_weight, simulation_to_objective, expected_value_under_model, regret_from_prediction, counterfactual_utility, policy_gradient_advantage, reward_shaping_potential, multi_objective_scalarize, model_confidence_gate, adaptive_exploration_rate
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

    var _acc_ml_to_simulation_weight: Float64 = 0.0
    var _t0_ml_to_simulation_weight = perf_counter_ns()
    for _ in range(N):
        _acc_ml_to_simulation_weight += ml_to_simulation_weight(0.5, 0.5)
    var _t1_ml_to_simulation_weight = perf_counter_ns()
    var _ns_ml_to_simulation_weight = Float64(_t1_ml_to_simulation_weight - _t0_ml_to_simulation_weight) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::ml_to_simulation_weight", _ns_ml_to_simulation_weight, _acc_ml_to_simulation_weight)
    var _acc_simulation_to_objective: Float64 = 0.0
    var _t0_simulation_to_objective = perf_counter_ns()
    for _ in range(N):
        _acc_simulation_to_objective += simulation_to_objective(0.5, 0.5, 0.5)
    var _t1_simulation_to_objective = perf_counter_ns()
    var _ns_simulation_to_objective = Float64(_t1_simulation_to_objective - _t0_simulation_to_objective) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::simulation_to_objective", _ns_simulation_to_objective, _acc_simulation_to_objective)
    var _acc_expected_value_under_model: Float64 = 0.0
    var _t0_expected_value_under_model = perf_counter_ns()
    for _ in range(N):
        _acc_expected_value_under_model += expected_value_under_model(0.5, 0.5, 0.5, 0.5)
    var _t1_expected_value_under_model = perf_counter_ns()
    var _ns_expected_value_under_model = Float64(_t1_expected_value_under_model - _t0_expected_value_under_model) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::expected_value_under_model", _ns_expected_value_under_model, _acc_expected_value_under_model)
    var _acc_regret_from_prediction: Float64 = 0.0
    var _t0_regret_from_prediction = perf_counter_ns()
    for _ in range(N):
        _acc_regret_from_prediction += regret_from_prediction(0.5, 0.5, 0.5)
    var _t1_regret_from_prediction = perf_counter_ns()
    var _ns_regret_from_prediction = Float64(_t1_regret_from_prediction - _t0_regret_from_prediction) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::regret_from_prediction", _ns_regret_from_prediction, _acc_regret_from_prediction)
    var _acc_counterfactual_utility: Float64 = 0.0
    var _t0_counterfactual_utility = perf_counter_ns()
    for _ in range(N):
        _acc_counterfactual_utility += counterfactual_utility(0.5, 0.5)
    var _t1_counterfactual_utility = perf_counter_ns()
    var _ns_counterfactual_utility = Float64(_t1_counterfactual_utility - _t0_counterfactual_utility) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::counterfactual_utility", _ns_counterfactual_utility, _acc_counterfactual_utility)
    var _acc_policy_gradient_advantage: Float64 = 0.0
    var _t0_policy_gradient_advantage = perf_counter_ns()
    for _ in range(N):
        _acc_policy_gradient_advantage += policy_gradient_advantage(0.5, 0.5)
    var _t1_policy_gradient_advantage = perf_counter_ns()
    var _ns_policy_gradient_advantage = Float64(_t1_policy_gradient_advantage - _t0_policy_gradient_advantage) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::policy_gradient_advantage", _ns_policy_gradient_advantage, _acc_policy_gradient_advantage)
    var _acc_reward_shaping_potential: Float64 = 0.0
    var _t0_reward_shaping_potential = perf_counter_ns()
    for _ in range(N):
        _acc_reward_shaping_potential += reward_shaping_potential(0.5, 0.5, 0.5)
    var _t1_reward_shaping_potential = perf_counter_ns()
    var _ns_reward_shaping_potential = Float64(_t1_reward_shaping_potential - _t0_reward_shaping_potential) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::reward_shaping_potential", _ns_reward_shaping_potential, _acc_reward_shaping_potential)
    var _acc_multi_objective_scalarize: Float64 = 0.0
    var _t0_multi_objective_scalarize = perf_counter_ns()
    for _ in range(N):
        _acc_multi_objective_scalarize += multi_objective_scalarize(0.5, 0.5, 0.5, 0.5)
    var _t1_multi_objective_scalarize = perf_counter_ns()
    var _ns_multi_objective_scalarize = Float64(_t1_multi_objective_scalarize - _t0_multi_objective_scalarize) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::multi_objective_scalarize", _ns_multi_objective_scalarize, _acc_multi_objective_scalarize)
    var _acc_model_confidence_gate: Float64 = 0.0
    var _t0_model_confidence_gate = perf_counter_ns()
    for _ in range(N):
        _acc_model_confidence_gate += model_confidence_gate(0.5, 0.5, 0.5, 0.5)
    var _t1_model_confidence_gate = perf_counter_ns()
    var _ns_model_confidence_gate = Float64(_t1_model_confidence_gate - _t0_model_confidence_gate) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::model_confidence_gate", _ns_model_confidence_gate, _acc_model_confidence_gate)
    var _acc_adaptive_exploration_rate: Float64 = 0.0
    var _t0_adaptive_exploration_rate = perf_counter_ns()
    for _ in range(N):
        _acc_adaptive_exploration_rate += adaptive_exploration_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_adaptive_exploration_rate = perf_counter_ns()
    var _ns_adaptive_exploration_rate = Float64(_t1_adaptive_exploration_rate - _t0_adaptive_exploration_rate) / Float64(N)
    print("MOJO_TIMING decision_ml_fusion::adaptive_exploration_rate", _ns_adaptive_exploration_rate, _acc_adaptive_exploration_rate)
