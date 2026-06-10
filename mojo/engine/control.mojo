"""
control.mojo — PID Controller & Control Systems. Zero Python imports.

Replaces python-control with pure Mojo implementations of PID control,
bang-bang control, step/ramp response, settling time, overshoot, and
steady-state error analysis.

Public API:
  PIDState              — PID controller state struct
  create_pid            — Initialize PID controller
  pid_update            — Single PID step
  pid_simulate          — Simulate PID on first-order plant
  bang_bang              — Bang-bang (on/off) control
  step_response         — First-order step response
  ramp_response         — First-order ramp response
  settling_time         — Time to settle within tolerance
  overshoot             — Max overshoot fraction
  steady_state_error    — |final_value - setpoint|
"""

from std.math import exp, abs as fabs


# ── PIDState ─────────────────────────────────────────────────────────────────


@fieldwise_init
struct PIDState:
    """State for a PID controller."""
    var kp: Float64
    var ki: Float64
    var kd: Float64
    var integral: Float64
    var prev_error: Float64
    var output_min: Float64
    var output_max: Float64

    fn __init__(out self, kp: Float64, ki: Float64, kd: Float64,
                output_min: Float64, output_max: Float64):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_error = 0.0
        self.output_min = output_min
        self.output_max = output_max


# ── create_pid ───────────────────────────────────────────────────────────────


fn create_pid(kp: Float64, ki: Float64, kd: Float64,
              output_min: Float64 = -1e18, output_max: Float64 = 1e18) -> PIDState:
    """Initialize a PID controller.

    Args:
        kp: Proportional gain.
        ki: Integral gain.
        kd: Derivative gain.
        output_min: Minimum output clamp.
        output_max: Maximum output clamp.

    Returns:
        Initialized PIDState.
    """
    return PIDState(kp, ki, kd, output_min, output_max)


# ── pid_update ───────────────────────────────────────────────────────────────


fn pid_update(mut state: PIDState, setpoint: Float64, measured: Float64,
              dt: Float64) -> Float64:
    """Compute one PID step.

    Args:
        state: Mutable PID state (integral and prev_error updated).
        setpoint: Desired value.
        measured: Current measured value.
        dt: Time step (must be > 0).

    Returns:
        Clamped control output.
    """
    var error = setpoint - measured
    state.integral += error * dt
    var derivative: Float64 = 0.0
    if dt > 0.0:
        derivative = (error - state.prev_error) / dt
    state.prev_error = error

    var output = state.kp * error + state.ki * state.integral + state.kd * derivative

    # Clamp
    if output < state.output_min:
        output = state.output_min
    if output > state.output_max:
        output = state.output_max
    return output


# ── pid_simulate ─────────────────────────────────────────────────────────────


fn pid_simulate(kp: Float64, ki: Float64, kd: Float64, setpoint: Float64,
                initial: Float64, plant_gain: Float64, dt: Float64,
                steps: Int) -> List[Float64]:
    """Simulate PID controlling a first-order plant.

    Plant model: y[n+1] = y[n] + plant_gain * u * dt

    Args:
        kp: Proportional gain.
        ki: Integral gain.
        kd: Derivative gain.
        setpoint: Desired output value.
        initial: Initial plant output.
        plant_gain: Plant gain factor.
        dt: Time step.
        steps: Number of simulation steps.

    Returns:
        List of plant output values (length = steps + 1).
    """
    var state = create_pid(kp, ki, kd)
    var trajectory = List[Float64](capacity=steps + 1)
    var y = initial
    trajectory.append(y)

    for i in range(steps):
        var u = pid_update(state, setpoint, y, dt)
        y = y + plant_gain * u * dt
        trajectory.append(y)
    return trajectory^


# ── bang_bang ─────────────────────────────────────────────────────────────────


