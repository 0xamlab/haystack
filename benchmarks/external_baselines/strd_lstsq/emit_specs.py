"""Write one hex-bit-pattern spec file per NIST StRD linear-regression dataset.

Every float crosses into Mojo as a 16-digit hex IEEE-754 bit pattern, so the design matrix
the Mojo route builds is provably the same bits Python's reference arms see. An ASCII decimal
round trip would be *probably* identical and that is not the same claim.

Nothing is transcribed: the data rows, the line spans and the certified parameter values all
come out of the published .dat files via `load.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import load  # noqa: E402

DATA = os.path.join(HERE, "data")
load.HERE = DATA

# name -> (n_raw_predictor_columns, lo_degree, hi_degree, is_polynomial)
# lo_degree/hi_degree are the powers of the single predictor the published model fits.
# NoInt1/NoInt2 are y = B1*x with NO intercept, hence lo_degree 1.
SPEC = {
    "Norris": (1, 0, 1, True),
    "NoInt1": (1, 1, 1, True),
    "NoInt2": (1, 1, 1, True),
    "Pontius": (1, 0, 2, True),
    "Wampler1": (1, 0, 5, True),
    "Wampler2": (1, 0, 5, True),
    "Wampler3": (1, 0, 5, True),
    "Wampler4": (1, 0, 5, True),
    "Wampler5": (1, 0, 5, True),
    "Longley": (6, 0, 0, False),
    "Filip": (1, 0, 10, True),
}


def hx(v: float) -> str:
    return "%016x" % struct.unpack("<Q", struct.pack("<d", v))[0]


def main() -> None:
    out_dir = os.path.join(HERE, "specs")
    os.makedirs(out_dir, exist_ok=True)
    manifest = {}
    for name in load.ORDER:
        nraw, lo_deg, hi_deg, is_poly = SPEC[name]
        xcols, y, beta = load.raw(name)
        assert len(xcols) == nraw, (name, len(xcols), nraw)
        m = len(y)
        ncols = (hi_deg - lo_deg + 1) if is_poly else (nraw + 1)
        assert ncols == len(beta), (name, ncols, len(beta))
        lines = ["%d %d %d %d %d" % (m, nraw, lo_deg, hi_deg, 1 if is_poly else 0)]
        for i in range(m):
            row = [hx(y[i])] + [hx(xcols[j][i]) for j in range(nraw)]
            lines.append(" ".join(row))
        text = "\n".join(lines) + "\n"
        path = os.path.join(out_dir, name + ".spec")
        with open(path, "w") as fh:
            fh.write(text)
        with open(os.path.join(DATA, name + ".dat"), "rb") as fh:
            dat_sha = hashlib.sha256(fh.read()).hexdigest()
        manifest[name] = {
            "rows": m,
            "params": ncols,
            "raw_predictor_cols": nraw,
            "lo_degree": lo_deg,
            "hi_degree": hi_deg,
            "polynomial": is_poly,
            "certified": [repr(v) for v in beta],
            "certified_hex": [hx(v) for v in beta],
            "spec_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "dat_sha256": dat_sha,
        }
    with open(os.path.join(HERE, "specs", "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print("wrote %d specs to %s" % (len(manifest), out_dir))


if __name__ == "__main__":
    main()
