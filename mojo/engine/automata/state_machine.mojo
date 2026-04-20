"""
state_machine.mojo — Finite state machine. Zero Python imports.
For workflow management, decision logic, and event-driven simulation.

Public API:
  Transition struct
  StateMachine struct — add_state, add_transition, fire, can_fire,
                        get_possible_events, reset, state_count, transition_count
"""


# ── Transition ────────────────────────────────────────────────────────────────


struct Transition(Copyable, Movable):
    """A single state machine transition: from_state --event--> to_state.
    guard_value: 0.0 = no guard, >0 = threshold (value must >= guard)."""

    var from_state: String
    var event: String
    var to_state: String
    var guard_value: Float64

    fn __init__(
        out self,
        from_state: String,
        event: String,
        to_state: String,
        guard_value: Float64 = 0.0,
    ):
        self.from_state = from_state
        self.event = event
        self.to_state = to_state
        self.guard_value = guard_value


# ── StateMachine ──────────────────────────────────────────────────────────────


struct StateMachine(Copyable, Movable):
    """Finite state machine with guard conditions and history tracking."""

    var current_state: String
    var states: List[String]
    var transitions: List[Transition]
    var history: List[String]
    var _initial_state: String

    fn __init__(out self, initial_state: String):
        self.current_state = initial_state
        self._initial_state = initial_state
        self.states = List[String]()
        self.transitions = List[Transition]()
        self.history = List[String]()
        self.history.append(initial_state)

    fn add_state(mut self, name: String):
        """Register a state name."""
        # Avoid duplicates
        for i in range(len(self.states)):
            if self.states[i] == name:
                return
        self.states.append(name)

    fn add_transition(
        mut self,
        from_s: String,
        event: String,
        to_s: String,
        guard: Float64 = 0.0,
    ):
        """Add a transition rule."""
        self.transitions.append(Transition(from_s, event, to_s, guard))

    fn _find_transition(
        self, event: String, value: Float64
    ) -> Int:
        """Find the index of a matching transition, or -1 if none."""
        for i in range(len(self.transitions)):
            var t_from = self.transitions[i].from_state
            var t_event = self.transitions[i].event
            var t_guard = self.transitions[i].guard_value
            if t_from == self.current_state and t_event == event:
                # Check guard
                if t_guard > 0.0 and value < t_guard:
                    continue
                return i
        return -1

    fn fire(mut self, event: String, value: Float64 = 0.0) -> Bool:
        """Attempt to fire an event. Returns True if a transition occurred."""
        var idx = self._find_transition(event, value)
        if idx < 0:
            return False
        self.current_state = self.transitions[idx].to_state
        self.history.append(self.current_state)
        return True

    fn can_fire(self, event: String, value: Float64 = 0.0) -> Bool:
        """Check whether an event can fire from the current state."""
        return self._find_transition(event, value) >= 0

    fn get_possible_events(self) -> List[String]:
        """Return list of events that can fire from the current state (ignoring guards)."""
        var events = List[String]()
        for i in range(len(self.transitions)):
            var t_from = self.transitions[i].from_state
            var t_event = self.transitions[i].event
            if t_from == self.current_state:
                # Avoid duplicates
                var found = False
                for j in range(len(events)):
                    if events[j] == t_event:
                        found = True
                        break
                if not found:
                    events.append(t_event)
        return events^

    fn reset(mut self):
        """Reset to initial state, clear history."""
        self.current_state = self._initial_state
        self.history = List[String]()
        self.history.append(self._initial_state)

    fn state_count(self) -> Int:
        """Number of registered states."""
        return len(self.states)

    fn transition_count(self) -> Int:
        """Number of registered transitions."""
        return len(self.transitions)
