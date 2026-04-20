"""Python equivalent of mojo/engine/constraint.mojo (auto-generated)."""
import math
import random as _rng

class CSPResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('solution')
        self.solution = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('found')
        self.found = _v1 if _v1 is not None else False
    def __repr__(self):
        return f'CSPResult({vars(self)})'

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

def _check_constraint(assignment, n_assigned, c):
    v1 = c[0]
    v2 = c[1]
    rel = c[2]
    if v1 >= n_assigned or v2 >= n_assigned:
        return True  # not yet assigned
    a = assignment[v1]
    b = assignment[v2]
    if rel == 0:
        return a != b
    elif rel == 1:
        return a < b
    elif rel == 2:
        return a == b
    return True



def _bt_solve(assignment, idx, domains, constraints):
    n = len(domains)
    if idx == n:
        return True
    dom = domains[idx].copy()
    for di in range(len(dom)):
        assignment[idx] = dom[di]
        ok = True
        for ci in range(len(constraints)):
            if not _check_constraint(assignment, idx + 1, constraints[ci]):
                ok = False
                break
        if ok:
            if _bt_solve(assignment, idx + 1, domains, constraints):
                return True
    assignment[idx] = -1
    return False



def _nq_solve(queens, row, n):
    if row == n:
        return True
    for col in range(n):
        ok = True
        for r in range(row):
            if queens[r] == col:
                ok = False
                break
            rd = row - r
            if queens[r] - col == rd or col - queens[r] == rd:
                ok = False
                break
        if ok:
            queens[row] = col
            if _nq_solve(queens, row + 1, n):
                return True
    queens[row] = -1
    return False



def _gc_solve(colors, node, n_nodes, n_colors, adj):
    if node == n_nodes:
        return True
    for c in range(n_colors):
        ok = True
        neighbors = adj[node].copy()
        for ni in range(len(neighbors)):
            nb = neighbors[ni]
            if colors[nb] != -1 and colors[nb] == c:
                ok = False
                break
        if ok:
            colors[node] = c
            if _gc_solve(colors, node + 1, n_nodes, n_colors, adj):
                return True
            colors[node] = -1
    return False



def solve_backtrack(domains, constraints):
    n = len(domains)
    assignment = []
    for i in range(n):
        assignment.append(-1)
    if _bt_solve(assignment, 0, domains, constraints):
        return CSPResult(assignment, True)
    return CSPResult([], False)






def all_different(values):
    n = len(values)
    for i in range(n):
        for j in range(i + 1, n):
            if values[i] == values[j]:
                return False
    return True






def n_queens_check(queens):
    n = len(queens)
    for i in range(n):
        for j in range(i + 1, n):
            if queens[i] == queens[j]:
                return False
            diff = j - i
            if queens[i] - queens[j] == diff or queens[j] - queens[i] == diff:
                return False
    return True






def solve_n_queens(n):
    queens = []
    for i in range(n):
        queens.append(-1)
    if _nq_solve(queens, 0, n):
        return queens
    return []






def magic_square_check(square):
    n = len(square)
    if n == 0:
        return False

    target = 0
    for j in range(n):
        target += square[0][j]

    for i in range(1, n):
        s = 0
        for j in range(n):
            s += square[i][j]
        if s != target:
            return False

    for j in range(n):
        s = 0
        for i in range(n):
            s += square[i][j]
        if s != target:
            return False

    d1 = 0
    for i in range(n):
        d1 += square[i][i]
    if d1 != target:
        return False

    d2 = 0
    for i in range(n):
        d2 += square[i][n - 1 - i]
    if d2 != target:
        return False
    return True






def graph_coloring(adj, n_colors):
    n = len(adj)
    colors = []
    for i in range(n):
        colors.append(-1)
    if _gc_solve(colors, 0, n, n_colors, adj):
        return colors
    return []






def sudoku_valid(board):
    if len(board) != 9:
        return False

    for i in range(9):
        if len(board[i]) != 9:
            return False
        for j in range(9):
            v = board[i][j]
            if v == 0:
                continue
            if v < 1 or v > 9:
                return False
            for k in range(j + 1, 9):
                if board[i][k] == v:
                    return False

    for j in range(9):
        for i in range(9):
            v = board[i][j]
            if v == 0:
                continue
            for k in range(i + 1, 9):
                if board[k][j] == v:
                    return False

    for br in range(3):
        for bc in range(3):
            vals = []
            for i in range(3):
                for j in range(3):
                    v = board[br * 3 + i][bc * 3 + j]
                    if v != 0:
                        for vi in range(len(vals)):
                            if vals[vi] == v:
                                return False
                        vals.append(v)
    return True






def count_solutions_nqueens(n):
    queens = []
    for i in range(n):
        queens.append(-1)
    count = 0
    _nq_count(queens, 0, n, count)
    return count
