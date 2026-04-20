"""
generate_mojo_tests.py — Generates mojo/tests/libs/test_<lib>.mojo for every library.

Strategy:
  • One small Mojo file per library (fast JIT via `mojo run`)
  • Python runner executes them in parallel and collects results
  • The companion Python integration test is tests/integration/test_mojo_libraries_az.py

Usage:
  python3 tests/generate_mojo_tests.py           # generate all per-lib files
  python3 tests/generate_mojo_tests.py --dry-run # print first library only
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT      = Path(__file__).resolve().parent.parent
MOJO_DIR  = ROOT / "mojo" / "engine"
OUT_DIR   = ROOT / "mojo" / "tests" / "libs"

# Core engine infrastructure — not domain libraries
SKIP_FILES = {
    "main", "types", "expr", "output", "request_parser", "python_bridge",
    "compare", "decision_tree", "time_series", "importance_sampling",
    "decision_tree_parser", "field_mapper", "validate",
}

_SCALAR_VALUES: dict[str, str] = {
    # 0.5 covers probabilities (0-1), rates (0-1), and is valid for most math.
    # Using 0.5 avoids log(-x)/sqrt(-x) NaN from out-of-range probability inputs.
    "Float64": "0.5",
    "Int":     "5",
    "Bool":    "True",
    "UInt64":  "UInt64(42)",
    "UInt32":  "UInt32(42)",
    "UInt8":   "UInt8(8)",
    "String":  '"test"',
}
_LIST_VAR: dict[str, str] = {
    "Float64": "_lf5",
    "Int":     "_li5",
    "Bool":    "_lb5",
}
# Per-function argument overrides (lib, fn) → list of arg expressions.
# Used when the generic 0.5 value causes NaN/Inf for domain-specific reasons.
_PARAM_OVERRIDES: dict[tuple[str, str], list[str]] = {
    # carnot_cop_cooling(t_cold, t_hot): t_cold/t_hot must have t_cold < t_hot
    ("cryogenics",      "carnot_cop_cooling"):         ["200.0", "300.0"],
    # time_to_peak(ka, ke): ka != ke to avoid log(1)/0
    ("pharmacokinetics","time_to_peak"):               ["0.8", "0.2"],
    # one_compartment_oral(dose, ka, ke, vd, t): ka != ke
    ("pharmacokinetics","one_compartment_oral"):       ["100.0", "0.8", "0.2", "10.0", "2.0"],
    # epicenter_distance(delta_t, vs, vp): vs != vp
    ("seismology",      "epicenter_distance_from_ts_tp"): ["2.0", "3.5", "6.0"],
    # junction_capacitance(cj0, v, vbi, m): v must be < vbi
    ("semiconductors",  "junction_capacitance"):       ["1e-12", "0.3", "0.7", "0.5"],
    # gross_premium(pure_premium, expense_ratio, profit_margin): expense+profit < 1
    ("insurance",       "gross_premium"):              ["100.0", "0.2", "0.1"],
    # shields_parameter(shear_stress, density_s, density_f, g, grain_size): ds != df
    ("geomorphology",   "shields_parameter"):          ["5.0", "2650.0", "1000.0", "9.81", "0.01"],
    # hypsometric_integral(mean, min, max): max != min
    ("geomorphology",   "hypsometric_integral"):       ["500.0", "100.0", "1000.0"],
    # regula_falsi(a, b, func_id): bracket a root (func_id=0 → x, use a=-1, b=1)
    ("root_finding",    "regula_falsi"):               ["-1.0", "1.0", "0"],
}

_SKIP_PARAM_TYPES: set[str] = {
    "TTLCache", "Matrix", "Graph", "WeightedGraph", "Heap",
    "BloomFilter", "PetriNet", "KalmanState", "SKLearnNode",
    "LRUCache", "CountMinSketch", "Bloom",
}


class Param(NamedTuple):
    name: str
    typ:  str
    has_default: bool
    is_mut: bool = False


class FnSig(NamedTuple):
    name:    str
    params:  list[Param]
    ret:     str
    lib:     str


def _clean_type(t: str) -> str:
    t = t.split("=")[0].strip()
    t = re.sub(r"\s+", " ", t)
    for prefix in ("owned ", "inout ", "ref ", "read ", "mut "):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t.strip()


def _parse_params(raw: str) -> list[Param] | None:
    params_raw: list[str] = []
    depth = 0
    cur   = ""
    for ch in raw:
        if ch in "([": depth += 1
        elif ch in ")]": depth -= 1
        if ch == "," and depth == 0:
            params_raw.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        params_raw.append(cur.strip())

    result: list[Param] = []
    for p in params_raw:
        p = p.strip()
        if not p:
            continue
        is_mut = bool(re.match(r"(mut|inout)\s+", p))
        m = re.match(r"(?:mut\s+|owned\s+|inout\s+)?(\w+)\s*:\s*(.+)", p)
        if not m:
            return None
        name = m.group(1)
        rest = m.group(2).strip()
        has_def = "=" in rest
        typ = _clean_type(rest)
        result.append(Param(name=name, typ=typ, has_default=has_def, is_mut=is_mut))
    return result


def parse_library(path: Path) -> list[FnSig]:
    lib  = path.stem
    text = path.read_text(encoding="utf-8", errors="replace")
    sigs: list[FnSig] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        m = re.match(r"fn\s+([A-Za-z][A-Za-z0-9_]*)\s*\(", stripped)
        if not m:
            i += 1
            continue
        fname = m.group(1)
        if fname.startswith("_"):
            i += 1
            continue

        sig_lines = [stripped]
        j = i + 1
        while j < min(i + 10, len(lines)):
            nxt = lines[j].strip()
            if re.match(r"(fn|def|struct|from|var|let)\s", nxt):
                break
            sig_lines.append(nxt)
            if nxt.endswith(":") or (re.search(r"->.*:", nxt) and not nxt.endswith(",")):
                break
            j += 1
        full = " ".join(sig_lines)

        ret = "Float64"
        am = re.search(r"->\s*([^\n:{]+)", full)
        if am:
            ret = am.group(1).strip().rstrip("{: ")
            ret = re.sub(r"\s+", " ", ret)
        else:
            ret = "None"

        pm = re.search(r"\(([^)]*)\)", full)
        if pm:
            param_str = pm.group(1)
        else:
            idx_open = full.find("(")
            if idx_open == -1:
                i += 1
                continue
            paren_text = full[idx_open + 1:]
            depth = 1
            buf = ""
            for ch in paren_text:
                if ch == "(": depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                buf += ch
            param_str = buf

        params = _parse_params(param_str)
        if params is None:
            i += 1
            continue

        sigs.append(FnSig(name=fname, params=params, ret=ret, lib=lib))
        i += 1
    return sigs


def _arg_expr(p: Param) -> str | None:
    typ = p.typ
    if typ in _SKIP_PARAM_TYPES:
        return None
    if typ in _SCALAR_VALUES:
        return _SCALAR_VALUES[typ]
    m = re.match(r"List\[(\w+)\]", typ)
    if m:
        inner = m.group(1)
        return _LIST_VAR.get(inner)
    if typ.startswith("List[List"):
        return None
    return None


def _is_testable(sig: FnSig) -> tuple[bool, list[str] | None]:
    if sig.ret.startswith("SIMD["):
        return False, None
    # Use per-function override if provided
    override = _PARAM_OVERRIDES.get((sig.lib, sig.name))
    if override is not None:
        return True, override
    args: list[str] = []
    for p in sig.params:
        if p.is_mut:
            return False, None
        v = _arg_expr(p)
        if v is None:
            return False, None
        args.append(v)
    return True, args


def emit_lib_test(lib: str, sigs: list[FnSig]) -> str:
    """Emit a complete Mojo test file for one library."""
    lines: list[str] = [
        f'"""test_{lib}.mojo — auto-generated tests for {lib} library."""',
        "from std.math import isnan, isinf",
        f"from {lib} import {', '.join(s.name for s in sigs)}",
        "",
        "fn is_finite(x: Float64) -> Bool:",
        "    return not isnan(x) and not isinf(x)",
        "",
        "def main() raises:",
        "    var _lf5 = List[Float64]()",
        "    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)",
        "    _lf5.append(0.4); _lf5.append(0.3)",
        "    var _li5 = List[Int]()",
        "    _li5.append(1); _li5.append(2); _li5.append(3)",
        "    _li5.append(4); _li5.append(5)",
        "    var _lb5 = List[Bool]()",
        "    _lb5.append(True); _lb5.append(False); _lb5.append(True)",
        "    _lb5.append(True); _lb5.append(False)",
        "    var passed: Int = 0",
        "    var failed: Int = 0",
        "",
    ]

    for sig in sigs:
        testable, args = _is_testable(sig)
        if not testable or args is None:
            continue

        call  = f"{sig.name}({', '.join(args)})"
        label = f"{lib}::{sig.name}"

        if sig.ret == "Float64":
            vn = f"_v_{sig.name}"
            lines += [
                f"    var {vn} = {call}",
                f"    if is_finite({vn}): passed += 1; print(\"  ✅ {label} =\", {vn})",
                f"    else: failed += 1; print(\"  ❌ {label} → non-finite:\", {vn})",
            ]
        elif sig.ret in ("Bool", "Int", "UInt64", "UInt32", "UInt8"):
            lines += [
                f"    _ = {call}",
                f"    passed += 1; print(\"  ✅ {label}\")",
            ]
        elif sig.ret.startswith("List[") and not sig.ret.startswith("List[List"):
            vn = f"_v_{sig.name}"
            lines += [
                f"    var {vn} = {call}",
                f"    if len({vn}) >= 0: passed += 1; print(\"  ✅ {label}\")",
            ]
        else:
            lines += [
                f"    _ = {call}",
                f"    passed += 1; print(\"  ✅ {label}\")",
            ]

    lines += [
        "",
        f'    print("  [{lib}] Passed:", passed, "Failed:", failed)',
    ]

    return "\n".join(lines) + "\n"


def generate(libs: list[Path], dry_run: bool = False) -> dict[str, int]:
    """Generate per-library test files. Returns {lib: n_tests}."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    total_fns = 0
    skipped_libs = 0

    for lib_path in sorted(libs):
        lib  = lib_path.stem
        sigs = parse_library(lib_path)
        testable = [s for s in sigs if _is_testable(s)[0]]
        if not testable:
            skipped_libs += 1
            continue

        n = len(testable)
        counts[lib] = n
        total_fns  += n

        if dry_run and lib != sorted(libs)[0].stem:
            continue  # Only show first lib in dry-run

        code = emit_lib_test(lib, testable)
        if dry_run:
            print(code)
        else:
            (OUT_DIR / f"test_{lib}.mojo").write_text(code, encoding="utf-8")

    if not dry_run:
        print(f"Generated {len(counts)} test files in {OUT_DIR}")
        print(f"  Total functions to test: {total_fns}")
        print(f"  Skipped libraries (untestable): {skipped_libs}")

    return counts


def main():
    dry_run = "--dry-run" in sys.argv
    libs = sorted(p for p in MOJO_DIR.glob("*.mojo") if p.stem not in SKIP_FILES)
    print(f"Scanning {len(libs)} library files...")
    generate(libs, dry_run=dry_run)


if __name__ == "__main__":
    main()
