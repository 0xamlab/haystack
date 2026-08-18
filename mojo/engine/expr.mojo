"""
Expression AST — zero-Python objective function evaluator and parser.
Imports ExprNode from types.mojo.
"""
from std.math import sqrt, exp, log, abs as fabs, pow, sin, cos, tan, asin, acos, atan
from types import ExprNode
from conv import span_to_str, span_to_str_end

# ── Extended math helpers (native approximations for special functions) ────────

def _erf_approx(x: Float64) -> Float64:
    """Abramowitz & Stegun approximation for erf(x), max error 1.5e-7."""
    var t = 1.0 / (1.0 + 0.3275911 * fabs(x))
    var y = 1.0 - (((((1.061405429*t - 1.453152027)*t) + 1.421413741)*t - 0.284496736)*t + 0.254829592)*t * exp(-x*x)
    return y if x >= 0.0 else -y

def _norm_cdf(x: Float64) -> Float64:
    """Standard normal CDF via erf approximation."""
    return 0.5 * (1.0 + _erf_approx(x / 1.4142135623730951))

def _norm_pdf(x: Float64) -> Float64:
    """Standard normal PDF."""
    return exp(-0.5 * x * x) / 2.5066282746310002

def _gamma_approx(x: Float64) -> Float64:
    """Lanczos approximation for Gamma(x), x > 0."""
    if x < 0.5:
        return 3.141592653589793 / (sin(3.141592653589793 * x) * _gamma_approx(1.0 - x))
    var xx = x - 1.0
    var b = xx + 7.5
    var c: Float64 = 0.99999999999980993
    c += 676.5203681218851 / (xx + 1.0)
    c += -1259.1392167224028 / (xx + 2.0)
    c += 771.32342877765313 / (xx + 3.0)
    c += -176.61502916214059 / (xx + 4.0)
    c += 12.507343278686905 / (xx + 5.0)
    c += -0.13857109526572012 / (xx + 6.0)
    c += 9.9843695780195716e-6 / (xx + 7.0)
    c += 1.5056327351493116e-7 / (xx + 8.0)
    return sqrt(6.283185307179586) * pow(b, xx + 0.5) * exp(-b) * c

def _factorial_f(n: Float64) -> Float64:
    """Factorial as float. Returns 0 for negative, caps at n=170 (Float64 overflow)."""
    var ni = Int(n)
    if ni < 0: return 0.0
    if ni > 170: return 1e308
    var r: Float64 = 1.0
    for i in range(2, ni + 1): r *= Float64(i)
    return r

def _fibonacci(n: Float64) -> Float64:
    """Fibonacci number F(n) using fast formula. F(0)=0, F(1)=1, ..."""
    var ni = Int(max(0.0, n))
    if ni <= 0: return 0.0
    if ni == 1: return 1.0
    var phi = (1.0 + sqrt(5.0)) / 2.0
    return Float64(Int((pow(phi, Float64(ni)) - pow(-1.0/phi, Float64(ni))) / sqrt(5.0) + 0.5))

def _sign(x: Float64) -> Float64:
    if x > 0.0: return 1.0
    if x < 0.0: return -1.0
    return 0.0

def _log1p_approx(x: Float64) -> Float64:
    """log(1+x) — accurate near 0."""
    if fabs(x) < 1e-10: return x - x*x/2.0 + x*x*x/3.0
    return log(1.0 + x)

def _expm1_approx(x: Float64) -> Float64:
    """exp(x)-1 — accurate near 0."""
    if fabs(x) < 1e-10: return x + x*x/2.0 + x*x*x/6.0
    return exp(x) - 1.0


# ── Evaluator ─────────────────────────────────────────────────────────────────

