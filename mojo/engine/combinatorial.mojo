"""
combinatorial.mojo — Combinatorial optimization algorithms. Zero Python imports.

Replaces ortools basics with pure Mojo implementations of knapsack, TSP,
bin packing, assignment, max subarray, LIS, and coin change.

Public API:
  knapsack_01                    — 0/1 knapsack, returns selected indices
  knapsack_01_value              — 0/1 knapsack, returns max value
  tsp_greedy                     — nearest-neighbor TSP tour
  tsp_tour_length                — total tour length
  bin_packing_first_fit          — first-fit bin packing
  bin_packing_first_fit_decreasing — FFD bin packing
  assignment_greedy              — greedy assignment (row→col)
  max_subarray_sum               — Kadane's algorithm
  longest_increasing_subsequence — LIS length via patience sorting
  coin_change                    — minimum coins for amount
"""


# ── knapsack_01 ──────────────────────────────────────────────────────────────


fn knapsack_01(weights: List[Int], values: List[Int], capacity: Int) -> List[Int]:
    """0/1 Knapsack via DP. Returns list of selected item indices."""
    var n = len(weights)
    if n == 0 or capacity <= 0:
        return List[Int]()
    if len(values) != n:
        return List[Int]()
    for i in range(n):
        if weights[i] < 0:
            return List[Int]()  # negative weight corrupts DP/backtrack indices
    # Bound the DP allocation: capacity is untrusted caller input.
    if capacity > 1000000 or (n + 1) * (capacity + 1) > 10000000:
        return List[Int]()

    # DP table: (n+1) x (capacity+1)
    var dp = List[Int]()
    for _ in range((n + 1) * (capacity + 1)):
        dp.append(0)

    for i in range(1, n + 1):
        for w in range(capacity + 1):
            # Don't take item i-1
            dp[i * (capacity + 1) + w] = dp[(i - 1) * (capacity + 1) + w]
            # Take item i-1 if it fits
            if weights[i - 1] <= w:
                var with_item = dp[(i - 1) * (capacity + 1) + (w - weights[i - 1])] + values[i - 1]
                if with_item > dp[i * (capacity + 1) + w]:
                    dp[i * (capacity + 1) + w] = with_item

    # Backtrack to find selected items
    var selected = List[Int]()
    var w = capacity
    var i = n
    while i > 0 and w > 0:
        if dp[i * (capacity + 1) + w] != dp[(i - 1) * (capacity + 1) + w]:
            selected.append(i - 1)
            w -= weights[i - 1]
        i -= 1

    # Reverse to get ascending order
    var rev = List[Int]()
    var k = len(selected) - 1
    while k >= 0:
        rev.append(selected[k])
        k -= 1
    return rev^


# ── knapsack_01_value ────────────────────────────────────────────────────────


fn knapsack_01_value(weights: List[Int], values: List[Int], capacity: Int) -> Int:
    """Maximum value achievable with 0/1 knapsack. Space-optimized 1D DP."""
    var n = len(weights)
    if n == 0 or capacity <= 0:
        return 0
    if len(values) != n:
        return 0
    for i in range(n):
        if weights[i] < 0:
            return 0  # negative weight indexes past dp's end
    if capacity > 1000000:
        return 0  # bound the DP allocation: capacity is untrusted input

    var dp = List[Int]()
    for _ in range(capacity + 1):
        dp.append(0)

    for i in range(n):
        var w = capacity
        while w >= weights[i]:
            var with_item = dp[w - weights[i]] + values[i]
            if with_item > dp[w]:
                dp[w] = with_item
            w -= 1

    return dp[capacity]


# ── tsp_greedy ───────────────────────────────────────────────────────────────


fn tsp_greedy(distances: List[List[Float64]]) -> List[Int]:
    """Greedy nearest-neighbor TSP tour starting from node 0.

    Returns visit order including return to start.
    """
    var n = len(distances)
    if n == 0:
        return List[Int]()
    if n == 1:
        var tour = List[Int]()
        tour.append(0)
        tour.append(0)
        return tour^

    var visited = List[Bool]()
    for _ in range(n):
        visited.append(False)

    var tour = List[Int]()
    tour.append(0)
    visited[0] = True
    var current = 0

    for _ in range(n - 1):
        var best_next = -1
        var best_dist = 1e308
        for j in range(n):
            if not visited[j] and distances[current][j] < best_dist:
                best_dist = distances[current][j]
                best_next = j
        tour.append(best_next)
        visited[best_next] = True
        current = best_next

    tour.append(0)  # Return to start
    return tour^


# ── tsp_tour_length ──────────────────────────────────────────────────────────


