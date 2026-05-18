"""
boolean_algebra.mojo — Boolean Algebra. Zero Python imports.

Replaces sympy.logic basics with pure Mojo implementations of boolean
operations, truth table generation, DNF/CNF evaluation, tautology
checking, and aggregate boolean functions.

Public API:
  bool_and              — Logical AND
  bool_or               — Logical OR
  bool_not              — Logical NOT
  bool_xor              — Logical XOR
  bool_implies          — Implication (a → b)
  bool_iff              — Biconditional (a ↔ b)
  truth_table_2         — Generate truth table for 2-variable ops
  eval_dnf              — Evaluate DNF (OR of ANDs)
  eval_cnf              — Evaluate CNF (AND of ORs)
  is_tautology_2var     — Check if 2-var op is a tautology
  count_satisfying_2var — Count satisfying assignments for 2-var op
  majority_vote         — True if more than half are True
  parity                — XOR of all values
"""


# ── bool_and ─────────────────────────────────────────────────────────────────


fn bool_and(a: Bool, b: Bool) -> Bool:
    """Logical AND."""
    return a and b


# ── bool_or ──────────────────────────────────────────────────────────────────


fn bool_or(a: Bool, b: Bool) -> Bool:
    """Logical OR."""
    return a or b


# ── bool_not ─────────────────────────────────────────────────────────────────


fn bool_not(a: Bool) -> Bool:
    """Logical NOT."""
    return not a


# ── bool_xor ─────────────────────────────────────────────────────────────────


fn bool_xor(a: Bool, b: Bool) -> Bool:
    """Logical XOR."""
    return a != b


# ── bool_implies ─────────────────────────────────────────────────────────────


fn bool_implies(a: Bool, b: Bool) -> Bool:
    """Implication: a → b = ¬a ∨ b."""
    return (not a) or b


# ── bool_iff ─────────────────────────────────────────────────────────────────


fn bool_iff(a: Bool, b: Bool) -> Bool:
    """Biconditional: a ↔ b."""
    return a == b


# ── _apply_op_2 ─────────────────────────────────────────────────────────────


fn _apply_op_2(a: Bool, b: Bool, op: Int) -> Bool:
    """Apply a 2-variable operation by index.
    0=AND, 1=OR, 2=XOR, 3=IMPLIES, 4=IFF.
    """
    if op == 0:
        return bool_and(a, b)
    elif op == 1:
        return bool_or(a, b)
    elif op == 2:
        return bool_xor(a, b)
    elif op == 3:
        return bool_implies(a, b)
    elif op == 4:
        return bool_iff(a, b)
    return False


# ── truth_table_2 ───────────────────────────────────────────────────────────


fn truth_table_2(op: Int) -> List[List[Bool]]:
    """Generate truth table for 2 variables.
    op: 0=AND, 1=OR, 2=XOR, 3=IMPLIES, 4=IFF.
    Returns [[a, b, result], ...] for all 4 input combinations.
    """
    var table = List[List[Bool]]()
    # Iterate over all 4 combinations: FF, FT, TF, TT
    var vals = List[Bool]()
    vals.append(False)
    vals.append(True)
    for i in range(2):
        for j in range(2):
            var a = vals[i]
            var b = vals[j]
            var result = _apply_op_2(a, b, op)
            var row = List[Bool]()
            row.append(a)
            row.append(b)
            row.append(result)
            table.append(row^)
    return table^


# ── eval_dnf ─────────────────────────────────────────────────────────────────


fn eval_dnf(values: List[Bool], clauses: List[List[Int]]) -> Bool:
    """Evaluate DNF (OR of ANDs).
    Each clause is a list of variable indices (negative index = NOT that var).
    DNF is satisfied if ANY clause is satisfied.
    A clause is satisfied if ALL its literals are true.
    """
    for ci in range(len(clauses)):
        var clause_true = True
        for li in range(len(clauses[ci])):
            var lit = clauses[ci][li]
            var idx: Int
            var negated: Bool
            if lit < 0:
                idx = -lit - 1
                negated = True
            else:
                idx = lit - 1
                negated = False
            if idx < 0 or idx >= len(values):
                clause_true = False
                break
            var val = values[idx]
            if negated:
                val = not val
            if not val:
                clause_true = False
                break
        if clause_true:
            return True
    return False


# ── eval_cnf ─────────────────────────────────────────────────────────────────


fn eval_cnf(values: List[Bool], clauses: List[List[Int]]) -> Bool:
    """Evaluate CNF (AND of ORs).
    Each clause is a list of variable indices (negative index = NOT that var).
    CNF is satisfied if ALL clauses are satisfied.
    A clause is satisfied if ANY of its literals is true.
    """
    for ci in range(len(clauses)):
        var clause_true = False
        for li in range(len(clauses[ci])):
            var lit = clauses[ci][li]
            var idx: Int
            var negated: Bool
            if lit < 0:
                idx = -lit - 1
                negated = True
            else:
                idx = lit - 1
                negated = False
            if idx < 0 or idx >= len(values):
                continue
            var val = values[idx]
            if negated:
                val = not val
            if val:
                clause_true = True
                break
        if not clause_true:
            return False
    return True


# ── is_tautology_2var ────────────────────────────────────────────────────────


fn is_tautology_2var(op: Int) -> Bool:
    """Check if a 2-variable operation is a tautology (True for all inputs)."""
    var table = truth_table_2(op)
    for i in range(len(table)):
        if not table[i][2]:
            return False
    return True


# ── count_satisfying_2var ────────────────────────────────────────────────────


fn count_satisfying_2var(op: Int) -> Int:
    """Count satisfying assignments for 2-variable operation."""
    var table = truth_table_2(op)
    var count = 0
    for i in range(len(table)):
        if table[i][2]:
            count += 1
    return count


# ── majority_vote ────────────────────────────────────────────────────────────


fn majority_vote(values: List[Bool]) -> Bool:
    """True if more than half of the values are True."""
    var count = 0
    var n = len(values)
    for i in range(n):
        if values[i]:
            count += 1
    return count * 2 > n


# ── parity ───────────────────────────────────────────────────────────────────


fn parity(values: List[Bool]) -> Bool:
    """XOR of all values (True if odd number of True)."""
    var result = False
    for i in range(len(values)):
        if values[i]:
            result = not result
    return result
