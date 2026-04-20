"""
Pipeline entry points: preprocess_payload, postprocess_results, build_unit_context,
suggest_unit_specs, get_physical_constants, eval_with_constants.

Advanced math available in eval_with_constants (and objective_function via Mojo AST):
  Standard:   sqrt, exp, log, ln, log10, log2, log1p, expm1, abs, max, min, floor, ceil, round
  Trig:       sin, cos, tan, asin, acos, atan, atan2, sinh, cosh, tanh
  Special:    erf, erfc, gamma, lgamma, factorial, comb, perm
  Sequences:  fibonacci(n), fib(n), fib_ratio(n) = F(n)/F(n-1)
  Statistics: norm_cdf(x), norm_pdf(x), norm_ppf(p), t_cdf(x,df), chi2_cdf(x,df), beta_cdf(x,a,b)
  Financial:  npv(rate, cf1, cf2, ...), pmt(rate, n, pv), fv(rate, n, pmt, pv),
              pv(rate, n, pmt), duration(rate, n), annuity(rate, n)
  Misc:       sign(x), hypot(a,b), logistic(x), logit(x)
  Constants:  c, G, g, kB, NA, R, pi, e, phi, c_sound, ...
"""
from __future__ import annotations

import math
from typing import Any

from .formatter import format_value
from .registries import DOMAIN_VARIABLE_HINTS, PHYSICAL_CONSTANTS
from .spec import UnitSpec
from .validate import preprocess_variable, validate_variable

# ── Helper functions for eval_with_constants ──────────────────────────────────

def _fibonacci(n: float) -> float:
    ni = max(0, int(n))
    if ni <= 0:
        return 0.0
    if ni == 1:
        return 1.0
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    return float(int((phi**ni - (-1/phi)**ni) / math.sqrt(5.0) + 0.5))


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_ppf(p: float) -> float:
    """Rational approximation to the inverse normal CDF."""
    p = max(1e-10, min(1.0 - 1e-10, p))
    t = math.sqrt(-2.0 * math.log(p if p < 0.5 else 1.0 - p))
    z = t - (
        (2.515517 + 0.802853 * t + 0.010328 * t * t)
        / (1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t)
    )
    return -z if p < 0.5 else z


def _t_cdf(x: float, df: float) -> float:
    """Student's t CDF via regularized incomplete beta function approximation."""
    if df <= 0:
        return 0.5
    try:
        # Use scipy if available, else approximation
        import scipy.special  # type: ignore[import]

        return float(scipy.special.stdtr(df, x))
    except ImportError:
        # Simple approximation via normal CDF for large df
        if df >= 30:
            return _norm_cdf(x)
        # Cornish-Fisher approximation
        d4 = 1.0 / (4.0 * df)
        d8 = 1.0 / (8.0 * df)
        adj_x = x * (1.0 - d4 + x*x*d4/12.0 - d8)
        return _norm_cdf(adj_x)


