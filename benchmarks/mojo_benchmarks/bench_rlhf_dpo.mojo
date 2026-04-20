"""bench_rlhf_dpo.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from rlhf_dpo import dpo_loss, ipo_loss, orpo_ratio, ppo_clip_objective, reward_model_score, kl_penalty_term, advantage_gae, grpo_group_advantage, sft_loss_token, preference_margin_loss
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

    var _acc_dpo_loss: Float64 = 0.0
    var _t0_dpo_loss = perf_counter_ns()
    for _ in range(N):
        _acc_dpo_loss += dpo_loss(0.5, 0.5, 0.5)
    var _t1_dpo_loss = perf_counter_ns()
    var _ns_dpo_loss = Float64(_t1_dpo_loss - _t0_dpo_loss) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::dpo_loss", _ns_dpo_loss, _acc_dpo_loss)
    var _acc_ipo_loss: Float64 = 0.0
    var _t0_ipo_loss = perf_counter_ns()
    for _ in range(N):
        _acc_ipo_loss += ipo_loss(0.5, 0.5, 0.5)
    var _t1_ipo_loss = perf_counter_ns()
    var _ns_ipo_loss = Float64(_t1_ipo_loss - _t0_ipo_loss) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::ipo_loss", _ns_ipo_loss, _acc_ipo_loss)
    var _acc_orpo_ratio: Float64 = 0.0
    var _t0_orpo_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_orpo_ratio += orpo_ratio(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_orpo_ratio = perf_counter_ns()
    var _ns_orpo_ratio = Float64(_t1_orpo_ratio - _t0_orpo_ratio) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::orpo_ratio", _ns_orpo_ratio, _acc_orpo_ratio)
    var _acc_ppo_clip_objective: Float64 = 0.0
    var _t0_ppo_clip_objective = perf_counter_ns()
    for _ in range(N):
        _acc_ppo_clip_objective += ppo_clip_objective(0.5, 0.5, 0.5)
    var _t1_ppo_clip_objective = perf_counter_ns()
    var _ns_ppo_clip_objective = Float64(_t1_ppo_clip_objective - _t0_ppo_clip_objective) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::ppo_clip_objective", _ns_ppo_clip_objective, _acc_ppo_clip_objective)
    var _acc_reward_model_score: Float64 = 0.0
    var _t0_reward_model_score = perf_counter_ns()
    for _ in range(N):
        _acc_reward_model_score += reward_model_score(0.5, 0.5)
    var _t1_reward_model_score = perf_counter_ns()
    var _ns_reward_model_score = Float64(_t1_reward_model_score - _t0_reward_model_score) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::reward_model_score", _ns_reward_model_score, _acc_reward_model_score)
    var _acc_kl_penalty_term: Float64 = 0.0
    var _t0_kl_penalty_term = perf_counter_ns()
    for _ in range(N):
        _acc_kl_penalty_term += kl_penalty_term(0.5, 0.5, 0.5)
    var _t1_kl_penalty_term = perf_counter_ns()
    var _ns_kl_penalty_term = Float64(_t1_kl_penalty_term - _t0_kl_penalty_term) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::kl_penalty_term", _ns_kl_penalty_term, _acc_kl_penalty_term)
    var _acc_advantage_gae: Float64 = 0.0
    var _t0_advantage_gae = perf_counter_ns()
    for _ in range(N):
        _acc_advantage_gae += advantage_gae(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_advantage_gae = perf_counter_ns()
    var _ns_advantage_gae = Float64(_t1_advantage_gae - _t0_advantage_gae) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::advantage_gae", _ns_advantage_gae, _acc_advantage_gae)
    var _acc_grpo_group_advantage: Float64 = 0.0
    var _t0_grpo_group_advantage = perf_counter_ns()
    for _ in range(N):
        _acc_grpo_group_advantage += grpo_group_advantage(0.5, 0.5, 0.5)
    var _t1_grpo_group_advantage = perf_counter_ns()
    var _ns_grpo_group_advantage = Float64(_t1_grpo_group_advantage - _t0_grpo_group_advantage) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::grpo_group_advantage", _ns_grpo_group_advantage, _acc_grpo_group_advantage)
    var _acc_sft_loss_token: Float64 = 0.0
    var _t0_sft_loss_token = perf_counter_ns()
    for _ in range(N):
        _acc_sft_loss_token += sft_loss_token(0.5)
    var _t1_sft_loss_token = perf_counter_ns()
    var _ns_sft_loss_token = Float64(_t1_sft_loss_token - _t0_sft_loss_token) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::sft_loss_token", _ns_sft_loss_token, _acc_sft_loss_token)
    var _acc_preference_margin_loss: Float64 = 0.0
    var _t0_preference_margin_loss = perf_counter_ns()
    for _ in range(N):
        _acc_preference_margin_loss += preference_margin_loss(0.5, 0.5, 0.5)
    var _t1_preference_margin_loss = perf_counter_ns()
    var _ns_preference_margin_loss = Float64(_t1_preference_margin_loss - _t0_preference_margin_loss) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::preference_margin_loss", _ns_preference_margin_loss, _acc_preference_margin_loss)
