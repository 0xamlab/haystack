"""
cellular_automata.mojo — Cellular Automata Library. Zero Python imports.

Pure Mojo implementations for elementary CA rules, Conway's Game of Life,
totalistic rules, Langton's Ant, Wireworld, Rule 110, majority, and parity.

Public API:
  elementary_rule         — Apply Wolfram elementary CA rule (0-255)
  rule_step_1d            — Evolve 1D CA one step using elementary rule
  game_of_life_cell       — Conway's Game of Life cell update rule
  game_of_life_step       — Count neighbors for GoL cell
  totalistic_rule         — k-color totalistic CA rule
  langtons_ant_step       — Langton's Ant: new direction and color
  wireworld_cell          — Wireworld CA rule
  rule110_cell            — Rule 110 (Turing complete)
  majority_rule           — Majority voting CA rule
  parity_rule             — XOR/parity CA rule
"""


# ── elementary_rule ──────────────────────────────────────────────────────────


fn elementary_rule(rule_number: Int, left: Int, center: Int, right: Int) -> Int:
    """Apply Wolfram elementary CA rule (0-255).
    left, center, right are 0 or 1. Returns 0 or 1."""
    var idx = (left << 2) | (center << 1) | right  # 0..7
    return (rule_number >> idx) & 1


# ── rule_step_1d ─────────────────────────────────────────────────────────────


fn rule_step_1d(cells: List[Int], n: Int, rule_number: Int) -> List[Int]:
    """Evolve 1D CA one step. Boundary wraps around. Returns new cell list."""
    var result = List[Int]()
    for i in range(n):
        var left: Int
        var right: Int
        if i == 0:
            left = cells[n - 1]
        else:
            left = cells[i - 1]
        if i == n - 1:
            right = cells[0]
        else:
            right = cells[i + 1]
        result.append(elementary_rule(rule_number, left, cells[i], right))
    return result^


# ── game_of_life_cell ────────────────────────────────────────────────────────


fn game_of_life_cell(alive: Bool, neighbors: Int) -> Bool:
    """Conway's Game of Life cell update rule.
    alive: current state; neighbors: count of live neighbors (0-8).
    Returns True if cell is alive next step."""
    if alive:
        return neighbors == 2 or neighbors == 3
    else:
        return neighbors == 3


# ── game_of_life_step ────────────────────────────────────────────────────────


fn game_of_life_step(grid: List[Int], rows: Int, cols: Int, i: Int, j: Int) -> Int:
    """Count live neighbors for GoL cell at (i,j) in row-major grid.
    Grid values: 0=dead, 1=alive. Returns neighbor count."""
    var count: Int = 0
    for di in range(-1, 2):
        for dj in range(-1, 2):
            if di == 0 and dj == 0:
                continue
            var ni = i + di
            var nj = j + dj
            if ni >= 0 and ni < rows and nj >= 0 and nj < cols:
                count += grid[ni * cols + nj]
    return count


# ── totalistic_rule ──────────────────────────────────────────────────────────


fn totalistic_rule(k: Int, rule_number: Int, total: Int) -> Int:
    """k-color totalistic CA rule. Given k colors, rule_number in base k,
    and total (sum of neighborhood), return the new cell state.
    Extracts digit at position 'total' from rule_number in base k."""
    var t = total
    var r = rule_number
    # Extract the digit at position t in base-k representation
    for _ in range(t):
        r = r // k
    return r % k


# ── langtons_ant_step ────────────────────────────────────────────────────────


fn langtons_ant_step(dir: Int, cell_color: Int) -> List[Int]:
    """Langton's Ant step. dir: 0=N,1=E,2=S,3=W. cell_color: 0=white,1=black.
    Returns [new_dir, new_color].
    On white: turn right, flip to black. On black: turn left, flip to white."""
    var new_dir: Int
    var new_color: Int
    if cell_color == 0:
        # White: turn right 90°, flip to black
        new_dir = (dir + 1) % 4
        new_color = 1
    else:
        # Black: turn left 90°, flip to white
        new_dir = (dir + 3) % 4
        new_color = 0
    var result = List[Int]()
    result.append(new_dir)
    result.append(new_color)
    return result^


# ── wireworld_cell ───────────────────────────────────────────────────────────


fn wireworld_cell(state: Int, copper_neighbors_excited: Int) -> Int:
    """Wireworld CA rule.
    state: 0=empty, 1=electron_head, 2=electron_tail, 3=conductor.
    copper_neighbors_excited: count of neighbors that are electron heads.
    Returns new state."""
    if state == 0:
        return 0  # empty stays empty
    elif state == 1:
        return 2  # head → tail
    elif state == 2:
        return 3  # tail → conductor
    else:
        # conductor: becomes head if 1 or 2 neighbors are heads
        if copper_neighbors_excited == 1 or copper_neighbors_excited == 2:
            return 1
        return 3


# ── rule110_cell ─────────────────────────────────────────────────────────────


fn rule110_cell(left: Int, center: Int, right: Int) -> Int:
    """Rule 110 CA cell (Turing complete). Same as elementary_rule(110, ...)."""
    return elementary_rule(110, left, center, right)


# ── majority_rule ────────────────────────────────────────────────────────────


fn majority_rule(neighbors_on: Int, total_neighbors: Int) -> Int:
    """Majority voting CA rule. Returns 1 if majority of neighbors are on,
    0 otherwise. Tie goes to 0."""
    if total_neighbors == 0:
        return 0
    if neighbors_on * 2 > total_neighbors:
        return 1
    return 0


# ── parity_rule ──────────────────────────────────────────────────────────────


fn parity_rule(neighbors_on: Int) -> Int:
    """XOR/parity CA rule. Returns 1 if odd number of neighbors are on."""
    return neighbors_on % 2
