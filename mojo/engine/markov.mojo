"""
markov.mojo — Markov chain library. Zero Python imports.
For stochastic modeling and decision processes.

Public API:
  struct MarkovChain — discrete-time Markov chain with transition matrix
    __init__            — create chain with n_states
    set_transition      — set P(from→to)
    get_transition      — get P(from→to)
    set_state           — set current state
    get_state           — get current state
    step                — take one stochastic step
    simulate            — run n steps, return state history
    steady_state        — compute stationary distribution (power iteration)
    expected_visits     — expected visits to each state over n steps
    absorption_probability — probability of reaching absorbing state
    mean_first_passage  — mean steps to reach target from each state
"""
from std.random import random_float64
from std.math import abs as fabs


# ── MarkovChain struct ────────────────────────────────────────────────────────


struct MarkovChain(Copyable, Movable):
    """Discrete-time Markov chain with n_states.

    Transition matrix stored as List[List[Float64]] where
    matrix[i][j] = P(transition from state i to state j).
    """

    var n_states: Int
    var matrix: List[List[Float64]]
    var current_state: Int

    def __init__(out self, n_states: Int):
        """Create a Markov chain with n_states. All transitions initialized to 0."""
        self.n_states = n_states
        self.current_state = 0
        self.matrix = List[List[Float64]]()
        for i in range(n_states):
            var row = List[Float64]()
            for j in range(n_states):
                row.append(0.0)
            self.matrix.append(row^)

    def set_transition(mut self, from_s: Int, to_s: Int, prob: Float64):
        """Set transition probability P(from_s → to_s)."""
        if from_s >= 0 and from_s < self.n_states and to_s >= 0 and to_s < self.n_states:
            self.matrix[from_s][to_s] = prob

    def get_transition(self, from_s: Int, to_s: Int) -> Float64:
        """Get transition probability P(from_s → to_s)."""
        if from_s >= 0 and from_s < self.n_states and to_s >= 0 and to_s < self.n_states:
            return self.matrix[from_s][to_s]
        return 0.0

    def set_state(mut self, state: Int):
        """Set the current state."""
        if state >= 0 and state < self.n_states:
            self.current_state = state

    def get_state(self) -> Int:
        """Get the current state."""
        return self.current_state

    def step(mut self) -> Int:
        """Take one stochastic step from current state.

        Uses random_float64() to sample from the transition probabilities
        of the current state row. Returns the new state.
        """
        var row = self.matrix[self.current_state].copy()
        var u = random_float64()
        var cumulative: Float64 = 0.0
        for j in range(self.n_states):
            cumulative += row[j]
            if u <= cumulative:
                self.current_state = j
                return j
        # Fallback to last state (rounding)
        self.current_state = self.n_states - 1
        return self.n_states - 1

    def simulate(mut self, steps: Int) -> List[Int]:
        """Run n steps from current state, return state history.

        Returns a list of length steps+1 (initial state + n transitions).
        """
        var history = List[Int]()
        history.append(self.current_state)
        for i in range(steps):
            var next_state = self.step()
            history.append(next_state)
        return history^

    def steady_state(self) -> List[Float64]:
        """Compute stationary distribution using power iteration.

        Iterates π = π * P until convergence (or max 1000 iterations).
        Returns probability vector of length n_states.
        """
        var n = self.n_states
        if n == 0:
            return List[Float64]()

        # Start with uniform distribution
        var pi = List[Float64]()
        for i in range(n):
            pi.append(1.0 / Float64(n))

        var max_iter = 1000
        var tol: Float64 = 1e-10

        for iteration in range(max_iter):
            # π_new = π * P  (row vector times transition matrix)
            var pi_new = List[Float64]()
            for j in range(n):
                var s: Float64 = 0.0
                for i in range(n):
                    s += pi[i] * self.matrix[i][j]
                pi_new.append(s)

            # Normalize
            var total: Float64 = 0.0
            for i in range(n):
                total += pi_new[i]
            if total > 0.0:
                for i in range(n):
                    pi_new[i] = pi_new[i] / total

            # Check convergence
            var max_diff: Float64 = 0.0
            for i in range(n):
                var diff = fabs(pi_new[i] - pi[i])
                if diff > max_diff:
                    max_diff = diff

            pi = pi_new^
            if max_diff < tol:
                break

        return pi^

    def expected_visits(self, steps: Int) -> List[Float64]:
        """Compute expected number of visits to each state over n steps.

        Uses matrix multiplication of the transition matrix to accumulate
        visit probabilities starting from the current state.

        Returns list of length n_states with expected visit counts.
        """
        var n = self.n_states
        var visits = List[Float64]()
        for i in range(n):
            visits.append(0.0)

        if n == 0 or steps <= 0:
            return visits^

        # Start with probability 1 at current state
        var prob = List[Float64]()
        for i in range(n):
            prob.append(0.0)
        prob[self.current_state] = 1.0

        # Accumulate visit probabilities over each step
        for i in range(n):
            visits[i] += prob[i]

        for step in range(steps):
            # prob_new = prob * P
            var prob_new = List[Float64]()
            for j in range(n):
                var s: Float64 = 0.0
                for i in range(n):
                    s += prob[i] * self.matrix[i][j]
                prob_new.append(s)
            prob = prob_new^
            for i in range(n):
                visits[i] += prob[i]

        return visits^

    def absorption_probability(self, absorbing_state: Int, start_state: Int) -> Float64:
        """Compute probability of eventually reaching absorbing_state from start_state.

        Uses iterative value computation. An absorbing state has self-transition = 1.
        If the absorbing state is reachable, probability converges to the true value.

        Args:
            absorbing_state: Target absorbing state index.
            start_state:     Starting state index.

        Returns:
            Probability of absorption (0.0 to 1.0).
        """
        var n = self.n_states
        if n == 0:
            return 0.0
        if absorbing_state < 0 or absorbing_state >= n:
            return 0.0
        if start_state < 0 or start_state >= n:
            return 0.0
        if start_state == absorbing_state:
            return 1.0

        # Iterative computation: p[i] = probability of reaching absorbing from i
        var prob = List[Float64]()
        for i in range(n):
            if i == absorbing_state:
                prob.append(1.0)
            else:
                prob.append(0.0)

        var max_iter = 1000
        var tol: Float64 = 1e-10

        for iteration in range(max_iter):
            var max_diff: Float64 = 0.0
            var new_prob = List[Float64]()
            for i in range(n):
                if i == absorbing_state:
                    new_prob.append(1.0)
                    continue
                # p[i] = sum_j P(i,j) * p[j]
                var s: Float64 = 0.0
                for j in range(n):
                    s += self.matrix[i][j] * prob[j]
                new_prob.append(s)
                var diff = fabs(s - prob[i])
                if diff > max_diff:
                    max_diff = diff
            prob = new_prob^
            if max_diff < tol:
                break

        return prob[start_state]

    def mean_first_passage(self, target: Int) -> List[Float64]:
        """Compute mean first passage time to target from each state.

        For each state i ≠ target, solves:
          m[i] = 1 + sum_{j≠target} P(i,j) * m[j]
        where m[target] = 0.

        Uses iterative (Gauss-Seidel-like) computation.

        Args:
            target: Target state index.

        Returns:
            List of length n_states with mean passage times.
            m[target] = 0, m[i] = expected steps from i to target.
        """
        var n = self.n_states
        var m = List[Float64]()
        for i in range(n):
            m.append(0.0)

        if n == 0 or target < 0 or target >= n:
            return m^

        # Initialize non-target states with an estimate
        for i in range(n):
            if i != target:
                m[i] = Float64(n)  # initial guess

        var max_iter = 2000
        var tol: Float64 = 1e-8

        for iteration in range(max_iter):
            var max_diff: Float64 = 0.0
            for i in range(n):
                if i == target:
                    continue
                # m[i] = 1 + sum_{j≠target} P(i,j) * m[j]
                var s: Float64 = 1.0
                for j in range(n):
                    if j != target:
                        s += self.matrix[i][j] * m[j]
                var diff = fabs(s - m[i])
                if diff > max_diff:
                    max_diff = diff
                m[i] = s
            if max_diff < tol:
                break

        return m^

    def is_ergodic(self) -> Bool:
        """Check if chain is ergodic (all states reachable from all states).

        Uses reachability check via BFS from each state.
        """
        var n = self.n_states
        if n <= 1:
            return True

        for start in range(n):
            # BFS from start
            var visited = List[Bool]()
            for i in range(n):
                visited.append(False)
            visited[start] = True
            var queue = List[Int]()
            queue.append(start)
            var head = 0
            while head < len(queue):
                var curr = queue[head]
                head += 1
                for j in range(n):
                    if not visited[j] and self.matrix[curr][j] > 0.0:
                        visited[j] = True
                        queue.append(j)
            # Check all reachable
            for i in range(n):
                if not visited[i]:
                    return False
        return True
