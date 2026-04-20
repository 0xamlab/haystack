"""Python equivalent of mojo/engine/reinforcement.mojo (auto-generated)."""
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

def _argmax(vals):
    n = len(vals)
    if n == 0:
        return 0
    best = 0
    best_val = vals[0]
    for i in range(1, n):
        if vals[i] > best_val:
            best_val = vals[i]
            best = i
    return best



def _init_q(n_states, n_actions):
    Q = []
    for _ in range(n_states):
        row = []
        for _ in range(n_actions):
            row.append(0.0)
        Q.append(row)
    return Q






def epsilon_greedy_action(Q_state, epsilon):
    n = len(Q_state)
    if n == 0:
        return 0
    r = random_float64()
    if r < epsilon:

        idx_f = random_float64() * float(n)
        idx = int(idx_f)
        if idx >= n:
            idx = n - 1
        return idx
    return _argmax(Q_state)






def q_learning(n_states, n_actions, rewards, transitions, alpha, gamma, epsilon, n_episodes):
    Q = _init_q(n_states, n_actions)
    terminal = n_states - 1

    for _ in range(n_episodes):

        s = 0
        steps = 0
        while s != terminal and steps < n_states * 10:
            a = epsilon_greedy_action(Q[s], epsilon)
            r = rewards[s][a]
            s_next = transitions[s][a]

            max_q_next = Q[s_next][0]
            for a2 in range(1, n_actions):
                if Q[s_next][a2] > max_q_next:
                    max_q_next = Q[s_next][a2]
            Q[s][a] = Q[s][a] + alpha * (r + gamma * max_q_next - Q[s][a])
            s = s_next
            steps += 1

    return Q






def sarsa(n_states, n_actions, rewards, transitions, alpha, gamma, epsilon, n_episodes):
    Q = _init_q(n_states, n_actions)
    terminal = n_states - 1

    for _ in range(n_episodes):
        s = 0
        a = epsilon_greedy_action(Q[s], epsilon)
        steps = 0
        while s != terminal and steps < n_states * 10:
            r = rewards[s][a]
            s_next = transitions[s][a]
            a_next = epsilon_greedy_action(Q[s_next], epsilon)
            Q[s][a] = Q[s][a] + alpha * (r + gamma * Q[s_next][a_next] - Q[s][a])
            s = s_next
            a = a_next
            steps += 1

    return Q






def value_iteration(n_states, n_actions, rewards, transitions, gamma, tol):
    V = []
    for _ in range(n_states):
        V.append(0.0)

    max_iter = 10000
    for _ in range(max_iter):
        delta = 0.0
        for s in range(n_states):
            best_val = rewards[s][0] + gamma * V[transitions[s][0]]
            for a in range(1, n_actions):
                val = rewards[s][a] + gamma * V[transitions[s][a]]
                if val > best_val:
                    best_val = val
            diff = best_val - V[s]
            if diff < 0.0:
                diff = -diff
            if diff > delta:
                delta = diff
            V[s] = best_val
        if delta < tol:
            break

    return V






def policy_from_q(Q):
    n_states = len(Q)
    policy = []
    for s in range(n_states):
        policy.append(_argmax(Q[s]))
    return policy






def policy_evaluation(policy, n_states, rewards, transitions, gamma, tol):
    V = []
    for _ in range(n_states):
        V.append(0.0)

    max_iter = 10000
    for _ in range(max_iter):
        delta = 0.0
        for s in range(n_states):
            a = policy[s]
            new_v = rewards[s][a] + gamma * V[transitions[s][a]]
            diff = new_v - V[s]
            if diff < 0.0:
                diff = -diff
            if diff > delta:
                delta = diff
            V[s] = new_v
        if delta < tol:
            break

    return V






def td_error(reward, gamma, v_next, v_current):
    return reward + gamma * v_next - v_current






def discounted_return(rewards, gamma):
    G = 0.0
    n = len(rewards)
    gamma_t = 1.0
    for t in range(n):
        G += gamma_t * rewards[t]
        gamma_t *= gamma
    return G