def eval_expr(nodes: List[ExprNode], idx: Int, sample: List[Float64]) -> Float64:
    if idx < 0 or idx >= len(nodes): return 0.0
    var n = nodes[idx].copy()
    if n.op == 0: return n.fval
    if n.op == 1: return sample[n.var_idx] if n.var_idx >= 0 and n.var_idx < len(sample) else 0.0
    if n.op == 2: return eval_expr(nodes, n.left, sample) + eval_expr(nodes, n.right, sample)
    if n.op == 3: return eval_expr(nodes, n.left, sample) - eval_expr(nodes, n.right, sample)
    if n.op == 4: return eval_expr(nodes, n.left, sample) * eval_expr(nodes, n.right, sample)
    if n.op == 5:
        var d = eval_expr(nodes, n.right, sample)
        return eval_expr(nodes, n.left, sample) / d if d != 0.0 else 0.0
    if n.op == 6: return -eval_expr(nodes, n.left, sample)
    if n.op == 7:
        var base = eval_expr(nodes, n.left, sample)
        var exp_v = eval_expr(nodes, n.right, sample)
        return pow(base, exp_v) if base >= 0.0 else 0.0
    if n.op == 8:
        var v = eval_expr(nodes, n.left, sample)
        return log(max(v, 1e-300))
    if n.op == 9:
        var v = eval_expr(nodes, n.left, sample)
        return log(max(v, 1e-300)) / 2.302585092994046
    if n.op == 10:
        var v = eval_expr(nodes, n.left, sample)
        return log(max(v, 1e-300)) / 0.6931471805599453
    if n.op == 11:
        var v = eval_expr(nodes, n.left, sample)
        return exp(min(v, 709.0))
    if n.op == 12:
        var v = eval_expr(nodes, n.left, sample)
        return sqrt(max(v, 0.0))
    if n.op == 13:
        return fabs(eval_expr(nodes, n.left, sample))
    if n.op == 14:
        var v = eval_expr(nodes, n.left, sample)
        return Float64(Int(v)) if v >= 0.0 else Float64(Int(v) - 1)
    if n.op == 15:
        var v = eval_expr(nodes, n.left, sample)
        var iv = Float64(Int(v))
        return iv if iv == v else iv + 1.0
    if n.op == 16:
        var v = eval_expr(nodes, n.left, sample)
        return Float64(Int(v + 0.5 if v >= 0.0 else v - 0.5))
    if n.op == 17:
        var a = eval_expr(nodes, n.left, sample)
        var b = eval_expr(nodes, n.right, sample)
        return a if a < b else b
    if n.op == 18:
        var a = eval_expr(nodes, n.left, sample)
        var b = eval_expr(nodes, n.right, sample)
        return a if a > b else b
    if n.op == 19:
        var v  = eval_expr(nodes, n.left, sample)
        var lo = eval_expr(nodes, n.right, sample)
        var hi = eval_expr(nodes, n.extra, sample) if n.extra >= 0 else 1e300
        return lo if v < lo else (hi if v > hi else v)
    if n.op == 20:
        var cond = eval_expr(nodes, n.left, sample)
        return eval_expr(nodes, n.right, sample) if cond > 0.0 else eval_expr(nodes, n.extra, sample)
    if n.op == 21:
        var a = eval_expr(nodes, n.left, sample)
        var b = eval_expr(nodes, n.right, sample)
        return a - Float64(Int(a / b)) * b if b != 0.0 else 0.0
    # ── Extended math ops (22-38) ─────────────────────────────────────────────
    if n.op == 22: return sin(eval_expr(nodes, n.left, sample))
    if n.op == 23: return cos(eval_expr(nodes, n.left, sample))
    if n.op == 24: return tan(eval_expr(nodes, n.left, sample))
    if n.op == 25: return asin(max(-1.0, min(1.0, eval_expr(nodes, n.left, sample))))
    if n.op == 26: return acos(max(-1.0, min(1.0, eval_expr(nodes, n.left, sample))))
    if n.op == 27: return atan(eval_expr(nodes, n.left, sample))
    if n.op == 28: return _gamma_approx(max(1e-10, eval_expr(nodes, n.left, sample)))
    if n.op == 29: return _erf_approx(eval_expr(nodes, n.left, sample))
    if n.op == 30: return _norm_cdf(eval_expr(nodes, n.left, sample))
    if n.op == 31: return _norm_pdf(eval_expr(nodes, n.left, sample))
    if n.op == 32: return _factorial_f(eval_expr(nodes, n.left, sample))
    if n.op == 33:  # comb(n, k)
        var nn = eval_expr(nodes, n.left, sample)
        var kk = eval_expr(nodes, n.right, sample)
        var nf = _factorial_f(nn); var kf = _factorial_f(kk); var nkf = _factorial_f(nn - kk)
        return nf / (kf * nkf) if kf > 0.0 and nkf > 0.0 else 0.0
    if n.op == 34: return _fibonacci(eval_expr(nodes, n.left, sample))
    if n.op == 35: return _sign(eval_expr(nodes, n.left, sample))
    if n.op == 36:  # hypot(a, b) = sqrt(a²+b²)
        var a = eval_expr(nodes, n.left, sample)
        var b = eval_expr(nodes, n.right, sample)
        return sqrt(a*a + b*b)
    if n.op == 37: return _log1p_approx(eval_expr(nodes, n.left, sample))
    if n.op == 38: return _expm1_approx(eval_expr(nodes, n.left, sample))
    return 0.0


# ── Parser helpers ────────────────────────────────────────────────────────────

def _try_atof_ok(s: String) -> Bool:
    try:
        _ = atof(s)
        return True
    except:
        return False

def _try_atof_val(s: String) -> Float64:
    try:
        return atof(s)
    except:
        return 0.0


