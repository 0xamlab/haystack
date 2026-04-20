"""Python equivalent of mojo/engine/scheduling_algo.mojo (auto-generated)."""
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

def _make_row4(a, b, c, d):
    row = []
    row.append(a)
    row.append(b)
    row.append(c)
    row.append(d)
    return row



def _make_row3(a, b, c):
    row = []
    row.append(a)
    row.append(b)
    row.append(c)
    return row






def fcfs(processes):
    n = len(processes)

    order = []
    for i in range(n):
        order.append(i)

    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if processes[order[j]][0] < processes[order[min_idx]][0]:
                min_idx = j
        if min_idx != i:
            tmp = order[i]
            order[i] = order[min_idx]
            order[min_idx] = tmp

    results = []
    current_time = 0
    for i in range(n):
        pid = order[i]
        arrival = processes[pid][0]
        burst = processes[pid][1]
        if current_time < arrival:
            current_time = arrival
        start = current_time
        finish = start + burst
        wait = start - arrival
        results.append(_make_row4(pid, start, finish, wait))
        current_time = finish
    return results






def sjf(processes):
    n = len(processes)
    done = []
    for i in range(n):
        done.append(False)
    results = []
    current_time = 0
    completed = 0
    while completed < n:

        best = -1
        best_burst = 2147483647  # INT_MAX
        for i in range(n):
            if not done[i] and processes[i][0] <= current_time:
                if processes[i][1] < best_burst:
                    best_burst = processes[i][1]
                    best = i
        if best == -1:

            min_arrival = 2147483647
            for i in range(n):
                if not done[i] and processes[i][0] < min_arrival:
                    min_arrival = processes[i][0]
            current_time = min_arrival
            continue
        arrival = processes[best][0]
        burst = processes[best][1]
        start = current_time
        finish = start + burst
        wait = start - arrival
        results.append(_make_row4(best, start, finish, wait))
        current_time = finish
        done[best] = True
        completed += 1
    return results






def priority_scheduling(processes):
    n = len(processes)
    done = []
    for i in range(n):
        done.append(False)
    results = []
    current_time = 0
    completed = 0
    while completed < n:
        best = -1
        best_prio = 2147483647
        for i in range(n):
            if not done[i] and processes[i][0] <= current_time:
                if processes[i][2] < best_prio:
                    best_prio = processes[i][2]
                    best = i
        if best == -1:
            min_arrival = 2147483647
            for i in range(n):
                if not done[i] and processes[i][0] < min_arrival:
                    min_arrival = processes[i][0]
            current_time = min_arrival
            continue
        arrival = processes[best][0]
        burst = processes[best][1]
        start = current_time
        finish = start + burst
        wait = start - arrival
        results.append(_make_row4(best, start, finish, wait))
        current_time = finish
        done[best] = True
        completed += 1
    return results






def round_robin(processes, quantum):
    n = len(processes)
    remaining = []
    finish_time = []
    wait_time = []
    for i in range(n):
        remaining.append(processes[i][1])
        finish_time.append(0)
        wait_time.append(0)

    current_time = 0
    done_count = 0
    queue = []
    in_queue = []
    for i in range(n):
        in_queue.append(False)

    while done_count < n:

        for i in range(n):
            if not in_queue[i] and processes[i][0] <= current_time and remaining[i] > 0:
                queue.append(i)
                in_queue[i] = True
        if len(queue) == 0:

            min_arr = 2147483647
            for i in range(n):
                if remaining[i] > 0 and processes[i][0] < min_arr:
                    min_arr = processes[i][0]
            current_time = min_arr
            continue

        pid = queue[0]

        new_queue = []
        for i in range(1, len(queue)):
            new_queue.append(queue[i])
        queue = new_queue

        run_time = quantum
        if remaining[pid] < quantum:
            run_time = remaining[pid]
        current_time += run_time
        remaining[pid] -= run_time


        for i in range(n):
            if not in_queue[i] and processes[i][0] <= current_time and remaining[i] > 0:
                queue.append(i)
                in_queue[i] = True

        if remaining[pid] == 0:
            finish_time[pid] = current_time
            wait_time[pid] = current_time - processes[pid][0] - processes[pid][1]
            done_count += 1
        else:
            queue.append(pid)

    results = []
    for i in range(n):
        results.append(_make_row3(i, finish_time[i], wait_time[i]))
    return results






def avg_wait_time(results):
    n = len(results)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        row_len = len(results[i])
        total += float(results[i][row_len - 1])
    return total / float(n)






def avg_turnaround(results):
    n = len(results)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        row_len = len(results[i])
        if row_len >= 4:

            finish = results[i][2]
            start = results[i][1]
            wait = results[i][3]
            arrival = start - wait
            total += float(finish - arrival)
        elif row_len >= 3:

            finish = results[i][1]
            total += float(finish)
    return total / float(n)






def throughput(results, total_time):
    if total_time <= 0:
        return 0.0
    return float(len(results)) / float(total_time)






def cpu_utilization(results, total_time):
    if total_time <= 0:
        return 0.0
    busy = 0.0
    for i in range(len(results)):
        row_len = len(results[i])
        if row_len >= 4:
            busy += float(results[i][2] - results[i][1])
        elif row_len >= 3:
            busy += float(results[i][1] - results[i][2])
    return busy / float(total_time)






def gantt_chart(results):
    n = len(results)
    order = []
    for i in range(n):
        order.append(i)

    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if results[order[j]][1] < results[order[min_idx]][1]:
                min_idx = j
        if min_idx != i:
            tmp = order[i]
            order[i] = order[min_idx]
            order[min_idx] = tmp
    pids = []
    for i in range(n):
        pids.append(results[order[i]][0])
    return pids
