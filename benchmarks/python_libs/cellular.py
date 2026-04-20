"""Python equivalent of mojo/engine/cellular.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.random import random_float64
except Exception:
    pass

def random_float64(lo=0.0, hi=1.0): return _rng.uniform(lo, hi)
def random_si64(): return _rng.randint(-2**31, 2**31)
def random_ui64(): return _rng.randint(0, 2**32)

def json_get_string(raw, key, default=''):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return str(v) if v is not None else default
    except Exception: return default
def json_get_float(raw, key, default=0.0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return float(v) if v is not None else default
    except Exception: return default
def json_get_int(raw, key, default=0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return int(v) if v is not None else default
    except Exception: return default
def json_get_bool(raw, key, default=False):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return bool(v) if v is not None else default
    except Exception: return default
def json_get_object(raw, key, default='{}'):
    try:
        import json as _j; v = _j.loads(raw).get(key, {})
        return _j.dumps(v) if isinstance(v, dict) else default
    except Exception: return default
def json_get_array(raw, key, default='[]'):
    try:
        import json as _j; v = _j.loads(raw).get(key, [])
        return _j.dumps(v) if isinstance(v, list) else default
    except Exception: return default
def json_array_len(arr):
    try:
        import json as _j; return len(_j.loads(arr))
    except Exception: return 0
def json_array_get(arr, index):
    try:
        import json as _j; v = _j.loads(arr)
        return _j.dumps(v[index]) if index < len(v) else ''
    except Exception: return ''
def to_lower(s): return s.lower()
def contains_keyword(text, keyword): return keyword.lower() in text.lower()
def detect_polarity(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','expense','loss','debit','charge','penalty','tax')): return -1
    if any(k in n for k in ('revenue','profit','income','gain','credit','sales')): return 1
    return 0
def detect_unit_hint(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','price','revenue','profit','amount','value','dollar')): return 'currency'
    if any(k in n for k in ('pct','percent','ratio','rate','margin')): return 'percentage'
    if any(k in n for k in ('qty','quantity','count','units','volume')): return 'count'
    return ''
def infer_distribution_from_values(values): return ('normal', '{}')
def map_fields(raw): return []
def build_objective_function(mappings): return ''
def build_variables_json(mappings): return '[]'
class FieldMapping: pass
def dice_coefficient(a, b):
    if not a or not b: return 0.0
    def _bg(s): return set(s[i:i+2] for i in range(len(s)-1))
    ag, bg = _bg(a), _bg(b)
    if not ag or not bg: return 0.0
    return 2.0 * len(ag & bg) / (len(ag) + len(bg))
def edit_similarity(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    m, n = len(a), len(b); dp = list(range(n+1))
    for i in range(1, m+1):
        prev, dp[0] = dp[0], i
        for j in range(1, n+1):
            t = dp[j]; dp[j] = prev if a[i-1]==b[j-1] else 1+min(prev,dp[j],dp[j-1]); prev=t
    return 1.0 - dp[n] / max(m, n)
def jaccard_index(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)
def to_set(lst): return list(set(lst))
def parse_float64(s, default=0.0):
    try: return float(s)
    except Exception: return default
def parse_int(s, default=0):
    try: return int(float(s))
    except Exception: return default
DIM_UNKNOWN = 0; DIM_COUNT = 1; DIM_CURRENCY = 2; DIM_RATE = 3
DIM_RATIO = 4; DIM_IDENTIFIER = 5; DIM_INVALID = -1
def infer_from_samples(values): return DIM_UNKNOWN
def propagate(a, b, op): return DIM_UNKNOWN
def role_for_dimension(dim): return 'metric'
class Python:
    @staticmethod
    def import_module(name):
        import importlib; return importlib.import_module(name)

def grid_create(rows, cols):
    grid = []
    for _ in range(rows):
        row = []
        for _ in range(cols):
            row.append(0)
        grid.append(row)
    return grid



def grid_randomize(rows, cols, density):
    grid = []
    for _ in range(rows):
        row = []
        for _ in range(cols):
            if random_float64() < density:
                row.append(1)
            else:
                row.append(0)
        grid.append(row)
    return grid



def count_alive(grid):
    total = 0
    for i in range(len(grid)):
        for j in range(len(grid[i])):
            if grid[i][j] != 0:
                total += 1
    return total



def grid_to_density(grid):
    rows = len(grid)
    if rows == 0:
        return 0.0
    cols = len(grid[0])
    total_cells = rows * cols
    if total_cells == 0:
        return 0.0
    alive = count_alive(grid)
    return float(alive) / float(total_cells)






def count_neighbors(grid, row, col, rows, cols):
    count = 0
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            if dr == 0 and dc == 0:
                continue
            nr = row + dr
            nc = col + dc
            if nr >= 0 and nr < rows and nc >= 0 and nc < cols:
                if grid[nr][nc] != 0:
                    count += 1
    return count






def game_of_life_step(grid, rows, cols):
    new_grid = grid_create(rows, cols)
    for r in range(rows):
        for c in range(cols):
            n = count_neighbors(grid, r, c, rows, cols)
            if grid[r][c] != 0:

                if n == 2 or n == 3:
                    new_grid[r][c] = 1
                else:
                    new_grid[r][c] = 0
            else:

                if n == 3:
                    new_grid[r][c] = 1
    return new_grid






def is_still_life(grid, rows, cols):
    next_grid = game_of_life_step(grid, rows, cols)
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != next_grid[r][c]:
                return False
    return True






def population_history(initial, rows, cols, steps):
    history = []
    current = []

    for r in range(len(initial)):
        row = []
        for c in range(len(initial[r])):
            row.append(initial[r][c])
        current.append(row)
    history.append(count_alive(current))
    for _ in range(steps):
        current = game_of_life_step(current, rows, cols)
        history.append(count_alive(current))
    return history






def rule_lookup(left, center, right, rule):
    idx = left * 4 + center * 2 + right
    return (rule >> idx) & 1



def elementary_ca_step(state, rule):
    n = len(state)
    new_state = []
    if n == 0:
        return new_state
    for i in range(n):
        left = 0
        if i > 0:
            left = state[i - 1]
        center = state[i]
        right = 0
        if i < n - 1:
            right = state[i + 1]
        new_state.append(rule_lookup(left, center, right, rule))
    return new_state



def run_elementary_ca(initial, rule, steps):
    history = []

    current = []
    for i in range(len(initial)):
        current.append(initial[i])
    history.append(current.copy())
    for _ in range(steps):
        current = elementary_ca_step(current, rule)
        history.append(current.copy())
    return history
