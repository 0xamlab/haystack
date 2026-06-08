"""bench_rlhf_dpo.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from rlhf_dpo import dpo_loss, ipo_loss, orpo_ratio, ppo_clip_objective, reward_model_score, kl_penalty_term, advantage_gae, grpo_group_advantage, sft_loss_token, preference_margin_loss
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

    var _acc_dpo_loss: Float64 = 0.0
    var _t0_dpo_loss = perf_counter_ns()
    for _ in range(N):
        _acc_dpo_loss += dpo_loss(0.5, 0.5, 0.5)
    var _t1_dpo_loss = perf_counter_ns()
    var _ns_dpo_loss = Float64(_t1_dpo_loss - _t0_dpo_loss) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::dpo_loss", _ns_dpo_loss, _acc_dpo_loss)
    var _result_dpo_loss = dpo_loss(0.5, 0.5, 0.5)
    var _summary_dpo_loss = _summary_float64(_result_dpo_loss)
    print("MOJO_RESULT rlhf_dpo::dpo_loss", _summary_dpo_loss)
    var _acc_ipo_loss: Float64 = 0.0
    var _t0_ipo_loss = perf_counter_ns()
    for _ in range(N):
        _acc_ipo_loss += ipo_loss(0.5, 0.5, 0.5)
    var _t1_ipo_loss = perf_counter_ns()
    var _ns_ipo_loss = Float64(_t1_ipo_loss - _t0_ipo_loss) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::ipo_loss", _ns_ipo_loss, _acc_ipo_loss)
    var _result_ipo_loss = ipo_loss(0.5, 0.5, 0.5)
    var _summary_ipo_loss = _summary_float64(_result_ipo_loss)
    print("MOJO_RESULT rlhf_dpo::ipo_loss", _summary_ipo_loss)
    var _acc_orpo_ratio: Float64 = 0.0
    var _t0_orpo_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_orpo_ratio += orpo_ratio(-0.2, -1.2, 5.0, 5.0, 0.1)
    var _t1_orpo_ratio = perf_counter_ns()
    var _ns_orpo_ratio = Float64(_t1_orpo_ratio - _t0_orpo_ratio) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::orpo_ratio", _ns_orpo_ratio, _acc_orpo_ratio)
    var _result_orpo_ratio = orpo_ratio(-0.2, -1.2, 5.0, 5.0, 0.1)
    var _summary_orpo_ratio = _summary_float64(_result_orpo_ratio)
    print("MOJO_RESULT rlhf_dpo::orpo_ratio", _summary_orpo_ratio)
    var _acc_ppo_clip_objective: Float64 = 0.0
    var _t0_ppo_clip_objective = perf_counter_ns()
    for _ in range(N):
        _acc_ppo_clip_objective += ppo_clip_objective(0.5, 0.5, 0.5)
    var _t1_ppo_clip_objective = perf_counter_ns()
    var _ns_ppo_clip_objective = Float64(_t1_ppo_clip_objective - _t0_ppo_clip_objective) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::ppo_clip_objective", _ns_ppo_clip_objective, _acc_ppo_clip_objective)
    var _result_ppo_clip_objective = ppo_clip_objective(0.5, 0.5, 0.5)
    var _summary_ppo_clip_objective = _summary_float64(_result_ppo_clip_objective)
    print("MOJO_RESULT rlhf_dpo::ppo_clip_objective", _summary_ppo_clip_objective)
    var _acc_reward_model_score: Float64 = 0.0
    var _t0_reward_model_score = perf_counter_ns()
    for _ in range(N):
        _acc_reward_model_score += reward_model_score(0.5, 0.5)
    var _t1_reward_model_score = perf_counter_ns()
    var _ns_reward_model_score = Float64(_t1_reward_model_score - _t0_reward_model_score) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::reward_model_score", _ns_reward_model_score, _acc_reward_model_score)
    var _result_reward_model_score = reward_model_score(0.5, 0.5)
    var _summary_reward_model_score = _summary_float64(_result_reward_model_score)
    print("MOJO_RESULT rlhf_dpo::reward_model_score", _summary_reward_model_score)
    var _acc_kl_penalty_term: Float64 = 0.0
    var _t0_kl_penalty_term = perf_counter_ns()
    for _ in range(N):
        _acc_kl_penalty_term += kl_penalty_term(0.5, 0.5, 0.5)
    var _t1_kl_penalty_term = perf_counter_ns()
    var _ns_kl_penalty_term = Float64(_t1_kl_penalty_term - _t0_kl_penalty_term) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::kl_penalty_term", _ns_kl_penalty_term, _acc_kl_penalty_term)
    var _result_kl_penalty_term = kl_penalty_term(0.5, 0.5, 0.5)
    var _summary_kl_penalty_term = _summary_float64(_result_kl_penalty_term)
    print("MOJO_RESULT rlhf_dpo::kl_penalty_term", _summary_kl_penalty_term)
    var _acc_advantage_gae: Float64 = 0.0
    var _t0_advantage_gae = perf_counter_ns()
    for _ in range(N):
        _acc_advantage_gae += advantage_gae(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_advantage_gae = perf_counter_ns()
    var _ns_advantage_gae = Float64(_t1_advantage_gae - _t0_advantage_gae) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::advantage_gae", _ns_advantage_gae, _acc_advantage_gae)
    var _result_advantage_gae = advantage_gae(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_advantage_gae = _summary_float64(_result_advantage_gae)
    print("MOJO_RESULT rlhf_dpo::advantage_gae", _summary_advantage_gae)
    var _acc_grpo_group_advantage: Float64 = 0.0
    var _t0_grpo_group_advantage = perf_counter_ns()
    for _ in range(N):
        _acc_grpo_group_advantage += grpo_group_advantage(0.5, 0.5, 0.5)
    var _t1_grpo_group_advantage = perf_counter_ns()
    var _ns_grpo_group_advantage = Float64(_t1_grpo_group_advantage - _t0_grpo_group_advantage) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::grpo_group_advantage", _ns_grpo_group_advantage, _acc_grpo_group_advantage)
    var _result_grpo_group_advantage = grpo_group_advantage(0.5, 0.5, 0.5)
    var _summary_grpo_group_advantage = _summary_float64(_result_grpo_group_advantage)
    print("MOJO_RESULT rlhf_dpo::grpo_group_advantage", _summary_grpo_group_advantage)
    var _acc_sft_loss_token: Float64 = 0.0
    var _t0_sft_loss_token = perf_counter_ns()
    for _ in range(N):
        _acc_sft_loss_token += sft_loss_token(0.5)
    var _t1_sft_loss_token = perf_counter_ns()
    var _ns_sft_loss_token = Float64(_t1_sft_loss_token - _t0_sft_loss_token) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::sft_loss_token", _ns_sft_loss_token, _acc_sft_loss_token)
    var _result_sft_loss_token = sft_loss_token(0.5)
    var _summary_sft_loss_token = _summary_float64(_result_sft_loss_token)
    print("MOJO_RESULT rlhf_dpo::sft_loss_token", _summary_sft_loss_token)
    var _acc_preference_margin_loss: Float64 = 0.0
    var _t0_preference_margin_loss = perf_counter_ns()
    for _ in range(N):
        _acc_preference_margin_loss += preference_margin_loss(0.5, 0.5, 0.5)
    var _t1_preference_margin_loss = perf_counter_ns()
    var _ns_preference_margin_loss = Float64(_t1_preference_margin_loss - _t0_preference_margin_loss) / Float64(N)
    print("MOJO_TIMING rlhf_dpo::preference_margin_loss", _ns_preference_margin_loss, _acc_preference_margin_loss)
    var _result_preference_margin_loss = preference_margin_loss(0.5, 0.5, 0.5)
    var _summary_preference_margin_loss = _summary_float64(_result_preference_margin_loss)
    print("MOJO_RESULT rlhf_dpo::preference_margin_loss", _summary_preference_margin_loss)
