"""
constraint.mojo — Constraint Satisfaction Problems. Zero Python imports.

Replaces python-constraint with pure Mojo implementations of backtracking
CSP solver, N-Queens, graph coloring, Sudoku validation, and magic squares.

Public API:
  CSPResult            — Result struct with solution and found flag
  solve_backtrack      — Backtracking CSP solver
  all_different        — Check all values unique
  n_queens_check       — Validate queen placement
  solve_n_queens       — Solve N-Queens via backtracking
  magic_square_check   — Validate magic square
  graph_coloring       — Graph coloring via backtracking
  sudoku_valid         — Validate 9x9 Sudoku board
  count_solutions_nqueens — Count all N-Queens solutions
"""


# ── CSPResult ────────────────────────────────────────────────────────────────


struct CSPResult(Copyable, Movable):
    """Result of a CSP solver run."""
    var solution: List[Int]
    var found: Bool

    fn __init__(out self, solution: List[Int], found: Bool):
        self.solution = solution.copy()
        self.found = found


# ── solve_backtrack ──────────────────────────────────────────────────────────


fn _check_constraint(assignment: List[Int], n_assigned: Int, c: List[Int]) -> Bool:
    """Check a single constraint [var1, var2, relation].
    relation: 0=not_equal, 1=less_than, 2=equal."""
    var v1 = c[0]
    var v2 = c[1]
    var rel = c[2]
    if v1 >= n_assigned or v2 >= n_assigned:
        return True  # not yet assigned
    var a = assignment[v1]
    var b = assignment[v2]
    if rel == 0:
        return a != b
    elif rel == 1:
        return a < b
    elif rel == 2:
        return a == b
    return True


fn _bt_solve(
    mut assignment: List[Int],
    idx: Int,
    domains: List[List[Int]],
    constraints: List[List[Int]],
) -> Bool:
    var n = len(domains)
    if idx == n:
        return True
    var dom = domains[idx].copy()
    for di in range(len(dom)):
        assignment[idx] = dom[di]
        var ok = True
        for ci in range(len(constraints)):
            if not _check_constraint(assignment, idx + 1, constraints[ci]):
                ok = False
                break
        if ok:
            if _bt_solve(assignment, idx + 1, domains, constraints):
                return True
    assignment[idx] = -1
    return False


fn solve_backtrack(
    domains: List[List[Int]], constraints: List[List[Int]]
) -> CSPResult:
    """Backtracking CSP solver. Returns first valid solution or found=False."""
    var n = len(domains)
    var assignment = List[Int]()
    for i in range(n):
        assignment.append(-1)
    if _bt_solve(assignment, 0, domains, constraints):
        return CSPResult(assignment, True)
    return CSPResult(List[Int](), False)


# ── all_different ────────────────────────────────────────────────────────────


fn all_different(values: List[Int]) -> Bool:
    """Check if all values in the list are unique."""
    var n = len(values)
    for i in range(n):
        for j in range(i + 1, n):
            if values[i] == values[j]:
                return False
    return True


# ── n_queens_check ───────────────────────────────────────────────────────────


fn n_queens_check(queens: List[Int]) -> Bool:
    """Check if a queen placement is valid (no attacks).
    queens[i] = column of queen in row i."""
    var n = len(queens)
    for i in range(n):
        for j in range(i + 1, n):
            if queens[i] == queens[j]:
                return False
            var diff = j - i
            if queens[i] - queens[j] == diff or queens[j] - queens[i] == diff:
                return False
    return True


# ── solve_n_queens ───────────────────────────────────────────────────────────


fn _nq_solve(mut queens: List[Int], row: Int, n: Int) -> Bool:
    if row == n:
        return True
    for col in range(n):
        var ok = True
        for r in range(row):
            if queens[r] == col:
                ok = False
                break
            var rd = row - r
            if queens[r] - col == rd or col - queens[r] == rd:
                ok = False
                break
        if ok:
            queens[row] = col
            if _nq_solve(queens, row + 1, n):
                return True
    queens[row] = -1
    return False


fn solve_n_queens(n: Int) -> List[Int]:
    """Solve N-Queens problem. Returns column assignments or empty list."""
    var queens = List[Int]()
    for i in range(n):
        queens.append(-1)
    if _nq_solve(queens, 0, n):
        return queens^
    return List[Int]()


