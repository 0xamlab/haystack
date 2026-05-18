"""
cellular.mojo — Cellular automata. Zero Python imports.

Replaces custom CA code with pure Mojo implementations for Conway's
Game of Life, 1D elementary cellular automata, and grid utilities.

Public API:
  game_of_life_step   — One step of Conway's Game of Life
  count_neighbors     — Count live neighbors (8-connected)
  elementary_ca_step  — One step of 1D elementary CA (Wolfram rule)
  rule_lookup         — Look up next state from rule number
  run_elementary_ca   — Run 1D CA for multiple steps
  count_alive         — Count living cells in 2D grid
  grid_create         — Create empty grid
  grid_randomize      — Random grid with given density
  grid_to_density     — Fraction of alive cells
  is_still_life       — Check if grid is a still life
  population_history  — Track population count over generations
"""
from std.random import random_float64


# ── Grid utilities ─────────────────────────────────────────────────────────────


fn grid_create(rows: Int, cols: Int) -> List[List[Int]]:
    """Create an empty (all-zero) grid of rows × cols."""
    var grid = List[List[Int]]()
    for _ in range(rows):
        var row = List[Int]()
        for _ in range(cols):
            row.append(0)
        grid.append(row^)
    return grid^


fn grid_randomize(
    rows: Int, cols: Int, density: Float64
) -> List[List[Int]]:
    """Random grid with given density of alive cells.

    Each cell has 'density' probability of being alive (1).
    """
    var grid = List[List[Int]]()
    for _ in range(rows):
        var row = List[Int]()
        for _ in range(cols):
            if random_float64() < density:
                row.append(1)
            else:
                row.append(0)
        grid.append(row^)
    return grid^


fn count_alive(grid: List[List[Int]]) -> Int:
    """Count living cells in 2D grid."""
    var total: Int = 0
    for i in range(len(grid)):
        for j in range(len(grid[i])):
            if grid[i][j] != 0:
                total += 1
    return total


fn grid_to_density(grid: List[List[Int]]) -> Float64:
    """Fraction of alive cells in the grid."""
    var rows = len(grid)
    if rows == 0:
        return 0.0
    var cols = len(grid[0])
    var total_cells = rows * cols
    if total_cells == 0:
        return 0.0
    var alive = count_alive(grid)
    return Float64(alive) / Float64(total_cells)


# ── Neighbor counting ─────────────────────────────────────────────────────────


fn count_neighbors(
    grid: List[List[Int]],
    row: Int,
    col: Int,
    rows: Int,
    cols: Int,
) -> Int:
    """Count live neighbors (8-connected) for cell at (row, col).

    Uses bounded checks (no wrapping).
    """
    var count: Int = 0
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            if dr == 0 and dc == 0:
                continue
            var nr = row + dr
            var nc = col + dc
            if nr >= 0 and nr < rows and nc >= 0 and nc < cols:
                if grid[nr][nc] != 0:
                    count += 1
    return count


# ── Game of Life ───────────────────────────────────────────────────────────────


fn game_of_life_step(
    grid: List[List[Int]], rows: Int, cols: Int
) -> List[List[Int]]:
    """One step of Conway's Game of Life.

    Rules:
    - Live cell with 2 or 3 neighbors survives.
    - Dead cell with exactly 3 neighbors becomes alive.
    - All other cells die or stay dead.
    """
    var new_grid = grid_create(rows, cols)
    for r in range(rows):
        for c in range(cols):
            var n = count_neighbors(grid, r, c, rows, cols)
            if grid[r][c] != 0:
                # Live cell
                if n == 2 or n == 3:
                    new_grid[r][c] = 1
                else:
                    new_grid[r][c] = 0
            else:
                # Dead cell
                if n == 3:
                    new_grid[r][c] = 1
    return new_grid^


# ── Still life detection ──────────────────────────────────────────────────────


fn is_still_life(
    grid: List[List[Int]], rows: Int, cols: Int
) -> Bool:
    """Check if grid is a still life (doesn't change after one step)."""
    var next_grid = game_of_life_step(grid, rows, cols)
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != next_grid[r][c]:
                return False
    return True


# ── Population history ────────────────────────────────────────────────────────


fn population_history(
    initial: List[List[Int]], rows: Int, cols: Int, steps: Int
) -> List[Int]:
    """Track population count over generations.

    Returns list of length steps+1 with population at each generation.
    """
    var history = List[Int]()
    var current = List[List[Int]]()
    # Deep copy initial
    for r in range(len(initial)):
        var row = List[Int]()
        for c in range(len(initial[r])):
            row.append(initial[r][c])
        current.append(row^)
    history.append(count_alive(current))
    for _ in range(steps):
        current = game_of_life_step(current, rows, cols)
        history.append(count_alive(current))
    return history^


# ── Elementary cellular automata ───────────────────────────────────────────────


fn rule_lookup(left: Int, center: Int, right: Int, rule: Int) -> Int:
    """Look up next state from Wolfram rule number.

    The neighborhood (left, center, right) forms a 3-bit number.
    The rule number is an 8-bit number where each bit determines
    the output for one of the 8 possible neighborhoods.
    """
    var idx = left * 4 + center * 2 + right
    return (rule >> idx) & 1


fn elementary_ca_step(state: List[Int], rule: Int) -> List[Int]:
    """One step of 1D elementary cellular automaton (Wolfram rule).

    Boundaries are treated as 0.
    """
    var n = len(state)
    var new_state = List[Int]()
    if n == 0:
        return new_state^
    for i in range(n):
        var left: Int = 0
        if i > 0:
            left = state[i - 1]
        var center = state[i]
        var right: Int = 0
        if i < n - 1:
            right = state[i + 1]
        new_state.append(rule_lookup(left, center, right, rule))
    return new_state^


fn run_elementary_ca(
    initial: List[Int], rule: Int, steps: Int
) -> List[List[Int]]:
    """Run 1D CA for multiple steps. Returns all states including initial.

    Returns list of length steps+1.
    """
    var history = List[List[Int]]()
    # Copy initial
    var current = List[Int]()
    for i in range(len(initial)):
        current.append(initial[i])
    history.append(current.copy())
    for _ in range(steps):
        current = elementary_ca_step(current, rule)
        history.append(current.copy())
    return history^
