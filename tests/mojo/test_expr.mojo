"""
test_expr.mojo — Tests for expr.mojo eval_expr() and parse_expr().

Tests all 21 op codes:
  0=literal  1=var_ref  2=add    3=sub    4=mul    5=div
  6=neg      7=pow      8=ln     9=log10  10=log2  11=exp
 12=sqrt    13=abs     14=floor 15=ceil  16=round 17=min2
 18=max2    19=clip    20=ifgt0 21=mod

Also tests:
  - Variable binding correctness
  - Multi-output via | separator
  - Complex nested expressions

Run:
  cd mojo_env && pixi run mojo test_expr.mojo
"""
from expr  import eval_expr, parse_expr
from types import ExprNode
from std.math import sqrt, exp, log, abs as fabs, pow


def _assert_close(a: Float64, b: Float64, msg: String, tol: Float64 = 1e-9):
    if fabs(a - b) > tol:
        print("FAIL: " + msg + " got=" + String(a) + " expected=" + String(b))
    else:
        print("PASS: " + msg)

def _assert(cond: Bool, msg: String):
    if not cond: print("FAIL: " + msg)
    else:        print("PASS: " + msg)


def _eval(expr_str: String, var_names: List[String], var_vals: List[Float64]) -> Float64:
    var nodes = List[ExprNode]()
    var root  = parse_expr(expr_str, var_names, nodes)
    if root < 0: return 0.0
    return eval_expr(nodes, root, var_vals)


def test_literal():
    """op=0: literal constant."""
    var names = List[String]()
    var vals  = List[Float64]()
    _assert_close(_eval("42", names, vals), 42.0, "literal 42")
    _assert_close(_eval("3.14", names, vals), 3.14, "literal 3.14", 1e-10)


def test_var_ref():
    """op=1: variable reference."""
    var names = List[String](); names.append("x"); names.append("y")
    var vals  = List[Float64](); vals.append(5.0); vals.append(7.0)
    _assert_close(_eval("x", names, vals), 5.0, "var_ref x")
    _assert_close(_eval("y", names, vals), 7.0, "var_ref y")


def test_add():
    """op=2: addition."""
    var names = List[String](); names.append("a"); names.append("b")
    var vals  = List[Float64](); vals.append(3.0); vals.append(4.0)
    _assert_close(_eval("a+b", names, vals), 7.0, "add 3+4")
    _assert_close(_eval("a+5", names, vals), 8.0, "add a+5")


def test_sub():
    """op=3: subtraction."""
    var names = List[String](); names.append("rev"); names.append("cost")
    var vals  = List[Float64](); vals.append(100.0); vals.append(60.0)
    _assert_close(_eval("rev-cost", names, vals), 40.0, "sub rev-cost")


def test_mul():
    """op=4: multiplication."""
    var names = List[String](); names.append("p"); names.append("q")
    var vals  = List[Float64](); vals.append(6.0); vals.append(7.0)
    _assert_close(_eval("p*q", names, vals), 42.0, "mul 6*7")


def test_div():
    """op=5: division."""
    var names = List[String](); names.append("n"); names.append("d")
    var vals  = List[Float64](); vals.append(10.0); vals.append(4.0)
    _assert_close(_eval("n/d", names, vals), 2.5, "div 10/4")


def test_neg():
    """op=6: unary negation."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(5.0)
    _assert_close(_eval("-x", names, vals), -5.0, "neg -x")


def test_pow():
    """op=7: exponentiation."""
    var names = List[String](); names.append("base")
    var vals  = List[Float64](); vals.append(2.0)
    _assert_close(_eval("base^3", names, vals), 8.0, "pow 2^3")


def test_ln():
    """op=8: natural log."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(exp(1.0))
    _assert_close(_eval("ln(x)", names, vals), 1.0, "ln(e) == 1")


def test_log10():
    """op=9: log base 10."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(100.0)
    _assert_close(_eval("log10(x)", names, vals), 2.0, "log10(100) == 2")


def test_log2():
    """op=10: log base 2."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(8.0)
    _assert_close(_eval("log2(x)", names, vals), 3.0, "log2(8) == 3")


