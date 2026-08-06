"""
fault_tolerance.mojo — Fault-tolerant training/serving: resume, recovery, determinism.
Zero Python imports.

Public API:
  checkpoint_interval_optimal    — optimal checkpoint frequency
  recovery_cost_estimate         — cost of recovering from failure
  deterministic_seed             — deterministic seed for replay
  partial_batch_replay_loss      — loss correction for partial batch
  node_failure_probability       — failure probability estimate
  mtbf_checkpoint_frequency      — MTBF-optimal checkpoint interval
  gradient_staleness_factor      — staleness penalty for delayed grads
  elastic_training_scale         — elastic training worker count
  failure_detection_latency      — time to detect node failure
  replication_overhead           — storage overhead for fault tolerance
"""
from std.math import sqrt, log, exp


def checkpoint_interval_optimal(
    checkpoint_cost_steps: Float64, failure_rate_per_step: Float64
) -> Float64:
    """Optimal checkpoint interval minimising expected wasted work.

    interval* = sqrt(2 × checkpoint_cost / failure_rate)

    Args:
        checkpoint_cost_steps: Steps lost to checkpointing.
        failure_rate_per_step: Probability of failure per step.

    Returns:
        Optimal steps between checkpoints.
    """
    if failure_rate_per_step <= 0.0:
        return 1e6
    return sqrt(2.0 * checkpoint_cost_steps / failure_rate_per_step)


def recovery_cost_estimate(
    steps_since_checkpoint: Float64, step_compute_cost: Float64,
    checkpoint_load_cost: Float64
) -> Float64:
    """Cost of recovering from failure at current step.

    cost = checkpoint_load + replay_steps × step_cost

    Args:
        steps_since_checkpoint: Steps that must be replayed.
        step_compute_cost: Compute cost per step.
        checkpoint_load_cost: Time to load checkpoint.

    Returns:
        Total recovery cost (in step-equivalents).
    """
    return checkpoint_load_cost + steps_since_checkpoint * step_compute_cost


def deterministic_seed(
    base_seed: Float64, step: Float64, rank: Float64
) -> Float64:
    """Deterministic seed for reproducible training replay.

    seed = base_seed + step × large_prime + rank

    Args:
        base_seed: Global random seed.
        step: Training step.
        rank: Worker rank.

    Returns:
        Deterministic seed for this step/rank.
    """
    return base_seed + step * 1000003.0 + rank


def partial_batch_replay_loss(
    full_batch_loss: Float64, processed_samples: Float64,
    batch_size: Float64
) -> Float64:
    """Loss contribution from partially processed batch before failure.

    partial_loss = full_loss × (processed / batch_size)

    Args:
        full_batch_loss: Expected full batch loss.
        processed_samples: Samples processed before failure.
        batch_size: Full batch size.

    Returns:
        Partial batch loss estimate.
    """
    if batch_size <= 0.0:
        return 0.0
    return full_batch_loss * processed_samples / batch_size


def node_failure_probability(
    n_nodes: Float64, mtbf_hours: Float64,
    job_duration_hours: Float64
) -> Float64:
    """Probability of at least one node failure during job.

    P(failure) = 1 - exp(-n_nodes × duration / MTBF)

    Args:
        n_nodes: Number of nodes in job.
        mtbf_hours: Mean time between failures per node.
        job_duration_hours: Expected job duration.

    Returns:
        Failure probability (0–1).
    """
    if mtbf_hours <= 0.0:
        return 1.0
    return 1.0 - exp(-n_nodes * job_duration_hours / mtbf_hours)


def mtbf_checkpoint_frequency(
    mtbf_hours: Float64, steps_per_hour: Float64
) -> Float64:
    """MTBF-based checkpoint frequency recommendation.

    checkpoint every sqrt(MTBF_steps) steps.

    Args:
        mtbf_hours: Mean time between failures (hours).
        steps_per_hour: Training throughput (steps/hour).

    Returns:
        Recommended checkpoint interval (steps).
    """
    var mtbf_steps = mtbf_hours * steps_per_hour
    return sqrt(mtbf_steps)


def gradient_staleness_factor(
    staleness: Float64, decay_rate: Float64
) -> Float64:
    """Staleness penalty for delayed gradient updates (async training).

    factor = exp(-decay_rate × staleness)

    Args:
        staleness: Number of steps gradient is stale.
        decay_rate: Staleness decay (higher = penalise stale grads more).

    Returns:
        Gradient weighting factor (1.0 = fresh, lower = stale).
    """
    return exp(-decay_rate * staleness)


def elastic_training_scale(
    current_workers: Float64, target_workers: Float64,
    lr: Float64
) -> Float64:
    """Learning rate scaling for elastic training worker count changes.

    Linear scaling: lr_new = lr × (new_workers / old_workers)

    Args:
        current_workers: Current active workers.
        target_workers: New worker count after elasticity event.
        lr: Current learning rate.

    Returns:
        Adjusted learning rate.
    """
    if current_workers <= 0.0:
        return lr
    return lr * target_workers / current_workers


def failure_detection_latency(
    heartbeat_interval_ms: Float64, missed_heartbeats: Float64
) -> Float64:
    """Time to detect node failure from missed heartbeats.

    latency = heartbeat_interval × missed_count

    Args:
        heartbeat_interval_ms: Time between heartbeats.
        missed_heartbeats: Consecutive missed heartbeats to declare failure.

    Returns:
        Failure detection latency (ms).
    """
    return heartbeat_interval_ms * missed_heartbeats


def replication_overhead(
    checkpoint_bytes: Float64, replication_factor: Float64,
    total_storage_bytes: Float64
) -> Float64:
    """Storage overhead fraction from checkpoint replication.

    overhead = (replication_factor - 1) × checkpoint / total

    Args:
        checkpoint_bytes: Size of one checkpoint.
        replication_factor: Number of replicas (2–3 typical).
        total_storage_bytes: Total available storage.

    Returns:
        Storage overhead fraction.
    """
    if total_storage_bytes <= 0.0:
        return 0.0
    return (replication_factor - 1.0) * checkpoint_bytes / total_storage_bytes
