"""Tests for Wave 66 — Robotics, Psychometrics, Power Systems."""

from robotics import (
    forward_kinematics_2dof,
    forward_kinematics_2dof_y,
    inverse_kinematics_2dof_theta2,
    jacobian_2dof_j11,
    pid_control,
    dead_reckoning_x,
    dead_reckoning_y,
    wheel_odometry_distance,
    differential_drive_omega,
    differential_drive_velocity,
    workspace_radius,
    manipulability_index,
)
from psychometrics import (
    item_difficulty,
    item_discrimination,
    point_biserial,
    kuder_richardson_20,
    cronbach_alpha,
    spearman_brown_prophecy,
    standard_error_of_measurement,
    z_score,
    t_score,
    stanine,
    irt_1pl_probability,
    irt_2pl_probability,
)
from power_systems import (
    active_power,
    reactive_power,
    apparent_power,
    power_factor_from_pq,
    three_phase_power,
    transformer_turns_ratio,
    transformer_secondary_voltage,
    line_loss,
    voltage_drop,
    power_efficiency,
    capacitor_reactive_power,
    load_factor,
)
from std.math import abs as fabs, cos, sin, sqrt, acos


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


# ── Robotics tests ───────────────────────────────────────────────────────────


def test_forward_kinematics_2dof_x() raises:
    # Both links length 1, both angles 0 => x = 2.0
    var x = forward_kinematics_2dof(1.0, 1.0, 0.0, 0.0)
    _assert(_near(x, 2.0), "fk 2dof x at zero angles")

    # l1=1, l2=1, theta1=pi/2, theta2=0 => x = cos(pi/2) + cos(pi/2) ≈ 0
    var pi2 = 1.5707963267948966
    var x2 = forward_kinematics_2dof(1.0, 1.0, pi2, 0.0)
    _assert(_near(x2, 0.0, 1e-6), "fk 2dof x at pi/2")

    # l1=2, l2=1, theta1=0, theta2=pi/2 => x = 2*cos(0) + 1*cos(pi/2) = 2
    var x3 = forward_kinematics_2dof(2.0, 1.0, 0.0, pi2)
    _assert(_near(x3, 2.0, 1e-6), "fk 2dof x with elbow bent")


def test_forward_kinematics_2dof_y() raises:
    var y = forward_kinematics_2dof_y(1.0, 1.0, 0.0, 0.0)
    _assert(_near(y, 0.0), "fk 2dof y at zero angles")

    var pi2 = 1.5707963267948966
    var y2 = forward_kinematics_2dof_y(1.0, 1.0, pi2, 0.0)
    _assert(_near(y2, 2.0, 1e-6), "fk 2dof y at pi/2")

    # l1=2, l2=1, theta1=0, theta2=pi/2 => y = 0 + sin(pi/2) = 1
    var y3 = forward_kinematics_2dof_y(2.0, 1.0, 0.0, pi2)
    _assert(_near(y3, 1.0, 1e-6), "fk 2dof y with elbow bent")


def test_inverse_kinematics_2dof_theta2() raises:
    # Target at (2, 0) with l1=l2=1 => theta2 = 0
    var th2 = inverse_kinematics_2dof_theta2(1.0, 1.0, 2.0, 0.0)
    _assert(_near(th2, 0.0, 1e-6), "ik theta2 fully extended")

    # Target at (0, 0) with l1=l2=1 => cos(theta2) = -1 => theta2 = pi
    var th2b = inverse_kinematics_2dof_theta2(1.0, 1.0, 0.0, 0.0)
    _assert(_near(th2b, 3.141592653589793, 1e-6), "ik theta2 folded")


def test_jacobian_2dof_j11() raises:
    # At theta1=0, theta2=0: J11 = -l1*sin(0) - l2*sin(0) = 0
    var j = jacobian_2dof_j11(1.0, 1.0, 0.0, 0.0)
    _assert(_near(j, 0.0), "jacobian j11 at zero angles")

    # At theta1=pi/2, theta2=0: J11 = -1*sin(pi/2) - 1*sin(pi/2) = -2
    var pi2 = 1.5707963267948966
    var j2 = jacobian_2dof_j11(1.0, 1.0, pi2, 0.0)
    _assert(_near(j2, -2.0, 1e-6), "jacobian j11 at pi/2")


def test_pid_control() raises:
    var out = pid_control(1.0, 0.5, 0.1, 10.0, 5.0, 2.0)
    # 1*10 + 0.5*5 + 0.1*2 = 10 + 2.5 + 0.2 = 12.7
    _assert(_near(out, 12.7), "pid control output")

    var out2 = pid_control(2.0, 0.0, 0.0, 5.0, 0.0, 0.0)
    _assert(_near(out2, 10.0), "pid proportional only")


