"""
agent_runtime.mojo — Agent/tool execution runtime: planning, retry, state, cost.
Zero Python imports.

Public API:
  tool_call_cost_estimate        — latency + token cost of a tool call
  retry_should_attempt           — retry decision given attempt count
  plan_step_dependency_ready     — check if plan step dependencies met
  action_value_estimate          — estimated value of agent action
  tool_selection_score           — tool selection ranking score
  memory_retrieval_relevance     — agent memory relevance score
  context_window_budget          — remaining tokens in context
  agent_step_reward              — intermediate reward for agent step
  structured_output_match        — validate structured output schema
  agent_cost_budget_remaining    — remaining cost budget for agent run
"""
from std.math import sqrt, log, exp


fn tool_call_cost_estimate(
    tool_latency_ms: Float64, input_tokens: Float64,
    output_tokens: Float64, cost_per_1k_tokens: Float64
) -> Float64:
    """Estimated cost of one tool call (latency + token cost).

    Args:
        tool_latency_ms: Expected tool execution time (ms).
        input_tokens: Tokens in tool call input.
        output_tokens: Tokens in tool response.
        cost_per_1k_tokens: Cost per 1000 tokens ($).

    Returns:
        Total estimated cost in $ + latency (normalised).
    """
    var token_cost = (input_tokens + output_tokens) * cost_per_1k_tokens / 1000.0
    var latency_cost = tool_latency_ms / 1000.0  # seconds as proxy
    return token_cost + latency_cost * 0.001  # weight latency


fn retry_should_attempt(
    attempt: Float64, max_attempts: Float64,
    last_error_type: Float64
) -> Float64:
    """Decide whether to retry a failed tool call.

    Returns 1.0 if should retry, 0.0 if give up.

    error_type: 1=transient (retry), 2=permanent (don't retry).

    Args:
        attempt: Current attempt number (1-indexed).
        max_attempts: Maximum allowed attempts.
        last_error_type: 1.0=transient, 2.0=permanent error.

    Returns:
        1.0 if retry, 0.0 if stop.
    """
    if attempt >= max_attempts:
        return 0.0
    if last_error_type >= 2.0:
        return 0.0
    return 1.0


fn plan_step_dependency_ready(
    completed_steps_mask: Float64, required_steps_mask: Float64
) -> Float64:
    """Check if all required predecessor steps are completed.

    Uses bitmask representation (simplified to float).

    Args:
        completed_steps_mask: Bitmask of completed step IDs.
        required_steps_mask: Bitmask of required predecessor IDs.

    Returns:
        1.0 if all dependencies satisfied, 0.0 otherwise.
    """
    # Simplified: check if completed_mask covers required_mask
    var covered = Float64(Int64(completed_steps_mask) & Int64(required_steps_mask))
    if covered == required_steps_mask:
        return 1.0
    return 0.0


fn action_value_estimate(
    immediate_reward: Float64, future_value: Float64,
    discount: Float64, steps_remaining: Float64
) -> Float64:
    """Expected value of agent action: R + γ^t × V(s').

    Args:
        immediate_reward: Immediate reward from action.
        future_value: Estimated future state value.
        discount: Discount factor γ.
        steps_remaining: Steps until terminal state.

    Returns:
        Action value estimate.
    """
    return immediate_reward + exp(steps_remaining * log(discount if discount > 0.0 else 1e-300)) * future_value


fn tool_selection_score(
    tool_relevance: Float64, tool_cost: Float64,
    tool_reliability: Float64
) -> Float64:
    """Score for selecting which tool to call next.

    score = relevance × reliability / cost

    Args:
        tool_relevance: Semantic relevance to current goal.
        tool_cost: Estimated cost (tokens + latency).
        tool_reliability: Historical success rate.

    Returns:
        Tool selection score (higher = prefer this tool).
    """
    var denom = tool_cost + 1e-6
    return tool_relevance * tool_reliability / denom


fn memory_retrieval_relevance(
    query_embed_dot: Float64, query_norm: Float64,
    memory_norm: Float64, recency_weight: Float64
) -> Float64:
    """Agent memory relevance: cosine similarity + recency bonus.

    score = cos(query, memory) × recency_weight

    Args:
        query_embed_dot: Dot product of query and memory embeddings.
        query_norm: Query embedding norm.
        memory_norm: Memory embedding norm.
        recency_weight: Recency decay factor (1 = fresh, 0 = old).

    Returns:
        Memory relevance score.
    """
    var denom = query_norm * memory_norm
    if denom <= 0.0:
        return 0.0
    return (query_embed_dot / denom) * recency_weight


fn context_window_budget(
    max_tokens: Float64, used_tokens: Float64,
    reserved_output_tokens: Float64
) -> Float64:
    """Remaining context window budget for additional inputs.

    Args:
        max_tokens: Maximum context window size.
        used_tokens: Tokens already in context.
        reserved_output_tokens: Tokens reserved for generation.

    Returns:
        Available input tokens remaining.
    """
    var remaining = max_tokens - used_tokens - reserved_output_tokens
    if remaining < 0.0:
        return 0.0
    return remaining


fn agent_step_reward(
    goal_progress: Float64, step_cost: Float64,
    constraint_violation: Float64, penalty: Float64
) -> Float64:
    """Intermediate reward for one agent step.

    reward = progress - cost - constraint_penalty

    Args:
        goal_progress: Fractional progress toward goal (0–1 delta).
        step_cost: Cost of this step (normalised to [0,1]).
        constraint_violation: 1.0 if constraint violated, else 0.
        penalty: Penalty for constraint violations.

    Returns:
        Step reward.
    """
    return goal_progress - step_cost - constraint_violation * penalty


fn structured_output_match(
    output_schema_hash: Float64, actual_output_hash: Float64
) -> Float64:
    """Validate structured output matches expected schema.

    Returns 1.0 if match, 0.0 if mismatch.

    Args:
        output_schema_hash: Hash of expected output schema.
        actual_output_hash: Hash of actual model output structure.

    Returns:
        1.0 if schema matches.
    """
    if output_schema_hash == actual_output_hash:
        return 1.0
    return 0.0


fn agent_cost_budget_remaining(
    total_budget: Float64, spent_tokens: Float64,
    spent_tool_calls: Float64, cost_per_token: Float64,
    cost_per_tool_call: Float64
) -> Float64:
    """Remaining cost budget for agent run.

    Args:
        total_budget: Total cost budget ($).
        spent_tokens: Tokens consumed so far.
        spent_tool_calls: Tool calls made so far.
        cost_per_token: Cost per token ($).
        cost_per_tool_call: Average cost per tool call ($).

    Returns:
        Remaining budget ($).
    """
    var spent = spent_tokens * cost_per_token + spent_tool_calls * cost_per_tool_call
    var remaining = total_budget - spent
    if remaining < 0.0:
        return 0.0
    return remaining