def _find_arg_end(expr: String, start: Int) -> Int:
    """Find matching closing paren starting after '(' at start-1."""
    var depth = 1
    var i = start
    var bs = expr.as_bytes()
    var open_paren  = UInt8(ord("("))
    var close_paren = UInt8(ord(")"))
    while i < expr.byte_length():
        if bs[i] == open_paren:
            depth += 1
        elif bs[i] == close_paren:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return expr.byte_length() - 1


def _split_args(expr: String) -> List[String]:
    """Split comma-separated function args respecting nesting."""
    var args = List[String]()
    var depth = 0
    var start = 0
    var bs = expr.as_bytes()
    var open_paren  = UInt8(ord("("))
    var close_paren = UInt8(ord(")"))
    var open_brack  = UInt8(ord("["))
    var close_brack = UInt8(ord("]"))
    var comma       = UInt8(ord(","))
    for i in range(expr.byte_length()):
        var c = bs[i]
        if c == open_paren or c == open_brack:
            depth += 1
        elif c == close_paren or c == close_brack:
            depth -= 1
        elif c == comma and depth == 0:
            var seg = span_to_str(expr, start, i)
            args.append(String(seg.strip()))
            start = i + 1
    var seg2 = span_to_str_end(expr, start)
    var last = seg2.strip()
    if last.byte_length() > 0:
        args.append(String(last))
    return args^


# ── Main expression parser ────────────────────────────────────────────────────