fn tsp_tour_length(distances: List[List[Float64]], tour: List[Int]) -> Float64:
    """Total length of a TSP tour."""
    var total = 0.0
    var n = len(tour)
    var m = len(distances)
    for i in range(n - 1):
        var a = tour[i]
        var b = tour[i + 1]
        # Tour indices must stay inside the (possibly ragged) distance matrix.
        if a < 0 or a >= m or b < 0 or b >= len(distances[a]):
            return 0.0
        total += distances[a][b]
    return total


# ── bin_packing_first_fit ────────────────────────────────────────────────────


fn bin_packing_first_fit(items: List[Float64], bin_capacity: Float64) -> Int:
    """First-fit bin packing. Returns number of bins needed."""
    var n = len(items)
    if n == 0:
        return 0
    var bins = List[Float64]()  # remaining capacity per bin
    for i in range(n):
        var placed = False
        for b in range(len(bins)):
            if bins[b] >= items[i]:
                bins[b] -= items[i]
                placed = True
                break
        if not placed:
            bins.append(bin_capacity - items[i])
    return len(bins)


# ── bin_packing_first_fit_decreasing ─────────────────────────────────────────


fn bin_packing_first_fit_decreasing(items: List[Float64], bin_capacity: Float64) -> Int:
    """FFD: sort items descending, then apply first-fit."""
    var n = len(items)
    if n == 0:
        return 0
    # Copy and sort descending (insertion sort)
    var sorted_items = List[Float64]()
    for i in range(n):
        sorted_items.append(items[i])
    for i in range(1, n):
        var key = sorted_items[i]
        var j = i - 1
        while j >= 0 and sorted_items[j] < key:
            sorted_items[j + 1] = sorted_items[j]
            j -= 1
        sorted_items[j + 1] = key
    return bin_packing_first_fit(sorted_items, bin_capacity)


# ── assignment_greedy ────────────────────────────────────────────────────────


fn assignment_greedy(cost_matrix: List[List[Float64]]) -> List[Int]:
    """Greedy assignment: for each row, pick cheapest available column.

    Returns assignment[row] = col.
    """
    var n = len(cost_matrix)
    if n == 0:
        return List[Int]()

    var m = len(cost_matrix[0])
    var col_used = List[Bool]()
    for _ in range(m):
        col_used.append(False)

    var assignment = List[Int]()
    for i in range(n):
        var best_col = -1
        var best_cost = 1e308
        for j in range(m):
            if not col_used[j] and cost_matrix[i][j] < best_cost:
                best_cost = cost_matrix[i][j]
                best_col = j
        assignment.append(best_col)
        if best_col >= 0:
            col_used[best_col] = True
    return assignment^


# ── max_subarray_sum ─────────────────────────────────────────────────────────


fn max_subarray_sum(data: List[Float64]) -> Float64:
    """Kadane's algorithm: maximum contiguous subarray sum.

    Returns 0.0 for empty input. For all-negative, returns largest element.
    """
    var n = len(data)
    if n == 0:
        return 0.0
    var best = data[0]
    var current = data[0]
    for i in range(1, n):
        if current + data[i] > data[i]:
            current = current + data[i]
        else:
            current = data[i]
        if current > best:
            best = current
    return best


# ── longest_increasing_subsequence ───────────────────────────────────────────


fn longest_increasing_subsequence(data: List[Float64]) -> Int:
    """Length of LIS using patience sorting (O(n log n)).

    Uses binary search to maintain tails array.
    """
    var n = len(data)
    if n == 0:
        return 0

    var tails = List[Float64]()
    for i in range(n):
        var x = data[i]
        # Binary search for first tail >= x
        var lo = 0
        var hi = len(tails)
        while lo < hi:
            var mid = (lo + hi) // 2
            if tails[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        if lo == len(tails):
            tails.append(x)
        else:
            tails[lo] = x
    return len(tails)


# ── coin_change ──────────────────────────────────────────────────────────────


fn coin_change(coins: List[Int], amount: Int) -> Int:
    """Minimum number of coins to make amount. Returns -1 if impossible.

    Uses bottom-up DP.
    """
    if amount == 0:
        return 0
    if amount < 0 or len(coins) == 0:
        return -1
    if amount > 1000000:
        return -1  # bound the DP allocation: amount is untrusted input
    for j in range(len(coins)):
        if coins[j] < 0:
            return -1  # negative coin would index past dp's end

    var inf = amount + 1
    var dp = List[Int]()
    for _ in range(amount + 1):
        dp.append(inf)
    dp[0] = 0

    for i in range(1, amount + 1):
        for j in range(len(coins)):
            if coins[j] <= i:
                var prev = dp[i - coins[j]]
                if prev + 1 < dp[i]:
                    dp[i] = prev + 1

    if dp[amount] > amount:
        return -1
    return dp[amount]
