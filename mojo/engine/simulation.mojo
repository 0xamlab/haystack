"""
simulation.mojo — Discrete event simulation. Zero Python imports.

Replaces simpy with pure Mojo implementations for event scheduling,
processing, cancellation, and an M/M/1 queue simulator.

Public API:
  Event              — time, event_type, entity_id
  SimState           — clock, events, completed, next_id
  create_sim         — Initialize empty simulation
  schedule_event     — Schedule event at clock+delay
  next_event         — Pop earliest event, advance clock
  has_events         — Check if event queue non-empty
  run_until          — Process events until end_time
  cancel_event       — Remove event by entity_id
  sim_stats          — [total_processed, clock, events_remaining]
  mm1_simulate       — M/M/1 queue simulation
"""
from std.math import log


# ── We store events as three parallel lists for easy copy semantics ──────────


struct Event(Copyable, Movable):
    """A simulation event."""

    var time: Float64
    var event_type: Int
    var entity_id: Int

    fn __init__(out self, time: Float64, event_type: Int, entity_id: Int):
        self.time = time
        self.event_type = event_type
        self.entity_id = entity_id


# ── SimState struct (parallel arrays) ─────────────────────────────────────────


struct SimState(Copyable, Movable):
    """Simulation state using parallel arrays for event storage."""

    var clock: Float64
    var ev_time: List[Float64]
    var ev_type: List[Int]
    var ev_id: List[Int]
    var comp_time: List[Float64]
    var comp_type: List[Int]
    var comp_id: List[Int]
    var next_id: Int

    fn __init__(out self):
        self.clock = 0.0
        self.ev_time = List[Float64]()
        self.ev_type = List[Int]()
        self.ev_id = List[Int]()
        self.comp_time = List[Float64]()
        self.comp_type = List[Int]()
        self.comp_id = List[Int]()
        self.next_id = 0


# ── create_sim ────────────────────────────────────────────────────────────────


fn create_sim() -> SimState:
    """Initialize empty simulation state with clock=0."""
    return SimState()


# ── schedule_event ────────────────────────────────────────────────────────────


fn schedule_event(mut state: SimState, delay: Float64, event_type: Int) -> Int:
    """Schedule event at clock+delay. Returns entity_id. Insert sorted."""
    var eid = state.next_id
    state.next_id += 1
    var t = state.clock + delay
    # Find insertion position
    var n = len(state.ev_time)
    var pos = n
    for i in range(n):
        if t < state.ev_time[i]:
            pos = i
            break
    # Insert at pos by appending and shifting
    state.ev_time.append(0.0)
    state.ev_type.append(0)
    state.ev_id.append(0)
    var j = n
    while j > pos:
        state.ev_time[j] = state.ev_time[j - 1]
        state.ev_type[j] = state.ev_type[j - 1]
        state.ev_id[j] = state.ev_id[j - 1]
        j -= 1
    state.ev_time[pos] = t
    state.ev_type[pos] = event_type
    state.ev_id[pos] = eid
    return eid


# ── has_events ────────────────────────────────────────────────────────────────


fn has_events(state: SimState) -> Bool:
    """Check if event queue is non-empty."""
    return len(state.ev_time) > 0


# ── _remove_event_at (helper) ────────────────────────────────────────────────


fn _remove_event_at(mut state: SimState, idx: Int):
    """Remove event at given index by rebuilding lists."""
    var n = len(state.ev_time)
    var new_t = List[Float64]()
    var new_ty = List[Int]()
    var new_id = List[Int]()
    for i in range(n):
        if i != idx:
            new_t.append(state.ev_time[i])
            new_ty.append(state.ev_type[i])
            new_id.append(state.ev_id[i])
    state.ev_time = new_t^
    state.ev_type = new_ty^
    state.ev_id = new_id^


# ── next_event ────────────────────────────────────────────────────────────────


