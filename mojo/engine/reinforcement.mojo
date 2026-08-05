"""
reinforcement.mojo — Reinforcement learning algorithms. Zero Python imports.

Replaces gymnasium/stable-baselines with pure Mojo implementations for
Q-learning, SARSA, value iteration, policy extraction, epsilon-greedy
action selection, policy evaluation, TD error, and discounted return.

Public API:
  q_learning           — Q-learning off-policy
  sarsa                — SARSA on-policy
  value_iteration      — Value iteration for MDPs
  policy_from_q        — Greedy policy from Q-table
  epsilon_greedy_action — ε-greedy action selection
  policy_evaluation    — Evaluate a fixed policy
  td_error             — TD(0) error
  discounted_return    — Discounted cumulative return
"""
from std.random import random_float64


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _argmax(vals: List[Float64]) -> Int:
    """Return index of maximum value."""
    var n = len(vals)
    if n == 0:
        return 0
    var best = 0
    var best_val = vals[0]
    for i in range(1, n):
        if vals[i] > best_val:
            best_val = vals[i]
            best = i
    return best


fn _init_q(n_states: Int, n_actions: Int) -> List[List[Float64]]:
    """Initialize Q-table to zeros."""
    var Q = List[List[Float64]]()
    for _ in range(n_states):
        var row = List[Float64]()
        for _ in range(n_actions):
            row.append(0.0)
        Q.append(row^)
    return Q^


# ── Epsilon-greedy ────────────────────────────────────────────────────────────


fn epsilon_greedy_action(Q_state: List[Float64], epsilon: Float64) -> Int:
    """ε-greedy action selection."""
    var n = len(Q_state)
    if n == 0:
        return 0
    var r = random_float64()
    if r < epsilon:
        # Random action
        var idx_f = random_float64() * Float64(n)
        var idx = Int(idx_f)
        if idx >= n:
            idx = n - 1
        return idx
    return _argmax(Q_state)


# ── Q-learning ────────────────────────────────────────────────────────────────


fn q_learning(
    n_states: Int,
    n_actions: Int,
    rewards: List[List[Float64]],
    transitions: List[List[Int]],
    alpha: Float64,
    gamma: Float64,
    epsilon: Float64,
    n_episodes: Int,
) -> List[List[Float64]]:
    """Q-learning off-policy. Returns Q-table [n_states × n_actions].
    
    rewards[s][a] = reward for taking action a in state s.
    transitions[s][a] = next state for taking action a in state s.
    Terminal state: transitions to self with 0 reward.
    """
    # Untrusted n_states*n_actions is a memory weapon, so clamp the table to
    # what the payload actually contains; out-of-range reads below are
    # uncatchable aborts, so refuse degenerate shapes with an empty table.
    if n_states <= 0 or n_actions <= 0:
        return List[List[Float64]]()
    var ns = n_states
    if ns > len(rewards):
        ns = len(rewards)
    if ns > len(transitions):
        ns = len(transitions)
    var na = n_actions
    for s in range(ns):
        if len(rewards[s]) < na:
            na = len(rewards[s])
        if len(transitions[s]) < na:
            na = len(transitions[s])
    if ns <= 0 or na <= 0:
        return List[List[Float64]]()
    # Transition targets index the Q-table directly.
    for s in range(ns):
        for a in range(na):
            if transitions[s][a] < 0 or transitions[s][a] >= ns:
                return List[List[Float64]]()
    # Untrusted n_episodes drives iteration; clamp it.
    var episodes = n_episodes
    if episodes < 0:
        episodes = 0
    if episodes > 10000:
        episodes = 10000
    var Q = _init_q(ns, na)
    var terminal = ns - 1

    for _ in range(episodes):
        # Start from state 0
        var s = 0
        var steps = 0
        while s != terminal and steps < ns * 10:
            var a = epsilon_greedy_action(Q[s], epsilon)
            var r = rewards[s][a]
            var s_next = transitions[s][a]
            # Q-learning update: max over next actions
            var max_q_next = Q[s_next][0]
            for a2 in range(1, na):
                if Q[s_next][a2] > max_q_next:
                    max_q_next = Q[s_next][a2]
            Q[s][a] = Q[s][a] + alpha * (r + gamma * max_q_next - Q[s][a])
            s = s_next
            steps += 1

    return Q^


# ── SARSA ─────────────────────────────────────────────────────────────────────


fn sarsa(
    n_states: Int,
    n_actions: Int,
    rewards: List[List[Float64]],
    transitions: List[List[Int]],
    alpha: Float64,
    gamma: Float64,
    epsilon: Float64,
    n_episodes: Int,
) -> List[List[Float64]]:
    """SARSA on-policy. Returns Q-table [n_states × n_actions]."""
    # Untrusted n_states*n_actions is a memory weapon, so clamp the table to
    # what the payload actually contains; out-of-range reads below are
    # uncatchable aborts, so refuse degenerate shapes with an empty table.
    if n_states <= 0 or n_actions <= 0:
        return List[List[Float64]]()
    var ns = n_states
    if ns > len(rewards):
        ns = len(rewards)
    if ns > len(transitions):
        ns = len(transitions)
    var na = n_actions
    for s in range(ns):
        if len(rewards[s]) < na:
            na = len(rewards[s])
        if len(transitions[s]) < na:
            na = len(transitions[s])
    if ns <= 0 or na <= 0:
        return List[List[Float64]]()
    # Transition targets index the Q-table directly.
    for s in range(ns):
        for a in range(na):
            if transitions[s][a] < 0 or transitions[s][a] >= ns:
                return List[List[Float64]]()
    # Untrusted n_episodes drives iteration; clamp it.
    var episodes = n_episodes
    if episodes < 0:
        episodes = 0
    if episodes > 10000:
        episodes = 10000
    var Q = _init_q(ns, na)
    var terminal = ns - 1

    for _ in range(episodes):
        var s = 0
        var a = epsilon_greedy_action(Q[s], epsilon)
        var steps = 0
        while s != terminal and steps < ns * 10:
            var r = rewards[s][a]
            var s_next = transitions[s][a]
            var a_next = epsilon_greedy_action(Q[s_next], epsilon)
            Q[s][a] = Q[s][a] + alpha * (r + gamma * Q[s_next][a_next] - Q[s][a])
            s = s_next
            a = a_next
            steps += 1

    return Q^