def parse_expr(expr: String, var_names: List[String], mut nodes: List[ExprNode]) -> Int:
    """
    Universal expression parser.
    Operators: +, -, *, /, ^ (power), % (mod)
    Functions: ln, log10, log2, exp, sqrt, abs, floor, ceil, round,
               min(a,b), max(a,b), clip(v,lo,hi), if(cond,then,else), pow(a,b)
    Variable names and numeric literals are also supported.
    """
    var t = String(expr.strip())
    if t.byte_length() == 0:
        nodes.append(ExprNode(0, 0.0, -1, -1, -1)); return len(nodes) - 1

    if _try_atof_ok(String(t)):
        nodes.append(ExprNode(0, _try_atof_val(String(t)), -1, -1, -1))
        return len(nodes) - 1

    for i in range(len(var_names)):
        if t == var_names[i]:
            nodes.append(ExprNode(1, 0.0, i, -1, -1)); return len(nodes) - 1

    # ── Function calls ────────────────────────────────────────────────────────
    var fn_names = List[String]()
    fn_names.append("ln"); fn_names.append("log10"); fn_names.append("log2")
    fn_names.append("exp"); fn_names.append("sqrt"); fn_names.append("abs")
    fn_names.append("floor"); fn_names.append("ceil"); fn_names.append("round")
    fn_names.append("min"); fn_names.append("max"); fn_names.append("clip")
    fn_names.append("if"); fn_names.append("pow"); fn_names.append("log")
    # ── Extended math functions ────────────────────────────────────────────────
    fn_names.append("sin"); fn_names.append("cos"); fn_names.append("tan")
    fn_names.append("asin"); fn_names.append("acos"); fn_names.append("atan")
    fn_names.append("gamma"); fn_names.append("erf"); fn_names.append("norm_cdf")
    fn_names.append("norm_pdf"); fn_names.append("factorial"); fn_names.append("comb")
    fn_names.append("fibonacci"); fn_names.append("fib"); fn_names.append("sign")
    fn_names.append("hypot"); fn_names.append("log1p"); fn_names.append("expm1")

    var fn_opcodes = List[Int]()
    fn_opcodes.append(8);  fn_opcodes.append(9);  fn_opcodes.append(10)
    fn_opcodes.append(11); fn_opcodes.append(12); fn_opcodes.append(13)
    fn_opcodes.append(14); fn_opcodes.append(15); fn_opcodes.append(16)
    fn_opcodes.append(17); fn_opcodes.append(18); fn_opcodes.append(19)
    fn_opcodes.append(20); fn_opcodes.append(7);  fn_opcodes.append(8)
    # Extended opcodes — must match fn_names order above
    fn_opcodes.append(22); fn_opcodes.append(23); fn_opcodes.append(24)
    fn_opcodes.append(25); fn_opcodes.append(26); fn_opcodes.append(27)
    fn_opcodes.append(28); fn_opcodes.append(29); fn_opcodes.append(30)
    fn_opcodes.append(31); fn_opcodes.append(32); fn_opcodes.append(33)
    fn_opcodes.append(34); fn_opcodes.append(34); fn_opcodes.append(35)
    fn_opcodes.append(36); fn_opcodes.append(37); fn_opcodes.append(38)

    for fi in range(len(fn_names)):
        var fname = fn_names[fi]
        var flen  = fname.byte_length()
        var t_bytes  = t.as_bytes()
        var fn_bytes = fname.as_bytes()
        var t_prefix_match = True
        if t.byte_length() <= flen + 1:
            t_prefix_match = False
        else:
            for k in range(flen):
                if t_bytes[k] != fn_bytes[k]: t_prefix_match = False; break
            if t_prefix_match and t_bytes[flen] != UInt8(ord("(")): t_prefix_match = False
        if not t_prefix_match: continue

        var fop = fn_opcodes[fi]
        var arg_start = flen + 1
        var arg_end   = _find_arg_end(t, arg_start)
        var arg_str   = span_to_str(t, arg_start, arg_end)
        var args      = _split_args(arg_str)

        if len(args) == 1:
            var ai = parse_expr(args[0], var_names, nodes)
            nodes.append(ExprNode(fop, 0.0, -1, ai, -1)); return len(nodes) - 1
        elif len(args) == 2:
            var li = parse_expr(args[0], var_names, nodes)
            var ri = parse_expr(args[1], var_names, nodes)
            nodes.append(ExprNode(fop, 0.0, -1, li, ri)); return len(nodes) - 1
        elif len(args) == 3:
            var ai  = parse_expr(args[0], var_names, nodes)
            var bi  = parse_expr(args[1], var_names, nodes)
            var ci2 = parse_expr(args[2], var_names, nodes)
            var nd  = ExprNode(fop, 0.0, -1, ai, bi, ci2)
            nodes.append(nd^); return len(nodes) - 1

    # ── Operator scanning (byte-based) ────────────────────────────────────────
    var tb       = t.as_bytes()
    var ch_close = UInt8(ord(")"))
    var ch_open  = UInt8(ord("("))
    var ch_caret = UInt8(ord("^"))
    var ch_plus  = UInt8(ord("+"))
    var ch_minus = UInt8(ord("-"))
    var ch_star  = UInt8(ord("*"))
    var ch_slash = UInt8(ord("/"))
    var ch_pct   = UInt8(ord("%"))

    # ── Operator precedence: scan LOWEST first so outer splits happen before inner ──
    # 1. +/−  (lowest)
    # 2. *, /, %
    # 3. ^   (highest — only splits after lower-prec operators are resolved)

    # +/-
    var depth = 0; var sp = -1; var sop = 0
    for i in range(t.byte_length() - 1, -1, -1):
        var c = tb[i]
        if c == ch_close:   depth += 1
        elif c == ch_open:  depth -= 1
        elif depth == 0 and i > 0:
            if c == ch_plus:  sp = i; sop = 2; break
            elif c == ch_minus: sp = i; sop = 3; break
    if sp > 0:
        var li = parse_expr(String(span_to_str(t, 0, sp).strip()), var_names, nodes)
        var ri = parse_expr(String(span_to_str_end(t, sp+1).strip()), var_names, nodes)
        nodes.append(ExprNode(sop, 0.0, -1, li, ri)); return len(nodes) - 1

    # *, /, %
    depth = 0; sp = -1
    for i in range(t.byte_length() - 1, -1, -1):
        var c = tb[i]
        if c == ch_close:   depth += 1
        elif c == ch_open:  depth -= 1
        elif depth == 0 and i > 0:
            if c == ch_star:  sp = i; sop = 4; break
            elif c == ch_slash: sp = i; sop = 5; break
            elif c == ch_pct:   sp = i; sop = 21; break
    if sp > 0:
        var li = parse_expr(String(span_to_str(t, 0, sp).strip()), var_names, nodes)
        var ri = parse_expr(String(span_to_str_end(t, sp+1).strip()), var_names, nodes)
        nodes.append(ExprNode(sop, 0.0, -1, li, ri)); return len(nodes) - 1

    # ^ (power — highest precedence, only scanned after +/- and */ have been resolved)
    depth = 0; sp = -1
    for i in range(t.byte_length() - 1, -1, -1):
        var c = tb[i]
        if c == ch_close:   depth += 1
        elif c == ch_open:  depth -= 1
        elif depth == 0 and i > 0 and c == ch_caret:
            sp = i; break
    if sp > 0:
        var li = parse_expr(String(span_to_str(t, 0, sp).strip()), var_names, nodes)
        var ri = parse_expr(String(span_to_str_end(t, sp+1).strip()), var_names, nodes)
        nodes.append(ExprNode(7, 0.0, -1, li, ri)); return len(nodes) - 1

    # Strip outer parens
    if t.byte_length() > 2 and tb[0] == ch_open and tb[t.byte_length()-1] == ch_close:
        return parse_expr(span_to_str(t, 1, t.byte_length()-1), var_names, nodes)

    # Unary negation
    if t.byte_length() > 1 and tb[0] == ch_minus:
        var ci = parse_expr(String(span_to_str_end(t, 1).strip()), var_names, nodes)
        nodes.append(ExprNode(6, 0.0, -1, ci, -1)); return len(nodes) - 1

    nodes.append(ExprNode(0, 0.0, -1, -1, -1)); return len(nodes) - 1