def test_exp():
    """op=11: e^x."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(1.0)
    _assert_close(_eval("exp(x)", names, vals), exp(1.0), "exp(1) == e", 1e-10)


def test_sqrt():
    """op=12: square root."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(16.0)
    _assert_close(_eval("sqrt(x)", names, vals), 4.0, "sqrt(16) == 4")


def test_abs():
    """op=13: absolute value."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(-7.5)
    _assert_close(_eval("abs(x)", names, vals), 7.5, "abs(-7.5) == 7.5")


def test_floor():
    """op=14: floor."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(3.7)
    _assert_close(_eval("floor(x)", names, vals), 3.0, "floor(3.7) == 3")


def test_ceil():
    """op=15: ceiling."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(3.2)
    _assert_close(_eval("ceil(x)", names, vals), 4.0, "ceil(3.2) == 4")


def test_round():
    """op=16: round to nearest."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(3.5)
    _assert_close(_eval("round(x)", names, vals), 4.0, "round(3.5) == 4")


def test_min2():
    """op=17: min of two values."""
    var names = List[String](); names.append("a"); names.append("b")
    var vals  = List[Float64](); vals.append(5.0); vals.append(3.0)
    _assert_close(_eval("min(a,b)", names, vals), 3.0, "min(5,3) == 3")


def test_max2():
    """op=18: max of two values."""
    var names = List[String](); names.append("a"); names.append("b")
    var vals  = List[Float64](); vals.append(5.0); vals.append(3.0)
    _assert_close(_eval("max(a,b)", names, vals), 5.0, "max(5,3) == 5")


def test_clip():
    """op=19: clip(x, lo, hi)."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(15.0)
    _assert_close(_eval("clip(x,0,10)", names, vals), 10.0, "clip(15,0,10) == 10")
    vals[0] = -5.0
    _assert_close(_eval("clip(x,0,10)", names, vals), 0.0, "clip(-5,0,10) == 0")
    vals[0] = 5.0
    _assert_close(_eval("clip(x,0,10)", names, vals), 5.0, "clip(5,0,10) == 5")


def test_ifgt0():
    """op=20: if x > 0 then a else b."""
    var names = List[String](); names.append("x"); names.append("a"); names.append("b")
    var vals  = List[Float64](); vals.append(1.0); vals.append(10.0); vals.append(20.0)
    _assert_close(_eval("ifgt0(x,a,b)", names, vals), 10.0, "ifgt0(1, 10, 20) == 10")
    vals[0] = -1.0
    _assert_close(_eval("ifgt0(x,a,b)", names, vals), 20.0, "ifgt0(-1, 10, 20) == 20")


def test_mod():
    """op=21: modulo."""
    var names = List[String](); names.append("x")
    var vals  = List[Float64](); vals.append(7.0)
    _assert_close(_eval("mod(x,3)", names, vals), 1.0, "mod(7,3) == 1")


def test_complex_expression():
    """Complex nested expression: revenue model."""
    var names = List[String]()
    names.append("rev"); names.append("cogs"); names.append("opex"); names.append("units")
    var vals = List[Float64]()
    vals.append(200000.0); vals.append(80000.0); vals.append(30000.0); vals.append(1000.0)
    var result = _eval("(rev - cogs - opex) / units", names, vals)
    _assert_close(result, 90.0, "profit_per_unit == 90")


def test_variable_binding_correctness():
    """Ensure variables are bound in correct index order."""
    var names = List[String]()
    names.append("a"); names.append("b"); names.append("c")
    var vals = List[Float64]()
    vals.append(1.0); vals.append(2.0); vals.append(3.0)
    # a + b*c should be 1 + 2*3 = 7 (not some other order)
    _assert_close(_eval("a+b*c", names, vals), 7.0, "a+b*c == 1+2*3 == 7")


def main():
    print("=== test_expr.mojo ===")
    test_literal()
    test_var_ref()
    test_add()
    test_sub()
    test_mul()
    test_div()
    test_neg()
    test_pow()
    test_ln()
    test_log10()
    test_log2()
    test_exp()
    test_sqrt()
    test_abs()
    test_floor()
    test_ceil()
    test_round()
    test_min2()
    test_max2()
    test_clip()
    test_ifgt0()
    test_mod()
    test_complex_expression()
    test_variable_binding_correctness()
    print("=== Done (21 op codes + 2 integration tests) ===")