# ── Value iteration ───────────────────────────────────────────────────────────


fn value_iteration(
    n_states: Int,
    n_actions: Int,
    rewards: List[List[Float64]],
    transitions: List[List[Int]],
    gamma: Float64,
    tol: Float64,
) -> List[Float64]:
    """Value iteration. Returns V[state]."""
    # Untrusted n_states is a memory weapon, so clamp it to what the payload
    # actually contains; out-of-range reads below are uncatchable aborts, so
    # refuse degenerate shapes with an empty result.
    if n_states <= 0 or n_actions <= 0:
        return List[Float64]()
    var ns = n_states
    if ns > len(rewards):
        ns = len(rewards)
    if ns > len(transitions):
        ns = len(transitions)
    var na = n_actions
    for s in range(ns):
        if len(rewards[s]) < na:
            na = len(rewards[s])
        if len(transitions[s]) < na:
            na = len(transitions[s])
    if ns <= 0 or na <= 0:
        return List[Float64]()
    # Transition targets index V directly.
    for s in range(ns):
        for a in range(na):
            if transitions[s][a] < 0 or transitions[s][a] >= ns:
                return List[Float64]()
    var V = List[Float64]()
    for _ in range(ns):
        V.append(0.0)

    var max_iter = 10000
    for _ in range(max_iter):
        var delta: Float64 = 0.0
        for s in range(ns):
            var best_val = rewards[s][0] + gamma * V[transitions[s][0]]
            for a in range(1, na):
                var val = rewards[s][a] + gamma * V[transitions[s][a]]
                if val > best_val:
                    best_val = val
            var diff = best_val - V[s]
            if diff < 0.0:
                diff = -diff
            if diff > delta:
                delta = diff
            V[s] = best_val
        if delta < tol:
            break

    return V^


# ── Policy extraction ─────────────────────────────────────────────────────────


fn policy_from_q(Q: List[List[Float64]]) -> List[Int]:
    """Greedy policy from Q-table: argmax over actions for each state."""
    var n_states = len(Q)
    var policy = List[Int]()
    for s in range(n_states):
        policy.append(_argmax(Q[s]))
    return policy^


# ── Policy evaluation ─────────────────────────────────────────────────────────


fn policy_evaluation(
    policy: List[Int],
    n_states: Int,
    rewards: List[List[Float64]],
    transitions: List[List[Int]],
    gamma: Float64,
    tol: Float64,
) -> List[Float64]:
    """Evaluate a fixed policy. Returns V."""
    # Same shape contract as value_iteration: untrusted n_states, untrusted policy
    # actions and untrusted transition targets all become array indexes below, and
    # out-of-range reads are uncatchable aborts, so clamp to what the payload contains
    # and refuse degenerate shapes with an empty result.
    var ns = n_states
    if ns > len(policy):
        ns = len(policy)
    if ns > len(rewards):
        ns = len(rewards)
    if ns > len(transitions):
        ns = len(transitions)
    if ns <= 0:
        return List[Float64]()
    for s in range(ns):
        var a = policy[s]
        if a < 0 or a >= len(rewards[s]) or a >= len(transitions[s]):
            return List[Float64]()
        # Transition targets index V directly.
        if transitions[s][a] < 0 or transitions[s][a] >= ns:
            return List[Float64]()

    var V = List[Float64]()
    for _ in range(ns):
        V.append(0.0)

    var max_iter = 10000
    for _ in range(max_iter):
        var delta: Float64 = 0.0
        for s in range(ns):
            var a = policy[s]
            var new_v = rewards[s][a] + gamma * V[transitions[s][a]]
            var diff = new_v - V[s]
            if diff < 0.0:
                diff = -diff
            if diff > delta:
                delta = diff
            V[s] = new_v
        if delta < tol:
            break

    return V^


# ── TD error ──────────────────────────────────────────────────────────────────


fn td_error(reward: Float64, gamma: Float64, v_next: Float64, v_current: Float64) -> Float64:
    """TD(0) error: r + γV(s') - V(s)."""
    return reward + gamma * v_next - v_current


# ── Discounted return ─────────────────────────────────────────────────────────


fn discounted_return(rewards: List[Float64], gamma: Float64) -> Float64:
    """G = Σ γ^t * r_t."""
    var G: Float64 = 0.0
    var n = len(rewards)
    var gamma_t: Float64 = 1.0
    for t in range(n):
        G += gamma_t * rewards[t]
        gamma_t *= gamma
    return G
