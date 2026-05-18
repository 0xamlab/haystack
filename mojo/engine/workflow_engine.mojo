"""
workflow_engine.mojo — AI workflow engine: DAG execution, retries, branching, conditional flows.
Zero Python imports.

Public API:
  dag_node_ready_score           — whether a DAG node is ready to execute
  retry_backoff_delay            — exponential backoff delay for retries
  conditional_branch_score       — score for selecting a conditional branch
  pipeline_stage_throughput      — effective throughput of a pipeline stage
  workflow_completion_fraction   — fraction of DAG nodes completed
  step_timeout_remaining_ms      — remaining time before step timeout
  dependency_resolution_order    — topological priority score for a node
  parallel_step_efficiency       — efficiency of parallel step execution
  workflow_cost_accumulator      — accumulated cost for workflow so far
  chain_output_compatibility     — compatibility of step output for next step
"""
from std.math import sqrt, log, exp


fn dag_node_ready_score(
    n_dependencies: Float64, n_completed_dependencies: Float64,
    blocked_by_resource: Float64
) -> Float64:
    """Whether a DAG node is ready to execute.

    Returns 1.0 if all deps complete and no resource block.

    Args:
        n_dependencies: Total dependencies for this node.
        n_completed_dependencies: Dependencies that have completed.
        blocked_by_resource: 1.0 if blocked by resource constraint.

    Returns:
        1.0 if ready to execute, 0.0 if not ready.
    """
    if blocked_by_resource > 0.5:
        return 0.0
    if n_dependencies <= 0.0:
        return 1.0
    if n_completed_dependencies >= n_dependencies:
        return 1.0
    return 0.0


fn retry_backoff_delay(
    attempt_number: Float64, base_delay_ms: Float64,
    max_delay_ms: Float64, jitter_factor: Float64
) -> Float64:
    """Exponential backoff delay for workflow step retries.

    delay = min(base × 2^attempt, max) × (1 + jitter)

    Args:
        attempt_number: Retry attempt count (0-indexed).
        base_delay_ms: Base delay in milliseconds.
        max_delay_ms: Maximum delay cap.
        jitter_factor: Fractional jitter to add (0 = no jitter).

    Returns:
        Retry delay in milliseconds.
    """
    var delay = base_delay_ms * exp(attempt_number * 0.693)  # 2^attempt
    if delay > max_delay_ms:
        delay = max_delay_ms
    return delay * (1.0 + jitter_factor * 0.5)


fn conditional_branch_score(
    condition_probability: Float64, branch_value: Float64,
    branch_cost: Float64
) -> Float64:
    """Score for selecting a conditional branch in a workflow.

    score = P(condition) × value - cost

    Args:
        condition_probability: Probability that branch condition is true.
        branch_value: Expected value if branch executes.
        branch_cost: Cost of executing this branch.

    Returns:
        Expected net value of this branch.
    """
    return condition_probability * branch_value - branch_cost


fn pipeline_stage_throughput(
    stage_compute_ms: Float64, stage_io_ms: Float64,
    parallelism: Float64
) -> Float64:
    """Effective throughput of a pipeline stage.

    throughput = parallelism / max(compute, io) latency

    Args:
        stage_compute_ms: Compute time for this stage.
        stage_io_ms: IO time for this stage.
        parallelism: Degree of parallelism.

    Returns:
        Throughput in requests per millisecond.
    """
    var bottleneck = stage_compute_ms if stage_compute_ms > stage_io_ms else stage_io_ms
    if bottleneck <= 0.0:
        return parallelism
    return parallelism / bottleneck


fn workflow_completion_fraction(
    completed_nodes: Float64, total_nodes: Float64,
    failed_nodes: Float64
) -> Float64:
    """Fraction of DAG workflow successfully completed.

    Args:
        completed_nodes: Successfully completed nodes.
        total_nodes: Total nodes in DAG.
        failed_nodes: Nodes that failed (not retrying).

    Returns:
        Completion fraction (0–1; does not count failed as complete).
    """
    if total_nodes <= 0.0:
        return 1.0
    return (completed_nodes - failed_nodes) / total_nodes


fn step_timeout_remaining_ms(
    step_start_ms: Float64, current_ms: Float64,
    timeout_budget_ms: Float64
) -> Float64:
    """Remaining time before a workflow step times out.

    Args:
        step_start_ms: Step start timestamp.
        current_ms: Current timestamp.
        timeout_budget_ms: Total timeout budget for this step.

    Returns:
        Remaining milliseconds (negative = timed out).
    """
    var elapsed = current_ms - step_start_ms
    return timeout_budget_ms - elapsed


fn dependency_resolution_order(
    n_downstream_nodes: Float64, critical_path_length: Float64,
    node_compute_cost: Float64
) -> Float64:
    """Topological priority score for scheduling DAG nodes.

    Priority = downstream_count × critical_path / compute_cost

    Args:
        n_downstream_nodes: Number of nodes depending on this one.
        critical_path_length: Length of critical path through this node.
        node_compute_cost: Compute cost of this node.

    Returns:
        Scheduling priority (higher = schedule first).
    """
    if node_compute_cost <= 0.0:
        return n_downstream_nodes * critical_path_length
    return n_downstream_nodes * critical_path_length / node_compute_cost


fn parallel_step_efficiency(
    sequential_time_ms: Float64, parallel_time_ms: Float64,
    n_workers: Float64
) -> Float64:
    """Efficiency of parallel step execution vs sequential.

    Amdahl efficiency = sequential / (parallel × workers)

    Args:
        sequential_time_ms: Time to run step sequentially.
        parallel_time_ms: Observed parallel execution time.
        n_workers: Number of parallel workers.

    Returns:
        Parallel efficiency (1 = perfect scaling).
    """
    if parallel_time_ms <= 0.0 or n_workers <= 0.0:
        return 1.0
    return sequential_time_ms / (parallel_time_ms * n_workers)


fn workflow_cost_accumulator(
    previous_cost: Float64, step_compute_cost: Float64,
    step_io_cost: Float64, step_api_cost: Float64
) -> Float64:
    """Accumulated cost for workflow execution so far.

    Args:
        previous_cost: Total cost accumulated before this step.
        step_compute_cost: Compute cost for this step.
        step_io_cost: IO/storage cost for this step.
        step_api_cost: External API call cost for this step.

    Returns:
        Updated total cost.
    """
    return previous_cost + step_compute_cost + step_io_cost + step_api_cost


fn chain_output_compatibility(
    output_schema_version: Float64, next_step_schema_version: Float64,
    output_type_code: Float64, expected_type_code: Float64
) -> Float64:
    """Compatibility of a step's output for the next step's input.

    Args:
        output_schema_version: Schema version of current step output.
        next_step_schema_version: Schema version expected by next step.
        output_type_code: Type code of output.
        expected_type_code: Type code expected by next step.

    Returns:
        Compatibility score (1.0 = fully compatible, 0.0 = incompatible).
    """
    var type_match = 1.0 if output_type_code == expected_type_code else 0.0
    var version_diff = output_schema_version - next_step_schema_version
    if version_diff < 0.0:
        version_diff = -version_diff
    var version_compat = exp(-version_diff)
    return type_match * version_compat
