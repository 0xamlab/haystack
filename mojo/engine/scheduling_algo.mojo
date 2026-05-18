"""
scheduling_algo.mojo — CPU scheduling algorithms. Zero Python imports.

Replaces OS simulation Python code with pure Mojo implementations for
FCFS, SJF, priority scheduling, round-robin, and scheduling metrics.

Process format: List[List[Int]] where each is [arrival_time, burst_time, priority].
Result format:  List[List[Int]] where each is [process_id, start_time, finish_time, wait_time].
Round-robin result: [pid, finish_time, wait_time] per process.

Public API:
  fcfs                 — First Come First Served
  sjf                  — Shortest Job First (non-preemptive)
  priority_scheduling  — Priority scheduling (lower=higher, non-preemptive)
  round_robin          — Round-robin with quantum
  avg_wait_time        — Average waiting time
  avg_turnaround       — Average turnaround time
  throughput           — Processes / total_time
  cpu_utilization      — Sum burst / total_time
  gantt_chart          — Process IDs in execution order
"""


# ── _make_row4 helper ─────────────────────────────────────────────────────────


fn _make_row4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var row = List[Int]()
    row.append(a)
    row.append(b)
    row.append(c)
    row.append(d)
    return row^


fn _make_row3(a: Int, b: Int, c: Int) -> List[Int]:
    var row = List[Int]()
    row.append(a)
    row.append(b)
    row.append(c)
    return row^


# ── fcfs ──────────────────────────────────────────────────────────────────────


fn fcfs(processes: List[List[Int]]) -> List[List[Int]]:
    """First Come First Served scheduling.

    Sorts by arrival time, runs each to completion.
    Returns [pid, start_time, finish_time, wait_time] per process.
    """
    var n = len(processes)
    # Build index list sorted by arrival time
    var order = List[Int]()
    for i in range(n):
        order.append(i)
    # Simple selection sort by arrival time
    for i in range(n):
        var min_idx = i
        for j in range(i + 1, n):
            if processes[order[j]][0] < processes[order[min_idx]][0]:
                min_idx = j
        if min_idx != i:
            var tmp = order[i]
            order[i] = order[min_idx]
            order[min_idx] = tmp

    var results = List[List[Int]]()
    var current_time = 0
    for i in range(n):
        var pid = order[i]
        var arrival = processes[pid][0]
        var burst = processes[pid][1]
        if current_time < arrival:
            current_time = arrival
        var start = current_time
        var finish = start + burst
        var wait = start - arrival
        results.append(_make_row4(pid, start, finish, wait))
        current_time = finish
    return results^


# ── sjf ───────────────────────────────────────────────────────────────────────


fn sjf(processes: List[List[Int]]) -> List[List[Int]]:
    """Shortest Job First (non-preemptive).

    At each step, among arrived processes pick shortest burst.
    Returns [pid, start_time, finish_time, wait_time] per process.
    """
    var n = len(processes)
    var done = List[Bool]()
    for i in range(n):
        done.append(False)
    var results = List[List[Int]]()
    var current_time = 0
    var completed = 0
    while completed < n:
        # Find shortest burst among arrived, not-done processes
        var best = -1
        var best_burst = 2147483647  # INT_MAX
        for i in range(n):
            if not done[i] and processes[i][0] <= current_time:
                if processes[i][1] < best_burst:
                    best_burst = processes[i][1]
                    best = i
        if best == -1:
            # No process arrived yet, advance time
            var min_arrival = 2147483647
            for i in range(n):
                if not done[i] and processes[i][0] < min_arrival:
                    min_arrival = processes[i][0]
            current_time = min_arrival
            continue
        var arrival = processes[best][0]
        var burst = processes[best][1]
        var start = current_time
        var finish = start + burst
        var wait = start - arrival
        results.append(_make_row4(best, start, finish, wait))
        current_time = finish
        done[best] = True
        completed += 1
    return results^


# ── priority_scheduling ───────────────────────────────────────────────────────


fn priority_scheduling(processes: List[List[Int]]) -> List[List[Int]]:
    """Priority scheduling (lower number = higher priority, non-preemptive).

    Returns [pid, start_time, finish_time, wait_time] per process.
    """
    var n = len(processes)
    var done = List[Bool]()
    for i in range(n):
        done.append(False)
    var results = List[List[Int]]()
    var current_time = 0
    var completed = 0
    while completed < n:
        var best = -1
        var best_prio = 2147483647
        for i in range(n):
            if not done[i] and processes[i][0] <= current_time:
                if processes[i][2] < best_prio:
                    best_prio = processes[i][2]
                    best = i
        if best == -1:
            var min_arrival = 2147483647
            for i in range(n):
                if not done[i] and processes[i][0] < min_arrival:
                    min_arrival = processes[i][0]
            current_time = min_arrival
            continue
        var arrival = processes[best][0]
        var burst = processes[best][1]
        var start = current_time
        var finish = start + burst
        var wait = start - arrival
        results.append(_make_row4(best, start, finish, wait))
        current_time = finish
        done[best] = True
        completed += 1
    return results^


