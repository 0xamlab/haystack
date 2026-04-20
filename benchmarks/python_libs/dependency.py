"""Python equivalent of mojo/engine/dependency.mojo (auto-generated)."""
import math
import random as _rng

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

def resolve_order(n_packages, dependencies):

    in_deg = []
    for _ in range(n_packages):
        in_deg.append(0)

    adj = []
    for _ in range(n_packages):
        adj.append([])

    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            pkg = dependencies[i][0]
            depends_on = dependencies[i][1]
            if pkg >= 0 and pkg < n_packages and depends_on >= 0 and depends_on < n_packages:
                adj[depends_on].append(pkg)
                in_deg[pkg] += 1


    queue = []
    for i in range(n_packages):
        if in_deg[i] == 0:
            queue.append(i)

    result = []
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        result.append(node)
        for j in range(len(adj[node])):
            nb = adj[node][j]
            in_deg[nb] -= 1
            if in_deg[nb] == 0:
                queue.append(nb)

    if len(result) != n_packages:
        return []  # cycle detected
    return result






def has_cycle(n_packages, dependencies):
    order = resolve_order(n_packages, dependencies)
    return len(order) == 0






def transitive_deps(package, dependencies):

    max_id = package + 1
    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            if dependencies[i][0] + 1 > max_id:
                max_id = dependencies[i][0] + 1
            if dependencies[i][1] + 1 > max_id:
                max_id = dependencies[i][1] + 1


    direct = []
    for _ in range(max_id):
        direct.append([])

    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            direct[dependencies[i][0]].append(dependencies[i][1])


    visited = []
    for _ in range(max_id):
        visited.append(False)

    queue = []
    result = []

    if package < 0 or package >= max_id:
        return result


    for j in range(len(direct[package])):
        d = direct[package][j]
        if not visited[d]:
            visited[d] = True
            queue.append(d)
            result.append(d)

    head = 0
    while head < len(queue):
        curr = queue[head]
        head += 1
        if curr < max_id:
            for j in range(len(direct[curr])):
                d = direct[curr][j]
                if not visited[d]:
                    visited[d] = True
                    queue.append(d)
                    result.append(d)

    return result






def dependency_depth(package, dependencies):
    max_id = package + 1
    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            if dependencies[i][0] + 1 > max_id:
                max_id = dependencies[i][0] + 1
            if dependencies[i][1] + 1 > max_id:
                max_id = dependencies[i][1] + 1

    direct = []
    for _ in range(max_id):
        direct.append([])

    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2:
            direct[dependencies[i][0]].append(dependencies[i][1])

    if package < 0 or package >= max_id:
        return 0


    stack_node = []
    stack_depth = []
    stack_node.append(package)
    stack_depth.append(0)
    max_depth = 0

    while len(stack_node) > 0:
        node = stack_node.pop()
        depth = stack_depth.pop()
        if depth > max_depth:
            max_depth = depth
        if node < max_id:
            for j in range(len(direct[node])):
                stack_node.append(direct[node][j])
                stack_depth.append(depth + 1)

    return max_depth






def is_compatible(version, min_ver, max_ver):
    return version >= min_ver and version <= max_ver






def find_conflicts(requirements):
    conflicts = []
    n = len(requirements)
    for i in range(n):
        if len(requirements[i]) < 3:
            continue
        for j in range(i + 1, n):
            if len(requirements[j]) < 3:
                continue

            if requirements[i][0] == requirements[j][0]:
                min_i = requirements[i][1]
                max_i = requirements[i][2]
                min_j = requirements[j][1]
                max_j = requirements[j][2]

                if max_i < min_j or max_j < min_i:
                    pair = []
                    pair.append(i)
                    pair.append(j)
                    conflicts.append(pair)
    return conflicts






def install_plan(n_packages, deps, target):

    all_deps = transitive_deps(target, deps)


    needed = []
    for _ in range(n_packages):
        needed.append(False)

    if target >= 0 and target < n_packages:
        needed[target] = True
    for i in range(len(all_deps)):
        d = all_deps[i]
        if d >= 0 and d < n_packages:
            needed[d] = True


    full_order = resolve_order(n_packages, deps)
    plan = []
    for i in range(len(full_order)):
        pkg = full_order[i]
        if needed[pkg]:
            plan.append(pkg)

    return plan






def reverse_deps(package, dependencies):
    result = []
    seen = []
    for i in range(len(dependencies)):
        if len(dependencies[i]) >= 2 and dependencies[i][1] == package:
            pkg = dependencies[i][0]

            found = False
            for k in range(len(seen)):
                if seen[k] == pkg:
                    found = True
                    break
            if not found:
                result.append(pkg)
                seen.append(pkg)
    return result
