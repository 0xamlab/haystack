"""Exact analytic variance ratio for the toy CRN environment — closed form, not quadrature.

Environment (strategy/crn.mojo): one factor x ~ U[0,1), cost 0.5, gamma 1.0, horizon H, THRESHOLD
policy with unit weight acts iff x >= theta. Per-step payoff p_theta(x) = (x - 0.5) * 1[x >= theta].

    E[p_theta]   = int_theta^1 (x - 0.5) dx          = 0.5*theta - theta^2/2
    E[p_theta^2] = int_theta^1 (x - 0.5)^2 dx        = (0.125 - (theta - 0.5)^3)/3

The PAIRED per-step difference for a < b is d(x) = p_b(x) - p_a(x) = -(x - 0.5) * 1[a <= x < b],
supported only on the disagreement slice [a, b):

    E[d]   = -(int_a^b (x - 0.5) dx)                 = -((b^2 - a^2)/2 - 0.5*(b - a))
    E[d^2] = int_a^b (x - 0.5)^2 dx                  = ((b - 0.5)^3 - (a - 0.5)^3)/3

Steps are i.i.d., so H multiplies every variance. UNPAIRED compares b on an independent scenario,
so its difference variance is Var(p_a) + Var(p_b).

The horizon cancels in the RATIO, which is a falsifiable prediction and is checked in
benchmarks/mojo_benchmarks/bench_crn_variance_reduction.mojo section [2] (169.5 / 172.9 / 168.3 at
horizons 16 / 64 / 256 against the exact 173.973).

Uses only the standard library plus nothing — scipy is not importable in this repo's pixi
environment, and none is needed: every integral here is a polynomial.

    /path/to/pixi/env/bin/python benchmarks/crn_analytic_reference.py

MEASURED against the shipped `crn_pairing_audit` at 2000 scenarios (Mojo section [1]):
gap 0.50 exact 4.2000 measured 4.2641 | 0.30 exact 10.0800 measured 10.3820 | 0.10 exact 173.9730
measured 172.9340 | 0.02 exact 19848.7157 measured 20155.1971. Worst relative error 5.2% across
3.7 orders of magnitude, all within the sampling error of a variance ratio at 2000 replications.
"""

from __future__ import annotations


def moments(theta: float) -> tuple[float, float]:
    e1 = 0.5 * theta - 0.5 * theta * theta
    e2 = (0.125 - (theta - 0.5) ** 3) / 3.0
    return e1, e2 - e1 * e1


def diff_moments(a: float, b: float) -> tuple[float, float]:
    e1 = -((b * b - a * a) / 2.0 - 0.5 * (b - a))
    e2 = ((b - 0.5) ** 3 - (a - 0.5) ** 3) / 3.0
    return e1, e2 - e1 * e1


def main() -> None:
    h = 64
    print("exact analytic ratio for the shipped toy environment, horizon", h)
    print(f"{'gap':>6} {'theta_a':>8} {'E[D]':>10} {'var_paired':>13} {'var_unpaired':>13} "
          f"{'ratio':>12} {'implied_rho':>12}")
    for gap in (0.50, 0.40, 0.30, 0.20, 0.10, 0.05, 0.02):
        a, b = 0.5 - gap, 0.5
        _ea, va = moments(a)
        _eb, vb = moments(b)
        ed, vd = diff_moments(a, b)
        vp = h * vd
        vu = h * (va + vb)
        rho = (va + vb - vd) / (2.0 * (va * vb) ** 0.5)
        print(f"{gap:6.2f} {a:8.2f} {h * ed:10.6f} {vp:13.8f} {vu:13.8f} {vu / vp:12.4f} "
              f"{rho:12.6f}")
    print()
    print("effect-to-noise |E[D]| / sd_unpaired, the scale-free way to say 'how similar':")
    for gap in (0.50, 0.30, 0.20, 0.10, 0.05, 0.02):
        a, b = 0.5 - gap, 0.5
        _ea, va = moments(a)
        _eb, vb = moments(b)
        ed, vd = diff_moments(a, b)
        vu = h * (va + vb)
        print(f"  gap {gap:4.2f}: |E[D]|={abs(h * ed):.6f}  sd_unpaired={vu ** 0.5:.6f}  "
              f"ratio_of_those={abs(h * ed) / vu ** 0.5:.4f}")
    print()
    print("M/M/1 exact deltas for the queue arm (lam=0.80):")
    for mu_b in (1.005, 1.01, 1.02, 1.05, 1.10):
        wa = 0.80 / (1.0 * (1.0 - 0.80))
        wb = 0.80 / (mu_b * (mu_b - 0.80))
        print(f"  mu_B={mu_b:5.3f}  Wq_A={wa:.6f} Wq_B={wb:.6f} delta={wb - wa:+.6f} "
              f"relative={(wb - wa) / wa * 100:+.2f}%")
    print("DONE")


if __name__ == "__main__":
    main()