# ── round_robin ───────────────────────────────────────────────────────────────


fn round_robin(processes: List[List[Int]], quantum: Int) -> List[List[Int]]:
    """Round-robin scheduling with time quantum.

    Returns [pid, finish_time, wait_time] for each process (indexed by pid).
    """
    var n = len(processes)
    var remaining = List[Int]()
    var finish_time = List[Int]()
    var wait_time = List[Int]()
    for i in range(n):
        remaining.append(processes[i][1])
        finish_time.append(0)
        wait_time.append(0)

    var current_time = 0
    var done_count = 0
    var queue = List[Int]()
    var in_queue = List[Bool]()
    for i in range(n):
        in_queue.append(False)

    while done_count < n:
        # Add newly arrived processes to queue
        for i in range(n):
            if not in_queue[i] and processes[i][0] <= current_time and remaining[i] > 0:
                queue.append(i)
                in_queue[i] = True
        if len(queue) == 0:
            # Advance to next arrival
            var min_arr = 2147483647
            for i in range(n):
                if remaining[i] > 0 and processes[i][0] < min_arr:
                    min_arr = processes[i][0]
            current_time = min_arr
            continue

        var pid = queue[0]
        # Remove front of queue
        var new_queue = List[Int]()
        for i in range(1, len(queue)):
            new_queue.append(queue[i])
        queue = new_queue^

        var run_time = quantum
        if remaining[pid] < quantum:
            run_time = remaining[pid]
        current_time += run_time
        remaining[pid] -= run_time

        # Add any new arrivals during this quantum
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

    var results = List[List[Int]]()
    for i in range(n):
        results.append(_make_row3(i, finish_time[i], wait_time[i]))
    return results^


# ── avg_wait_time ─────────────────────────────────────────────────────────────


fn avg_wait_time(results: List[List[Int]]) -> Float64:
    """Average waiting time from results. Wait is last element of each row."""
    var n = len(results)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        var row_len = len(results[i])
        total += Float64(results[i][row_len - 1])
    return total / Float64(n)


# ── avg_turnaround ────────────────────────────────────────────────────────────


fn avg_turnaround(results: List[List[Int]]) -> Float64:
    """Average turnaround time: finish - arrival (for FCFS/SJF/priority results).

    For [pid, start, finish, wait] format: turnaround = finish - arrival.
    arrival = start - wait.
    """
    var n = len(results)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        var row_len = len(results[i])
        if row_len >= 4:
            # [pid, start, finish, wait]; arrival = start - wait
            var finish = results[i][2]
            var start = results[i][1]
            var wait = results[i][3]
            var arrival = start - wait
            total += Float64(finish - arrival)
        elif row_len >= 3:
            # round_robin: [pid, finish, wait]
            var finish = results[i][1]
            total += Float64(finish)
    return total / Float64(n)


# ── throughput ────────────────────────────────────────────────────────────────


fn throughput(results: List[List[Int]], total_time: Int) -> Float64:
    """Throughput: n_processes / total_time."""
    if total_time <= 0:
        return 0.0
    return Float64(len(results)) / Float64(total_time)


# ── cpu_utilization ───────────────────────────────────────────────────────────


fn cpu_utilization(results: List[List[Int]], total_time: Int) -> Float64:
    """CPU utilization: sum of burst times / total_time.

    For [pid, start, finish, wait]: burst = finish - start.
    """
    if total_time <= 0:
        return 0.0
    var busy: Float64 = 0.0
    for i in range(len(results)):
        var row_len = len(results[i])
        if row_len >= 4:
            busy += Float64(results[i][2] - results[i][1])
        elif row_len >= 3:
            busy += Float64(results[i][1] - results[i][2])
    return busy / Float64(total_time)


# ── gantt_chart ───────────────────────────────────────────────────────────────


fn gantt_chart(results: List[List[Int]]) -> List[Int]:
    """Process IDs in execution order (sorted by start_time).

    Assumes results have [pid, start, ...] format.
    """
    var n = len(results)
    var order = List[Int]()
    for i in range(n):
        order.append(i)
    # Sort by start_time (index 1)
    for i in range(n):
        var min_idx = i
        for j in range(i + 1, n):
            if results[order[j]][1] < results[order[min_idx]][1]:
                min_idx = j
        if min_idx != i:
            var tmp = order[i]
            order[i] = order[min_idx]
            order[min_idx] = tmp
    var pids = List[Int]()
    for i in range(n):
        pids.append(results[order[i]][0])
    return pids^