fn next_event(mut state: SimState) raises -> Event:
    """Pop the next event (earliest time), advance clock, add to completed."""
    if len(state.ev_time) == 0:
        raise Error("No events in queue")
    var t = state.ev_time[0]
    var ty = state.ev_type[0]
    var eid = state.ev_id[0]
    _remove_event_at(state, 0)
    state.clock = t
    state.comp_time.append(t)
    state.comp_type.append(ty)
    state.comp_id.append(eid)
    return Event(t, ty, eid)


# ── run_until ─────────────────────────────────────────────────────────────────


fn run_until(mut state: SimState, end_time: Float64) raises -> List[Event]:
    """Process all events until clock >= end_time. Returns processed list."""
    var proc_t = List[Float64]()
    var proc_ty = List[Int]()
    var proc_id = List[Int]()
    while len(state.ev_time) > 0:
        if state.ev_time[0] > end_time:
            break
        var evt = next_event(state)
        proc_t.append(evt.time)
        proc_ty.append(evt.event_type)
        proc_id.append(evt.entity_id)
    # Convert to Event list
    var result = List[Event]()
    for i in range(len(proc_t)):
        result.append(Event(proc_t[i], proc_ty[i], proc_id[i]))
    return result^


# ── cancel_event ──────────────────────────────────────────────────────────────


fn cancel_event(mut state: SimState, entity_id: Int) -> Bool:
    """Remove event by entity_id. Returns True if found and removed."""
    var n = len(state.ev_time)
    for i in range(n):
        if state.ev_id[i] == entity_id:
            _remove_event_at(state, i)
            return True
    return False


# ── sim_stats ─────────────────────────────────────────────────────────────────


fn sim_stats(state: SimState) -> List[Float64]:
    """Return [total_events_processed, current_clock, events_remaining]."""
    var result = List[Float64]()
    result.append(Float64(len(state.comp_time)))
    result.append(state.clock)
    result.append(Float64(len(state.ev_time)))
    return result^


# ── _lcg_next (helper) ───────────────────────────────────────────────────────


fn _lcg_next(seed: Int) -> Int:
    """Simple LCG random number generator."""
    return (1103515245 * seed + 12345) & 0x7FFFFFFF


fn _lcg_float(seed: Int) -> Float64:
    """Convert LCG state to float in (0, 1)."""
    var v = Float64(seed) / Float64(0x7FFFFFFF)
    if v <= 0.0:
        v = 1e-10
    if v >= 1.0:
        v = 1.0 - 1e-10
    return v


# ── mm1_simulate ──────────────────────────────────────────────────────────────


fn mm1_simulate(
    arrival_rate: Float64, service_rate: Float64, n_customers: Int
) -> List[Float64]:
    """Simulate M/M/1 queue. Returns [avg_wait, avg_system_time, utilization].

    Uses LCG-based exponential RNG for inter-arrival and service times.
    """
    var seed = 42
    var total_wait = 0.0
    var total_system = 0.0
    var total_service = 0.0
    var clock = 0.0
    var server_free_at = 0.0

    for _ in range(n_customers):
        # Generate exponential inter-arrival time
        seed = _lcg_next(seed)
        var u1 = _lcg_float(seed)
        var inter_arrival = -log(u1) / arrival_rate
        clock += inter_arrival

        # Generate exponential service time
        seed = _lcg_next(seed)
        var u2 = _lcg_float(seed)
        var service_time = -log(u2) / service_rate

        # Compute wait and system time
        var start_service: Float64
        if clock >= server_free_at:
            start_service = clock
        else:
            start_service = server_free_at
        var wait_time = start_service - clock
        var system_time = wait_time + service_time
        server_free_at = start_service + service_time

        total_wait += wait_time
        total_system += system_time
        total_service += service_time

    var n = Float64(n_customers)
    var avg_wait = total_wait / n
    var avg_system = total_system / n
    var utilization: Float64
    if server_free_at > 0.0:
        utilization = total_service / server_free_at
    else:
        utilization = 0.0

    var result = List[Float64]()
    result.append(avg_wait)
    result.append(avg_system)
    result.append(utilization)
    return result^
