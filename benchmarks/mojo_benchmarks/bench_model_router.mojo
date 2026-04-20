"""bench_model_router.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_router import capability_match_score, model_load_score, fallback_trigger_score, ensemble_weight, hybrid_pipeline_stage_score, model_selection_utility, routing_uncertainty, latency_tier_assignment, model_freshness_score, shadow_routing_fraction
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

    var _acc_capability_match_score: Float64 = 0.0
    var _t0_capability_match_score = perf_counter_ns()
    for _ in range(N):
        _acc_capability_match_score += capability_match_score(0.5, 0.5, 0.5, 0.5)
    var _t1_capability_match_score = perf_counter_ns()
    var _ns_capability_match_score = Float64(_t1_capability_match_score - _t0_capability_match_score) / Float64(N)
    print("MOJO_TIMING model_router::capability_match_score", _ns_capability_match_score, _acc_capability_match_score)
    var _acc_model_load_score: Float64 = 0.0
    var _t0_model_load_score = perf_counter_ns()
    for _ in range(N):
        _acc_model_load_score += model_load_score(0.5, 0.5, 0.5)
    var _t1_model_load_score = perf_counter_ns()
    var _ns_model_load_score = Float64(_t1_model_load_score - _t0_model_load_score) / Float64(N)
    print("MOJO_TIMING model_router::model_load_score", _ns_model_load_score, _acc_model_load_score)
    var _acc_fallback_trigger_score: Float64 = 0.0
    var _t0_fallback_trigger_score = perf_counter_ns()
    for _ in range(N):
        _acc_fallback_trigger_score += fallback_trigger_score(0.5, 0.5, 0.5, 0.5)
    var _t1_fallback_trigger_score = perf_counter_ns()
    var _ns_fallback_trigger_score = Float64(_t1_fallback_trigger_score - _t0_fallback_trigger_score) / Float64(N)
    print("MOJO_TIMING model_router::fallback_trigger_score", _ns_fallback_trigger_score, _acc_fallback_trigger_score)
    var _acc_ensemble_weight: Float64 = 0.0
    var _t0_ensemble_weight = perf_counter_ns()
    for _ in range(N):
        _acc_ensemble_weight += ensemble_weight(0.5, 0.5, 0.5, 0.5)
    var _t1_ensemble_weight = perf_counter_ns()
    var _ns_ensemble_weight = Float64(_t1_ensemble_weight - _t0_ensemble_weight) / Float64(N)
    print("MOJO_TIMING model_router::ensemble_weight", _ns_ensemble_weight, _acc_ensemble_weight)
    var _acc_hybrid_pipeline_stage_score: Float64 = 0.0
    var _t0_hybrid_pipeline_stage_score = perf_counter_ns()
    for _ in range(N):
        _acc_hybrid_pipeline_stage_score += hybrid_pipeline_stage_score(0.5, 0.5, 0.5)
    var _t1_hybrid_pipeline_stage_score = perf_counter_ns()
    var _ns_hybrid_pipeline_stage_score = Float64(_t1_hybrid_pipeline_stage_score - _t0_hybrid_pipeline_stage_score) / Float64(N)
    print("MOJO_TIMING model_router::hybrid_pipeline_stage_score", _ns_hybrid_pipeline_stage_score, _acc_hybrid_pipeline_stage_score)
    var _acc_model_selection_utility: Float64 = 0.0
    var _t0_model_selection_utility = perf_counter_ns()
    for _ in range(N):
        _acc_model_selection_utility += model_selection_utility(0.5, 0.5, 0.5)
    var _t1_model_selection_utility = perf_counter_ns()
    var _ns_model_selection_utility = Float64(_t1_model_selection_utility - _t0_model_selection_utility) / Float64(N)
    print("MOJO_TIMING model_router::model_selection_utility", _ns_model_selection_utility, _acc_model_selection_utility)
    var _acc_routing_uncertainty: Float64 = 0.0
    var _t0_routing_uncertainty = perf_counter_ns()
    for _ in range(N):
        _acc_routing_uncertainty += routing_uncertainty(0.5, 0.5)
    var _t1_routing_uncertainty = perf_counter_ns()
    var _ns_routing_uncertainty = Float64(_t1_routing_uncertainty - _t0_routing_uncertainty) / Float64(N)
    print("MOJO_TIMING model_router::routing_uncertainty", _ns_routing_uncertainty, _acc_routing_uncertainty)
    var _acc_latency_tier_assignment: Float64 = 0.0
    var _t0_latency_tier_assignment = perf_counter_ns()
    for _ in range(N):
        _acc_latency_tier_assignment += latency_tier_assignment(0.5, 0.5, 0.5)
    var _t1_latency_tier_assignment = perf_counter_ns()
    var _ns_latency_tier_assignment = Float64(_t1_latency_tier_assignment - _t0_latency_tier_assignment) / Float64(N)
    print("MOJO_TIMING model_router::latency_tier_assignment", _ns_latency_tier_assignment, _acc_latency_tier_assignment)
    var _acc_model_freshness_score: Float64 = 0.0
    var _t0_model_freshness_score = perf_counter_ns()
    for _ in range(N):
        _acc_model_freshness_score += model_freshness_score(0.5, 0.5, 0.5)
    var _t1_model_freshness_score = perf_counter_ns()
    var _ns_model_freshness_score = Float64(_t1_model_freshness_score - _t0_model_freshness_score) / Float64(N)
    print("MOJO_TIMING model_router::model_freshness_score", _ns_model_freshness_score, _acc_model_freshness_score)
    var _acc_shadow_routing_fraction: Float64 = 0.0
    var _t0_shadow_routing_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_shadow_routing_fraction += shadow_routing_fraction(0.5, 0.5, 0.5)
    var _t1_shadow_routing_fraction = perf_counter_ns()
    var _ns_shadow_routing_fraction = Float64(_t1_shadow_routing_fraction - _t0_shadow_routing_fraction) / Float64(N)
    print("MOJO_TIMING model_router::shadow_routing_fraction", _ns_shadow_routing_fraction, _acc_shadow_routing_fraction)