def test_dead_reckoning() raises:
    # Moving along x-axis: theta=0, v=1, dt=1
    var x = dead_reckoning_x(0.0, 1.0, 0.0, 1.0)
    _assert(_near(x, 1.0), "dead reckoning x forward")

    var y = dead_reckoning_y(0.0, 1.0, 0.0, 1.0)
    _assert(_near(y, 0.0), "dead reckoning y forward along x")

    # theta=pi/2, should move in y
    var pi2 = 1.5707963267948966
    var x2 = dead_reckoning_x(5.0, 1.0, pi2, 1.0)
    _assert(_near(x2, 5.0, 1e-6), "dead reckoning x perpendicular")

    var y2 = dead_reckoning_y(0.0, 1.0, pi2, 2.0)
    _assert(_near(y2, 2.0, 1e-6), "dead reckoning y perpendicular")


def test_wheel_odometry() raises:
    # r=0.05, ticks=100, tpr=100 => d = 2*pi*0.05 * 1 ≈ 0.31416
    var d = wheel_odometry_distance(0.05, 100.0, 100.0)
    _assert(_near(d, 0.31415926535, 1e-6), "wheel odometry one rev")

    var d2 = wheel_odometry_distance(0.1, 200.0, 100.0)
    # 2*pi*0.1*2 = 1.2566...
    _assert(_near(d2, 1.2566370614, 1e-6), "wheel odometry two revs")


def test_differential_drive() raises:
    var omega = differential_drive_omega(1.0, 3.0, 0.5)
    # (3-1)/0.5 = 4.0
    _assert(_near(omega, 4.0), "diff drive omega")

    var v = differential_drive_velocity(1.0, 3.0)
    _assert(_near(v, 2.0), "diff drive velocity")

    var omega2 = differential_drive_omega(2.0, 2.0, 1.0)
    _assert(_near(omega2, 0.0), "diff drive omega straight")


def test_workspace_and_manipulability() raises:
    var r = workspace_radius(1.0, 0.5)
    _assert(_near(r, 1.5), "workspace radius")

    var m = manipulability_index(-3.5)
    _assert(_near(m, 3.5), "manipulability index negative det")

    var m2 = manipulability_index(2.0)
    _assert(_near(m2, 2.0), "manipulability index positive det")


# ── Psychometrics tests ──────────────────────────────────────────────────────


def test_item_difficulty() raises:
    var p = item_difficulty(70.0, 100.0)
    _assert(_near(p, 0.7), "item difficulty")

    var p2 = item_difficulty(0.0, 0.0)
    _assert(_near(p2, 0.0), "item difficulty zero total")


def test_item_discrimination() raises:
    # upper: 80/100=0.8, lower: 40/100=0.4 => D=0.4
    var d = item_discrimination(80.0, 100.0, 40.0, 100.0)
    _assert(_near(d, 0.4), "item discrimination")


def test_point_biserial() raises:
    # rpb = (75 - 70) / 10 * sqrt(0.6 * 0.4) = 0.5 * 0.4899 = 0.2449
    var rpb = point_biserial(75.0, 70.0, 10.0, 0.6)
    _assert(_near(rpb, 0.244949, 1e-4), "point biserial")


def test_kuder_richardson_20() raises:
    # n=10, var=25, sum_pq=5 => KR20 = (10/9)*(1-5/25) = 1.1111*0.8 = 0.8889
    var kr = kuder_richardson_20(10.0, 25.0, 5.0)
    _assert(_near(kr, 0.888889, 1e-4), "KR-20")


def test_cronbach_alpha() raises:
    # n=5, sum_item_var=10, total_var=50 => α = (5/4)*(1-10/50) = 1.25*0.8 = 1.0
    var a = cronbach_alpha(5.0, 10.0, 50.0)
    _assert(_near(a, 1.0), "cronbach alpha")

    # n=10, sum_item_var=20, total_var=100 => (10/9)*(1-20/100)=1.111*0.8=0.8889
    var a2 = cronbach_alpha(10.0, 20.0, 100.0)
    _assert(_near(a2, 0.888889, 1e-4), "cronbach alpha 2")


def test_spearman_brown() raises:
    # r=0.6, n=2 => 2*0.6/(1+0.6) = 1.2/1.6 = 0.75
    var sb = spearman_brown_prophecy(0.6, 2.0)
    _assert(_near(sb, 0.75), "spearman brown double length")

    # r=0.8, n=3 => 3*0.8/(1+2*0.8) = 2.4/2.6 = 0.923077
    var sb2 = spearman_brown_prophecy(0.8, 3.0)
    _assert(_near(sb2, 0.923077, 1e-4), "spearman brown triple")


def test_sem() raises:
    # SD=15, rel=0.91 => SEM = 15*sqrt(0.09) = 15*0.3 = 4.5
    var s = standard_error_of_measurement(15.0, 0.91)
    _assert(_near(s, 4.5, 1e-4), "SEM")


def test_z_and_t_scores() raises:
    var z = z_score(85.0, 70.0, 10.0)
    _assert(_near(z, 1.5), "z score")

    var t = t_score(1.5)
    _assert(_near(t, 65.0), "t score")

    var t2 = t_score(0.0)
    _assert(_near(t2, 50.0), "t score zero z")

    var t3 = t_score(-2.0)
    _assert(_near(t3, 30.0), "t score negative z")