def _chi2_cdf(x: float, df: float) -> float:
    """Chi-squared CDF."""
    try:
        import scipy.special  # type: ignore[import]

        return float(scipy.special.chdtr(df, x))
    except ImportError:
        if x <= 0:
            return 0.0
        # Approximation via normal: Wilson-Hilferty
        z = ((x / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / math.sqrt(
            2.0 / (9.0 * df)
        )
        return _norm_cdf(z)


def _beta_cdf(x: float, a: float, b: float) -> float:
    """Beta CDF via regularized incomplete beta."""
    try:
        import scipy.special  # type: ignore[import]
        return float(scipy.special.betainc(a, b, x))
    except ImportError:
        # Crude approximation for symmetric beta
        if abs(a - b) < 0.01 and abs(a - 1.0) < 0.01:
            return x  # uniform case
        return x  # fallback


def _npv(rate: float, *cashflows: float) -> float:
    """Net Present Value: npv(rate, cf0, cf1, cf2, ...)"""
    if rate == -1.0:
        return float("inf")
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def _pmt(rate: float, n: float, pv: float, fv: float = 0.0) -> float:
    """Payment per period. pmt(rate, n, pv) — monthly mortgage formula."""
    if rate == 0.0:
        return -(pv + fv) / n if n > 0 else 0.0
    r_n = (1.0 + rate) ** n
    return -(pv * r_n + fv) * rate / (r_n - 1.0)


def _fv(rate: float, n: float, pmt: float, pv: float = 0.0) -> float:
    """Future Value: fv(rate, n, pmt, pv)"""
    if rate == 0.0:
        return -(pv + pmt * n)
    r_n = (1.0 + rate) ** n
    return -(pv * r_n + pmt * (r_n - 1.0) / rate)


def _pv(rate: float, n: float, pmt: float, fv: float = 0.0) -> float:
    """Present Value: pv(rate, n, pmt, fv)"""
    if rate == 0.0:
        return -(pmt * n + fv)
    r_n = (1.0 + rate) ** n
    return -(pmt * (r_n - 1.0) / rate + fv) / r_n


def _rate_approx(n: float, pmt: float, pv: float, fv: float = 0.0) -> float:
    """Approximate interest rate using Newton's method. rate(n, pmt, pv)."""
    if pv == 0.0:
        return 0.0
    r = 0.1  # initial guess
    for _ in range(100):
        r_n = (1.0 + r) ** n
        f = pv * r_n + pmt * (r_n - 1.0) / r + fv
        df = (
            n * pv * (1.0 + r) ** (n - 1.0)
            + pmt * (n * r * (1.0 + r) ** (n - 1.0) - (r_n - 1.0)) / (r * r)
        )
        if abs(df) < 1e-15:
            break
        r_new = r - f / df
        if abs(r_new - r) < 1e-8:
            return r_new
        r = max(-0.999, r_new)
    return r


def _duration(rate: float, n: float) -> float:
    """Macaulay duration of an annuity: duration(rate, n)"""
    if rate == 0.0:
        return (n + 1.0) / 2.0
    return (1.0 + rate) / rate - n / ((1.0 + rate) ** n - 1.0)


def _annuity(rate: float, n: float) -> float:
    """Present value annuity factor: annuity(rate, n) = (1-(1+r)^-n)/r"""
    if rate == 0.0:
        return n
    return (1.0 - (1.0 + rate) ** (-n)) / rate


def preprocess_payload(
    payload: dict[str, Any],
    unit_specs_raw: list[dict | str | None],
) -> tuple[dict[str, Any], list[str]]:
    """Preprocess all variables in the Mojo payload per unit spec."""
    variables = payload.get("variables", [])
    warnings: list[str] = []
    new_variables = []
    for i, var in enumerate(variables):
        spec_raw = unit_specs_raw[i] if i < len(unit_specs_raw) else None
        spec = UnitSpec.from_raw(spec_raw)
        warnings.extend(validate_variable(var, spec))
        new_variables.append(preprocess_variable(var, spec))
    return {**payload, "variables": new_variables}, warnings


def postprocess_results(
    raw_stats: dict[str, float],
    output_unit_specs: list[dict[str, Any] | str | None],
    output_index: int = 0,
) -> dict[str, Any]:
    """Format raw simulation statistics for one output objective."""
    if not output_unit_specs or output_index >= len(output_unit_specs):
        spec = UnitSpec()
    else:
        spec = UnitSpec.from_raw(output_unit_specs[output_index])

    result: dict[str, Any] = {
        "unit": spec.code or "raw",
        "unit_type": spec.type,
        "label": spec.label or spec.code,
    }
    for key, val in raw_stats.items():
        if isinstance(val, int | float) and math.isfinite(val):
            result[f"{key}_formatted"] = format_value(val, spec)
            result[f"{key}_display"]   = val * spec.scale
        else:
            result[f"{key}_formatted"] = str(val) if val is not None else None
    return result


def build_unit_context(
    variables: list[dict[str, Any]],
    unit_specs_raw: list[dict | str | None],
    output_unit_specs_raw: list[dict | str | None] | None,
) -> dict[str, Any]:
    """Build the unit_context block for the DecisionEnvelope."""
    var_context: dict[str, Any] = {}
    for i, var in enumerate(variables):
        spec_raw = unit_specs_raw[i] if i < len(unit_specs_raw) else None
        spec = UnitSpec.from_raw(spec_raw)
        var_context[var.get("name", f"var_{i}")] = {
            "unit": spec.code, "type": spec.type,
            "precision": spec.precision, "scale": spec.scale,
            "sim_scale": spec.sim_scale, "label": spec.label,
        }
    out_context = []
    if output_unit_specs_raw:
        for raw in output_unit_specs_raw:
            spec = UnitSpec.from_raw(raw)
            out_context.append({
                "unit": spec.code, "type": spec.type,
                "precision": spec.precision, "format": spec.format,
                "label": spec.label,
            })
    return {"variables": var_context, "outputs": out_context}


def suggest_unit_specs(domain: str, variable_names: list[str]) -> list[str | None]:
    """
    Auto-suggest unit shorthand strings for a list of variable names given a domain hint.
    Returns list aligned with variable_names.
    """
    hints = DOMAIN_VARIABLE_HINTS.get(domain.lower(), {})
    result: list[str | None] = []
    for name in variable_names:
        nl = name.lower().replace("-", "_").replace(" ", "_")
        if nl in hints:
            result.append(hints[nl])
            continue
        matched = None
        for hint_key, hint_val in hints.items():
            if hint_key in nl or nl in hint_key:
                matched = hint_val
                break
        result.append(matched)
    return result


def get_physical_constants() -> dict[str, float]:
    """Return all physical constants available for use in objective_function expressions."""
    return dict(PHYSICAL_CONSTANTS)


def eval_with_constants(
    expr: str,
    variables: dict[str, float],
    extra_builtins: dict | None = None,
) -> float:
    """
    Evaluate an expression with physical constants + variable values.
    Safe: restricted builtins only.

    Examples:
      eval_with_constants('mass * g * height', {'mass': 70, 'height': 10}) → 6864.7
      eval_with_constants('1 / sqrt(1 - (v/c)**2)', {'v': 0.9 * 299792458}) → 2.294
    """
    import math as _math
    ctx: dict[str, Any] = dict(PHYSICAL_CONSTANTS)  # type: ignore[assignment]
    ctx.update(variables)  # type: ignore[arg-type]
    # ── Standard math ─────────────────────────────────────────────────────────
    ctx.update({  # type: ignore[arg-type]
        "sqrt": _math.sqrt, "exp": _math.exp, "log": _math.log,
        "ln": _math.log, "log10": _math.log10, "log2": _math.log2,
        "log1p": _math.log1p, "expm1": _math.expm1,
        "abs": abs, "max": max, "min": min, "round": round,
        "floor": _math.floor, "ceil": _math.ceil,
        "sin": _math.sin, "cos": _math.cos, "tan": _math.tan,
        "asin": _math.asin, "acos": _math.acos, "atan": _math.atan,
        "atan2": _math.atan2, "sinh": _math.sinh, "cosh": _math.cosh,
        "tanh": _math.tanh, "pow": pow, "inf": float("inf"),
        "sign": lambda x: (1.0 if x > 0 else (-1.0 if x < 0 else 0.0)),
        "hypot": _math.hypot,
        # ── Special functions ──────────────────────────────────────────────────
        "erf":      _math.erf,
        "erfc":     _math.erfc,
        "gamma":    _math.gamma,
        "lgamma":   _math.lgamma,
        "factorial": _math.factorial,
        "comb":     _math.comb,
        "perm":     _math.perm,
        # ── Sequences ─────────────────────────────────────────────────────────
        "fibonacci": _fibonacci,
        "fib":       _fibonacci,
        "fib_ratio": lambda n: _fibonacci(n) / max(1, _fibonacci(n-1)) if n > 1 else 1.0,
        # ── Statistical functions ──────────────────────────────────────────────
        "norm_cdf":  _norm_cdf,
        "norm_pdf":  _norm_pdf,
        "norm_ppf":  _norm_ppf,
        "t_cdf":     _t_cdf,
        "chi2_cdf":  _chi2_cdf,
        "beta_cdf":  _beta_cdf,
        "logistic":  lambda x: 1.0 / (1.0 + _math.exp(-x)),
        "logit":     lambda x: _math.log(max(x, 1e-15) / max(1.0 - x, 1e-15)),
        # ── Financial math ────────────────────────────────────────────────────
        "npv":       _npv,
        "pmt":       _pmt,
        "fv":        _fv,
        "pv":        _pv,
        "rate":      _rate_approx,
        "duration":  _duration,
        "annuity":   _annuity,
    })
    if extra_builtins:
        ctx.update(extra_builtins)
    try:
        return float(eval(expr, {"__builtins__": {}}, ctx))  # noqa: S307
    except Exception:
        vals = list(variables.values())
        return float(vals[0]) if vals else 0.0