fn bang_bang(setpoint: Float64, measured: Float64,
            hysteresis: Float64 = 0.0) -> Float64:
    """Bang-bang (on/off) control.

    Args:
        setpoint: Desired value.
        measured: Current measured value.
        hysteresis: Dead band half-width around setpoint.

    Returns:
        1.0 if measured < setpoint - hysteresis,
        0.0 if measured > setpoint + hysteresis,
        0.5 otherwise (within hysteresis band).
    """
    if measured < setpoint - hysteresis:
        return 1.0
    if measured > setpoint + hysteresis:
        return 0.0
    return 0.5


# ── step_response ────────────────────────────────────────────────────────────


fn step_response(gain: Float64, time_constant: Float64, dt: Float64,
                 steps: Int) -> List[Float64]:
    """First-order system step response: y(t) = gain * (1 - exp(-t/tau)).

    Args:
        gain: DC gain of the system.
        time_constant: Time constant tau (must be > 0).
        dt: Time step.
        steps: Number of output samples.

    Returns:
        List of response values (length = steps).
    """
    var result = List[Float64](capacity=steps)
    for i in range(steps):
        var t = Float64(i) * dt
        result.append(gain * (1.0 - exp(-t / time_constant)))
    return result^


# ── ramp_response ────────────────────────────────────────────────────────────


fn ramp_response(gain: Float64, time_constant: Float64, dt: Float64,
                 steps: Int) -> List[Float64]:
    """First-order ramp response: y(t) = gain * (t - tau*(1 - exp(-t/tau))).

    Args:
        gain: DC gain of the system.
        time_constant: Time constant tau (must be > 0).
        dt: Time step.
        steps: Number of output samples.

    Returns:
        List of response values (length = steps).
    """
    var result = List[Float64](capacity=steps)
    for i in range(steps):
        var t = Float64(i) * dt
        result.append(gain * (t - time_constant * (1.0 - exp(-t / time_constant))))
    return result^


# ── settling_time ────────────────────────────────────────────────────────────


fn settling_time(response: List[Float64], setpoint: Float64,
                 tolerance: Float64 = 0.02) -> Float64:
    """Time index at which response settles within tolerance band.

    Scans from the end to find the last time the response exits the
    tolerance band, then returns that index + 1.

    Args:
        response: List of response values.
        setpoint: Desired final value.
        tolerance: Fraction of setpoint for tolerance band.

    Returns:
        Index (as Float64) where response first permanently enters band.
        Returns -1.0 if never settles.
    """
    var band = fabs(setpoint) * tolerance
    if band < 1e-15:
        band = tolerance  # Fallback for setpoint ≈ 0

    var n = len(response)
    # Scan from end to find last violation
    var last_violation = -1
    for i in range(n):
        if fabs(response[i] - setpoint) > band:
            last_violation = i

    if last_violation == -1:
        return 0.0  # Always within band
    if last_violation == n - 1:
        return -1.0  # Never settled
    return Float64(last_violation + 1)


# ── overshoot ────────────────────────────────────────────────────────────────


fn overshoot(response: List[Float64], setpoint: Float64) -> Float64:
    """Maximum overshoot as fraction: (peak - setpoint) / setpoint.

    Args:
        response: List of response values.
        setpoint: Desired final value.

    Returns:
        Overshoot fraction. 0.0 if no overshoot or setpoint is 0.
    """
    if fabs(setpoint) < 1e-15:
        return 0.0

    var peak = response[0]
    for i in range(1, len(response)):
        if setpoint > 0.0:
            if response[i] > peak:
                peak = response[i]
        else:
            if response[i] < peak:
                peak = response[i]

    var os_val = (peak - setpoint) / fabs(setpoint)
    if os_val < 0.0:
        return 0.0
    return os_val


# ── steady_state_error ───────────────────────────────────────────────────────


fn steady_state_error(response: List[Float64], setpoint: Float64) -> Float64:
    """Absolute steady-state error: |final_value - setpoint|.

    Args:
        response: List of response values.
        setpoint: Desired final value.

    Returns:
        Absolute error at the last sample.
    """
    if len(response) == 0:
        return fabs(setpoint)
    return fabs(response[len(response) - 1] - setpoint)