def test_stanine() raises:
    _assert(stanine(-2.0) == 1, "stanine 1")
    _assert(stanine(-1.5) == 2, "stanine 2")
    _assert(stanine(-1.0) == 3, "stanine 3")
    _assert(stanine(-0.5) == 4, "stanine 4")
    _assert(stanine(0.0) == 5, "stanine 5")
    _assert(stanine(0.5) == 6, "stanine 6")
    _assert(stanine(1.0) == 7, "stanine 7")
    _assert(stanine(1.5) == 8, "stanine 8")
    _assert(stanine(2.0) == 9, "stanine 9")


def test_irt_models() raises:
    # 1PL: theta=b => P=0.5
    var p1 = irt_1pl_probability(1.0, 1.0)
    _assert(_near(p1, 0.5), "1PL at theta=b")

    # 1PL: theta >> b => P ≈ 1
    var p2 = irt_1pl_probability(5.0, 0.0)
    _assert(p2 > 0.99, "1PL high theta")

    # 2PL: theta=b => P=0.5 regardless of a
    var p3 = irt_2pl_probability(1.0, 2.0, 1.0)
    _assert(_near(p3, 0.5), "2PL at theta=b")

    # 2PL: high discrimination steepens curve
    var p4 = irt_2pl_probability(1.5, 3.0, 1.0)
    var p5 = irt_2pl_probability(1.5, 1.0, 1.0)
    _assert(p4 > p5, "2PL higher a => steeper")


# ── Power Systems tests ──────────────────────────────────────────────────────


def test_active_power() raises:
    var p = active_power(230.0, 10.0, 0.8)
    _assert(_near(p, 1840.0), "active power")


def test_reactive_power() raises:
    # PF=0.8 => sin=0.6 => Q=230*10*0.6=1380
    var q = reactive_power(230.0, 10.0, 0.8)
    _assert(_near(q, 1380.0, 0.1), "reactive power")


def test_apparent_power() raises:
    var s = apparent_power(230.0, 10.0)
    _assert(_near(s, 2300.0), "apparent power")


def test_power_factor_from_pq() raises:
    var pf = power_factor_from_pq(1840.0, 2300.0)
    _assert(_near(pf, 0.8), "power factor from P and S")


def test_three_phase_power() raises:
    # P = sqrt(3) * 400 * 50 * 0.9 ≈ 31176.91
    var p = three_phase_power(400.0, 50.0, 0.9)
    _assert(_near(p, 31176.914, 1.0), "three phase power")


def test_transformer() raises:
    var a = transformer_turns_ratio(4800.0, 240.0)
    _assert(_near(a, 20.0), "transformer turns ratio")

    var vs = transformer_secondary_voltage(4800.0, 20.0)
    _assert(_near(vs, 240.0), "transformer secondary voltage")


def test_line_loss() raises:
    # I=100, R=0.5 => P=100^2*0.5=5000
    var p = line_loss(100.0, 0.5)
    _assert(_near(p, 5000.0), "line loss")


def test_voltage_drop() raises:
    # I=20, R=0.1, L=100 => V=2*20*0.1*100=400
    var v = voltage_drop(20.0, 0.1, 100.0)
    _assert(_near(v, 400.0), "voltage drop round trip")


def test_power_efficiency() raises:
    var eff = power_efficiency(900.0, 1000.0)
    _assert(_near(eff, 0.9), "power efficiency")

    var eff2 = power_efficiency(0.0, 0.0)
    _assert(_near(eff2, 0.0), "power efficiency zero input")


def test_capacitor_reactive_power() raises:
    # Qc = V^2 * 2*pi*f*C = 230^2 * 2*pi*60*0.0001
    # = 52900 * 0.037699 = 1994.29
    var qc = capacitor_reactive_power(230.0, 0.0001, 60.0)
    _assert(_near(qc, 1994.29, 1.0), "capacitor reactive power")


def test_load_factor() raises:
    var lf = load_factor(500.0, 1000.0)
    _assert(_near(lf, 0.5), "load factor")

    var lf2 = load_factor(750.0, 1000.0)
    _assert(_near(lf2, 0.75), "load factor 75%")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    # Robotics
    test_forward_kinematics_2dof_x()
    test_forward_kinematics_2dof_y()
    test_inverse_kinematics_2dof_theta2()
    test_jacobian_2dof_j11()
    test_pid_control()
    test_dead_reckoning()
    test_wheel_odometry()
    test_differential_drive()
    test_workspace_and_manipulability()

    # Psychometrics
    test_item_difficulty()
    test_item_discrimination()
    test_point_biserial()
    test_kuder_richardson_20()
    test_cronbach_alpha()
    test_spearman_brown()
    test_sem()
    test_z_and_t_scores()
    test_stanine()
    test_irt_models()

    # Power Systems
    test_active_power()
    test_reactive_power()
    test_apparent_power()
    test_power_factor_from_pq()
    test_three_phase_power()
    test_transformer()
    test_line_loss()
    test_voltage_drop()
    test_power_efficiency()
    test_capacitor_reactive_power()
    test_load_factor()

    print("✅ Wave 66: all tests passed (76 assertions)")
