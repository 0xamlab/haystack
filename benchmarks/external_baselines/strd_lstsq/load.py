"""NIST StRD linear-least-squares dataset loader and certified-value parser.

Reads the ASCII files exactly as NIST publishes them. No values are transcribed
by hand: the certified parameter estimates come out of the same file as the data.
"""

from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# name -> (n_predictor_columns, has_intercept, polynomial_degree_or_None)
MODELS = {
    "Norris": (1, True, 1),
    "Pontius": (1, True, 2),
    "NoInt1": (1, False, 1),
    "NoInt2": (1, False, 1),
    "Filip": (1, True, 10),
    "Longley": (6, True, None),
    "Wampler1": (1, True, 5),
    "Wampler2": (1, True, 5),
    "Wampler3": (1, True, 5),
    "Wampler4": (1, True, 5),
    "Wampler5": (1, True, 5),
}

ORDER = [
    "Norris",
    "NoInt1",
    "NoInt2",
    "Pontius",
    "Wampler1",
    "Wampler2",
    "Wampler3",
    "Wampler4",
    "Wampler5",
    "Longley",
    "Filip",
]

_FORTRAN = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))[EeDd]([+-]?\d+)$")


def _num(tok: str) -> float:
    m = _FORTRAN.match(tok)
    if m:
        return float(m.group(1) + "e" + m.group(2))
    return float(tok)


def _line_span(header: str, label: str):
    m = re.search(label + r"\s+\(lines\s+(\d+)\s+to\s+(\d+)\)", header)
    if not m:
        raise ValueError("no line span for " + label)
    return int(m.group(1)), int(m.group(2))


def load(name: str):
    """Return (X_columns, y, certified_beta) for one StRD dataset.

    X_columns is a list of columns in model order, intercept column included
    when the model has one, so len(X_columns) == len(certified_beta).
    """
    path = os.path.join(HERE, name + ".dat")
    with open(path, "r") as fh:
        lines = fh.read().split("\n")
    header = "\n".join(lines[:12])

    cv_lo, cv_hi = _line_span(header, "Certified Values")
    d_lo, d_hi = _line_span(header, "Data")

    beta = []
    for raw in lines[cv_lo - 1 : cv_hi]:
        toks = raw.split()
        if len(toks) >= 2 and re.fullmatch(r"B\d+", toks[0]):
            beta.append(_num(toks[1]))

    rows = []
    for raw in lines[d_lo - 1 : d_hi]:
        toks = raw.split()
        if not toks:
            continue
        rows.append([_num(t) for t in toks])

    npred, intercept, degree = MODELS[name]
    y = [r[0] for r in rows]
    if degree is not None:
        x = [r[1] for r in rows]
        # Powers by repeated multiplication, so the Mojo arm can build the
        # bit-identical design matrix with the same recipe.
        powers = [[1.0] * len(x)]
        for _ in range(degree):
            prev = powers[-1]
            powers.append([prev[i] * x[i] for i in range(len(x))])
        start = 0 if intercept else 1
        cols = [powers[k] for k in range(start, degree + 1)]
    else:
        cols = []
        if intercept:
            cols.append([1.0] * len(rows))
        for j in range(npred):
            cols.append([r[1 + j] for r in rows])

    if len(cols) != len(beta):
        raise ValueError(
            "%s: %d columns vs %d certified parameters" % (name, len(cols), len(beta))
        )
    return cols, y, beta


def raw(name: str):
    """Return (predictor_columns_as_published, y, certified_beta)."""
    path = os.path.join(HERE, name + ".dat")
    with open(path, "r") as fh:
        lines = fh.read().split("\n")
    header = "\n".join(lines[:12])
    cv_lo, cv_hi = _line_span(header, "Certified Values")
    d_lo, d_hi = _line_span(header, "Data")
    beta = []
    for r in lines[cv_lo - 1 : cv_hi]:
        toks = r.split()
        if len(toks) >= 2 and re.fullmatch(r"B\d+", toks[0]):
            beta.append(_num(toks[1]))
    rows = []
    for r in lines[d_lo - 1 : d_hi]:
        toks = r.split()
        if toks:
            rows.append([_num(t) for t in toks])
    npred = MODELS[name][0]
    y = [r[0] for r in rows]
    xcols = [[r[1 + j] for r in rows] for j in range(npred)]
    return xcols, y, beta


def fingerprint(cols, y) -> int:
    """XOR of every raw 64-bit pattern in the design matrix and response."""
    import struct

    acc = 0
    for col in cols:
        for v in col:
            acc ^= struct.unpack("<Q", struct.pack("<d", v))[0]
    for v in y:
        acc ^= struct.unpack("<Q", struct.pack("<d", v))[0]
    return acc


def lre(estimate: float, certified: float) -> float:
    """Log relative error, the StRD accuracy metric. 15.95 = full double agreement."""
    if certified == 0.0:
        rel = abs(estimate)
    else:
        rel = abs(estimate - certified) / abs(certified)
    if rel == 0.0:
        return 15.95
    v = -__import__("math").log10(rel)
    if v > 15.95:
        return 15.95
    if v < 0.0:
        return 0.0
    return v


def min_lre(estimates, certified) -> float:
    return min(lre(e, c) for e, c in zip(estimates, certified))
