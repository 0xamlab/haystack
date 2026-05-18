"""
category_theory.mojo — Functional programming patterns (Category Theory).
Pure Mojo, zero Python imports.

Public API:
  map_list_fn, filter_fn, fold_left, fold_right, compose,
  zip_with, scan_left, take_while, drop_while, flat_map
"""
from std.math import abs as fabs


# ── Functor Map ───────────────────────────────────────────────────────────────


fn _apply_op(x: Float64, op: Int) -> Float64:
    """Apply a unary op: 0=double, 1=square, 2=negate, 3=increment, 4=abs."""
    if op == 0:
        return x * 2.0
    elif op == 1:
        return x * x
    elif op == 2:
        return -x
    elif op == 3:
        return x + 1.0
    elif op == 4:
        return fabs(x)
    return x


fn map_list_fn(data: List[Float64], op: Int) -> List[Float64]:
    """Functor map: apply op to each element.
    op: 0=double, 1=square, 2=negate, 3=increment, 4=abs."""
    var out = List[Float64]()
    for i in range(len(data)):
        out.append(_apply_op(data[i], op))
    return out^


# ── Filter ────────────────────────────────────────────────────────────────────


fn _pred_holds(x: Float64, pred: Int, threshold: Float64) -> Bool:
    """Evaluate predicate: 0=greater, 1=less, 2=equal(tol), 3=nonzero."""
    if pred == 0:
        return x > threshold
    elif pred == 1:
        return x < threshold
    elif pred == 2:
        return fabs(x - threshold) < 1e-9
    elif pred == 3:
        return fabs(x) > 1e-15
    return True


fn filter_fn(
    data: List[Float64], pred: Int, threshold: Float64
) -> List[Float64]:
    """Filter elements by predicate.
    pred: 0=greater, 1=less, 2=equal(tol=1e-9), 3=nonzero."""
    var out = List[Float64]()
    for i in range(len(data)):
        if _pred_holds(data[i], pred, threshold):
            out.append(data[i])
    return out^


# ── Binary Op for folds ──────────────────────────────────────────────────────


fn _bin_op(a: Float64, b: Float64, op: Int) -> Float64:
    """Binary operation: 0=add, 1=multiply, 2=max, 3=min."""
    if op == 0:
        return a + b
    elif op == 1:
        return a * b
    elif op == 2:
        if a > b:
            return a
        return b
    elif op == 3:
        if a < b:
            return a
        return b
    return a + b


# ── Fold Left ─────────────────────────────────────────────────────────────────


fn fold_left(data: List[Float64], init: Float64, op: Int) -> Float64:
    """Left fold: accumulate from the left.
    op: 0=add, 1=multiply, 2=max, 3=min."""
    var acc = init
    for i in range(len(data)):
        acc = _bin_op(acc, data[i], op)
    return acc


# ── Fold Right ────────────────────────────────────────────────────────────────


fn fold_right(data: List[Float64], init: Float64, op: Int) -> Float64:
    """Right fold: accumulate from the right.
    op: 0=add, 1=multiply, 2=max, 3=min."""
    var acc = init
    var n = len(data)
    for i in range(n):
        acc = _bin_op(data[n - 1 - i], acc, op)
    return acc


# ── Compose ───────────────────────────────────────────────────────────────────


fn compose(data: List[Float64], op1: Int, op2: Int) -> List[Float64]:
    """Function composition: apply op1 then op2 to each element."""
    var out = List[Float64]()
    for i in range(len(data)):
        var intermediate = _apply_op(data[i], op1)
        out.append(_apply_op(intermediate, op2))
    return out^


# ── Zip With ──────────────────────────────────────────────────────────────────


fn zip_with(
    a: List[Float64], b: List[Float64], op: Int
) -> List[Float64]:
    """Zip two lists with a binary operation.
    op: 0=add, 1=multiply, 2=max, 3=min."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var out = List[Float64]()
    for i in range(n):
        out.append(_bin_op(a[i], b[i], op))
    return out^


# ── Scan Left ─────────────────────────────────────────────────────────────────


fn scan_left(
    data: List[Float64], init: Float64, op: Int
) -> List[Float64]:
    """Running accumulation (prefix scan).
    Returns list of length len(data)+1, starting with init."""
    var out = List[Float64]()
    var acc = init
    out.append(acc)
    for i in range(len(data)):
        acc = _bin_op(acc, data[i], op)
        out.append(acc)
    return out^


# ── Take While ────────────────────────────────────────────────────────────────


fn take_while(
    data: List[Float64], pred: Int, threshold: Float64
) -> List[Float64]:
    """Take elements from the front while predicate holds."""
    var out = List[Float64]()
    for i in range(len(data)):
        if not _pred_holds(data[i], pred, threshold):
            break
        out.append(data[i])
    return out^


# ── Drop While ────────────────────────────────────────────────────────────────


fn drop_while(
    data: List[Float64], pred: Int, threshold: Float64
) -> List[Float64]:
    """Drop elements from the front while predicate holds."""
    var out = List[Float64]()
    var dropping = True
    for i in range(len(data)):
        if dropping and _pred_holds(data[i], pred, threshold):
            continue
        dropping = False
        out.append(data[i])
    return out^


# ── Flat Map ──────────────────────────────────────────────────────────────────


fn flat_map(data: List[Float64], op: Int) -> List[Float64]:
    """Map then flatten.
    op=0: x → [x, -x]
    op=1: x → [x, x*x]."""
    var out = List[Float64]()
    for i in range(len(data)):
        var x = data[i]
        if op == 0:
            out.append(x)
            out.append(-x)
        elif op == 1:
            out.append(x)
            out.append(x * x)
        else:
            out.append(x)
    return out^
