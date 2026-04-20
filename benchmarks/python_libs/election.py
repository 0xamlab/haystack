"""Python equivalent of mojo/engine/election.mojo (auto-generated)."""
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

def pairwise_matrix(ballots, n_candidates):
    matrix = []
    for i in range(n_candidates):
        row = []
        for j in range(n_candidates):
            row.append(0)
        matrix.append(row)
    nb = len(ballots)
    for b in range(nb):
        ballot = ballots[b].copy()
        blen = len(ballot)

        for i in range(blen):
            for j in range(i + 1, blen):
                ci = ballot[i]
                cj = ballot[j]
                row = matrix[ci].copy()
                row[cj] += 1
                matrix[ci] = row
    return matrix






def plurality(ballots, n_candidates):
    counts = []
    for _ in range(n_candidates):
        counts.append(0)
    nb = len(ballots)
    for b in range(nb):
        ballot = ballots[b].copy()
        if len(ballot) > 0:
            counts[ballot[0]] += 1
    best = -1
    best_count = -1
    for i in range(n_candidates):
        if counts[i] > best_count:
            best_count = counts[i]
            best = i
    return best






def borda_count(ballots, n_candidates):
    scores = []
    for _ in range(n_candidates):
        scores.append(0.0)
    nb = len(ballots)
    for b in range(nb):
        ballot = ballots[b].copy()
        blen = len(ballot)
        for rank in range(blen):

            points = float(n_candidates - 1 - rank)
            scores[ballot[rank]] += points
    return scores






def borda_winner(ballots, n_candidates):
    scores = borda_count(ballots, n_candidates)
    best = -1
    best_score = -1.0
    for i in range(n_candidates):
        if scores[i] > best_score:
            best_score = scores[i]
            best = i
    return best






def condorcet_winner(ballots, n_candidates):
    matrix = pairwise_matrix(ballots, n_candidates)
    for i in range(n_candidates):
        wins_all = True
        row_i = matrix[i].copy()
        for j in range(n_candidates):
            if i != j:
                row_j = matrix[j].copy()
                if row_i[j] <= row_j[i]:
                    wins_all = False
                    break
        if wins_all:
            return i
    return -1






def instant_runoff(ballots, n_candidates):

    eliminated = []
    for _ in range(n_candidates):
        eliminated.append(False)

    n_active = n_candidates
    nb = len(ballots)

    while n_active > 1:

        counts = []
        for _ in range(n_candidates):
            counts.append(0)
        for b in range(nb):
            ballot = ballots[b].copy()
            blen = len(ballot)
            for r in range(blen):
                if not eliminated[ballot[r]]:
                    counts[ballot[r]] += 1
                    break


        total_votes = 0
        for i in range(n_candidates):
            if not eliminated[i]:
                total_votes += counts[i]
        for i in range(n_candidates):
            if not eliminated[i] and counts[i] * 2 > total_votes:
                return i


        min_count = total_votes + 1
        for i in range(n_candidates):
            if not eliminated[i] and counts[i] < min_count:
                min_count = counts[i]


        for i in range(n_candidates):
            if not eliminated[i] and counts[i] == min_count:
                eliminated[i] = True
                n_active -= 1
                if n_active <= 1:
                    break


    for i in range(n_candidates):
        if not eliminated[i]:
            return i
    return -1






def approval_voting(approvals, n_candidates):
    counts = []
    for _ in range(n_candidates):
        counts.append(0)
    nb = len(approvals)
    for b in range(nb):
        ballot = approvals[b].copy()
        blen = len(ballot)
        for i in range(blen):
            counts[ballot[i]] += 1
    best = -1
    best_count = -1
    for i in range(n_candidates):
        if counts[i] > best_count:
            best_count = counts[i]
            best = i
    return best






def copeland_scores(ballots, n_candidates):
    matrix = pairwise_matrix(ballots, n_candidates)
    scores = []
    for _ in range(n_candidates):
        scores.append(0.0)
    for i in range(n_candidates):
        row_i = matrix[i].copy()
        for j in range(i + 1, n_candidates):
            row_j = matrix[j].copy()
            if row_i[j] > row_j[i]:
                scores[i] += 1.0
            elif row_i[j] < row_j[i]:
                scores[j] += 1.0
            else:
                scores[i] += 0.5
                scores[j] += 0.5
    return scores