# ── magic_square_check ───────────────────────────────────────────────────────


fn magic_square_check(square: List[List[Int]]) -> Bool:
    """Check if a square grid is a magic square."""
    var n = len(square)
    if n == 0:
        return False
    # Compute target sum from first row
    var target = 0
    for j in range(n):
        target += square[0][j]
    # Check all rows
    for i in range(1, n):
        var s = 0
        for j in range(n):
            s += square[i][j]
        if s != target:
            return False
    # Check all columns
    for j in range(n):
        var s = 0
        for i in range(n):
            s += square[i][j]
        if s != target:
            return False
    # Check main diagonal
    var d1 = 0
    for i in range(n):
        d1 += square[i][i]
    if d1 != target:
        return False
    # Check anti-diagonal
    var d2 = 0
    for i in range(n):
        d2 += square[i][n - 1 - i]
    if d2 != target:
        return False
    return True


# ── graph_coloring ───────────────────────────────────────────────────────────


fn _gc_solve(
    mut colors: List[Int],
    node: Int,
    n_nodes: Int,
    n_colors: Int,
    adj: List[List[Int]],
) -> Bool:
    if node == n_nodes:
        return True
    for c in range(n_colors):
        var ok = True
        var neighbors = adj[node].copy()
        for ni in range(len(neighbors)):
            var nb = neighbors[ni]
            if colors[nb] != -1 and colors[nb] == c:
                ok = False
                break
        if ok:
            colors[node] = c
            if _gc_solve(colors, node + 1, n_nodes, n_colors, adj):
                return True
            colors[node] = -1
    return False


fn graph_coloring(adj: List[List[Int]], n_colors: Int) -> List[Int]:
    """Color a graph with n_colors using backtracking.
    adj[i] is the list of neighbors of node i.
    Returns color assignment or empty list if no solution."""
    var n = len(adj)
    # A neighbor index outside [0, n) would be read in _gc_solve as colors[neighbor]
    # (uncatchable abort), and a non-positive palette has no assignment; refuse both with
    # the same empty-list answer used for "no solution".
    if n_colors <= 0:
        return List[Int]()
    for i in range(n):
        for j in range(len(adj[i])):
            if adj[i][j] < 0 or adj[i][j] >= n:
                return List[Int]()
    var colors = List[Int]()
    for i in range(n):
        colors.append(-1)
    if _gc_solve(colors, 0, n, n_colors, adj):
        return colors^
    return List[Int]()


# ── sudoku_valid ─────────────────────────────────────────────────────────────


fn sudoku_valid(board: List[List[Int]]) -> Bool:
    """Check if a 9x9 Sudoku board is valid (0 = empty cell)."""
    if len(board) != 9:
        return False
    # Check rows
    for i in range(9):
        if len(board[i]) != 9:
            return False
        for j in range(9):
            var v = board[i][j]
            if v == 0:
                continue
            if v < 1 or v > 9:
                return False
            for k in range(j + 1, 9):
                if board[i][k] == v:
                    return False
    # Check columns
    for j in range(9):
        for i in range(9):
            var v = board[i][j]
            if v == 0:
                continue
            for k in range(i + 1, 9):
                if board[k][j] == v:
                    return False
    # Check 3x3 boxes
    for br in range(3):
        for bc in range(3):
            var vals = List[Int]()
            for i in range(3):
                for j in range(3):
                    var v = board[br * 3 + i][bc * 3 + j]
                    if v != 0:
                        for vi in range(len(vals)):
                            if vals[vi] == v:
                                return False
                        vals.append(v)
    return True


# ── count_solutions_nqueens ──────────────────────────────────────────────────


fn _nq_count(mut queens: List[Int], row: Int, n: Int, mut count: Int):
    if row == n:
        count += 1
        return
    for col in range(n):
        var ok = True
        for r in range(row):
            if queens[r] == col:
                ok = False
                break
            var rd = row - r
            if queens[r] - col == rd or col - queens[r] == rd:
                ok = False
                break
        if ok:
            queens[row] = col
            _nq_count(queens, row + 1, n, count)
            queens[row] = -1


fn count_solutions_nqueens(n: Int) -> Int:
    """Count total solutions for N-Queens."""
    var queens = List[Int]()
    for i in range(n):
        queens.append(-1)
    var count = 0
    _nq_count(queens, 0, n, count)
    return count
