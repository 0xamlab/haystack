"""
formal_logic.mojo — Formal Logic / Propositional Calculus. Zero Python imports.

Pure Mojo implementations of propositional logic connectives, inference
rules, and truth-table analysis.

Public API:
  truth_and                — Logical AND
  truth_or                 — Logical OR
  truth_not                — Logical NOT
  truth_implies            — Material implication (¬a ∨ b)
  truth_iff                — Biconditional (a ↔ b)
  truth_xor                — Exclusive OR
  truth_nand               — NOT AND
  truth_nor                — NOT OR
  modus_ponens             — If p and p→q, then q
  modus_tollens            — If ¬q and p→q, then ¬p
  hypothetical_syllogism   — If p→q and q→r, then p→r
  disjunctive_syllogism    — If p∨q and ¬p, then q
  is_tautology_2var        — Check 2-var function is tautology
  is_contradiction_2var    — Check 2-var function is contradiction
"""


# ── truth_and ────────────────────────────────────────────────────────────────


fn truth_and(a: Bool, b: Bool) -> Bool:
    """Logical AND: True iff both are True."""
    return a and b


# ── truth_or ─────────────────────────────────────────────────────────────────


fn truth_or(a: Bool, b: Bool) -> Bool:
    """Logical OR: True iff at least one is True."""
    return a or b


# ── truth_not ────────────────────────────────────────────────────────────────


fn truth_not(a: Bool) -> Bool:
    """Logical NOT: negation."""
    return not a


# ── truth_implies ────────────────────────────────────────────────────────────


fn truth_implies(a: Bool, b: Bool) -> Bool:
    """Material implication: a → b ≡ ¬a ∨ b."""
    return (not a) or b


# ── truth_iff ────────────────────────────────────────────────────────────────


fn truth_iff(a: Bool, b: Bool) -> Bool:
    """Biconditional: a ↔ b. True iff both have same truth value."""
    return a == b


# ── truth_xor ────────────────────────────────────────────────────────────────


fn truth_xor(a: Bool, b: Bool) -> Bool:
    """Exclusive OR: True iff exactly one is True."""
    return a != b


# ── truth_nand ───────────────────────────────────────────────────────────────


fn truth_nand(a: Bool, b: Bool) -> Bool:
    """NOT AND: ¬(a ∧ b)."""
    return not (a and b)


# ── truth_nor ────────────────────────────────────────────────────────────────


fn truth_nor(a: Bool, b: Bool) -> Bool:
    """NOT OR: ¬(a ∨ b)."""
    return not (a or b)


# ── modus_ponens ─────────────────────────────────────────────────────────────


fn modus_ponens(p: Bool, p_implies_q: Bool) -> Bool:
    """Modus ponens: If p is True and p→q is True, conclude q.
    Returns True (q) only when both premises hold.
    If premises don't hold, returns False (no valid conclusion)."""
    if p and p_implies_q:
        return True
    return False


# ── modus_tollens ────────────────────────────────────────────────────────────


fn modus_tollens(not_q: Bool, p_implies_q: Bool) -> Bool:
    """Modus tollens: If ¬q is True and p→q is True, conclude ¬p (True).
    Returns True (¬p) only when both premises hold."""
    if not_q and p_implies_q:
        return True
    return False


# ── hypothetical_syllogism ───────────────────────────────────────────────────


fn hypothetical_syllogism(p_implies_q: Bool, q_implies_r: Bool) -> Bool:
    """If p→q and q→r, then p→r.
    Returns True when both conditional premises are True."""
    return p_implies_q and q_implies_r


# ── disjunctive_syllogism ────────────────────────────────────────────────────


fn disjunctive_syllogism(p_or_q: Bool, not_p: Bool) -> Bool:
    """If p∨q and ¬p, then q.
    Returns True (concluding q) when both premises hold."""
    return p_or_q and not_p


# ── _eval_2var ───────────────────────────────────────────────────────────────


fn _eval_2var(fn_idx: Int, a: Bool, b: Bool) -> Bool:
    """Evaluate a 2-variable boolean function by index.
    fn_idx encodes one of 16 possible 2-var functions:
      0=contradiction, 1=AND, 2=a∧¬b, 3=a, 4=¬a∧b, 5=b,
      6=XOR, 7=OR, 8=NOR, 9=IFF, 10=¬b, 11=a→b reversed(b→a),
      12=¬a, 13=IMPLIES(a→b), 14=NAND, 15=tautology."""
    if fn_idx == 0:
        return False
    elif fn_idx == 1:
        return a and b
    elif fn_idx == 2:
        return a and (not b)
    elif fn_idx == 3:
        return a
    elif fn_idx == 4:
        return (not a) and b
    elif fn_idx == 5:
        return b
    elif fn_idx == 6:
        return a != b
    elif fn_idx == 7:
        return a or b
    elif fn_idx == 8:
        return not (a or b)
    elif fn_idx == 9:
        return a == b
    elif fn_idx == 10:
        return not b
    elif fn_idx == 11:
        return (not b) or a  # b → a
    elif fn_idx == 12:
        return not a
    elif fn_idx == 13:
        return (not a) or b  # a → b
    elif fn_idx == 14:
        return not (a and b)
    elif fn_idx == 15:
        return True
    return False


# ── is_tautology_2var ────────────────────────────────────────────────────────


fn is_tautology_2var(fn_idx: Int) -> Bool:
    """Check if a 2-variable function (by index) is a tautology (all True)."""
    var vals = List[Bool]()
    vals.append(False)
    vals.append(True)
    for i in range(2):
        for j in range(2):
            if not _eval_2var(fn_idx, vals[i], vals[j]):
                return False
    return True


# ── is_contradiction_2var ────────────────────────────────────────────────────


fn is_contradiction_2var(fn_idx: Int) -> Bool:
    """Check if a 2-variable function (by index) is a contradiction (all False)."""
    var vals = List[Bool]()
    vals.append(False)
    vals.append(True)
    for i in range(2):
        for j in range(2):
            if _eval_2var(fn_idx, vals[i], vals[j]):
                return False
    return True
