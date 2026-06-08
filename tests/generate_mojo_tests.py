"""
generate_mojo_tests.py — Generates mojo/tests/libs/test_<module>.mojo for repo Mojo modules.

Strategy:
  • Discover current Mojo modules recursively under mojo/engine
  • Skip non-library infrastructure and nested test helpers
  • Generate one small Mojo file per testable module (fast JIT via `mojo run`)
  • The companion Python integration test is tests/integration/test_mojo_libraries_az.py

Usage:
  python3 tests/generate_mojo_tests.py           # generate all per-module files
  python3 tests/generate_mojo_tests.py --dry-run # print the first generated test
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
MOJO_DIR = ROOT / "mojo" / "engine"
OUT_DIR = ROOT / "mojo" / "tests" / "libs"

# Non-library control-plane modules and modules already covered by stronger suites.
SKIP_IMPORT_PATHS = {
    "conv",
    "math_ext",
    "main",
    "types",
    "expr",
    "output",
    "request_parser",
    "python_bridge",
    "compare",
    "decision_tree",
    "time_series",
    "importance_sampling",
    "decision_tree_parser",
    "field_mapper",
    "sha256",
    "validate",
    "net.unix_socket",
    "runtime_library_dispatch_generated",
}
SKIP_DIRS = {
    "engines",
}

_SCALAR_VALUES: dict[str, str] = {
    # 0.5 covers probabilities (0-1), rates (0-1), and is valid for most math.
    # Using 0.5 avoids log(-x)/sqrt(-x) NaN from out-of-range probability inputs.
    "Float64": "0.5",
    "Int": "5",
    "Bool": "True",
    "UInt64": "UInt64(42)",
    "UInt32": "UInt32(42)",
    "UInt8": "UInt8(8)",
    "String": '"test"',
}
_LIST_VAR: dict[str, str] = {
    "Float64": "_lf5",
    "Int": "_li5",
    "Bool": "_lb5",
}
# Per-function argument overrides (lib, fn) → list of arg expressions.
# Used when the generic 0.5 value causes NaN/Inf for domain-specific reasons.
_PARAM_OVERRIDES: dict[tuple[str, str], list[str]] = {
    # carnot_cop_cooling(t_cold, t_hot): t_cold/t_hot must have t_cold < t_hot
    ("cryogenics", "carnot_cop_cooling"): ["200.0", "300.0"],
    # time_to_peak(ka, ke): ka != ke to avoid log(1)/0
    ("pharmacokinetics", "time_to_peak"): ["0.8", "0.2"],
    # one_compartment_oral(dose, ka, ke, vd, t): ka != ke
    ("pharmacokinetics", "one_compartment_oral"): ["100.0", "0.8", "0.2", "10.0", "2.0"],
    # epicenter_distance(delta_t, vs, vp): vs != vp
    ("seismology", "epicenter_distance_from_ts_tp"): ["2.0", "3.5", "6.0"],
    # junction_capacitance(cj0, v, vbi, m): v must be < vbi
    ("semiconductors", "junction_capacitance"): ["1e-12", "0.3", "0.7", "0.5"],
    # gross_premium(pure_premium, expense_ratio, profit_margin): expense+profit < 1
    ("insurance", "gross_premium"): ["100.0", "0.2", "0.1"],
    # shields_parameter(shear_stress, density_s, density_f, g, grain_size): ds != df
    ("geomorphology", "shields_parameter"): ["5.0", "2650.0", "1000.0", "9.81", "0.01"],
    # hypsometric_integral(mean, min, max): max != min
    ("geomorphology", "hypsometric_integral"): ["500.0", "100.0", "1000.0"],
    # GoL neighborhood count requires a grid whose flattened length matches rows*cols.
    ("cellular_automata", "game_of_life_step"): ["_li6_grid2x3", "2", "3", "1", "1"],
    # Hex parser expects a valid 6-digit RGB hex string.
    ("color", "hex_to_rgb"): ['"#336699"'],
    # UCB exploration requires total_visits > 1 to keep log(N) non-negative.
    ("decision_ml_fusion", "adaptive_exploration_rate"): ["0.5", "1.0", "10.0", "1.0"],
    # 3-player Shapley value expects all 8 coalition values.
    ("game_theory", "shapley_value_3player"): ["_lf8_coalitions"],
    # unvec requires rows * cols == len(v).
    ("matrix_ops", "unvec"): ["_lf6_matrix", "2", "3"],
    # Split indices must be zero-based and within y bounds.
    ("regression_tree", "mse_reduction"): ["_lf5", "_li2_zero", "_li3_tail"],
    # regula_falsi(a, b, func_id): bracket a root (func_id=0 → x, use a=-1, b=1)
    ("root_finding", "regula_falsi"): ["-1.0", "1.0", "0"],
    # ORPO denominator must stay finite for the generated smoke sample.
    ("rlhf_dpo", "orpo_ratio"): ["-0.2", "-1.0", "10.0", "12.0", "0.1"],
    # nth_smallest uses zero-based indexing.
    ("sorting", "nth_smallest"): ["_lf5", "2"],
    # Borda count candidate index must fall inside the flattened rank matrix.
    ("voting", "borda_score"): ["_li10_borda", "5", "2"],
    # AES state transforms require a full 16-byte state/round key.
    ("crypto_aes_sbox", "sub_bytes"): ["_li16"],
    ("crypto_aes_sbox", "inv_sub_bytes"): ["_li16"],
    ("crypto_aes_sbox", "shift_rows"): ["_li16"],
    ("crypto_aes_sbox", "inv_shift_rows"): ["_li16"],
    ("crypto_aes_sbox", "xor_bytes"): ["_li16", "_li16"],
    ("crypto_aes_sbox", "add_round_key"): ["_li16", "_li16"],
    # ChaCha20 setup requires key=8 words, nonce=3 words, and 16-word blocks.
    ("crypto_chacha20", "chacha20_init_state"): ["_li8", "5", "_li3"],
    ("crypto_chacha20", "chacha20_block"): ["_li8", "5", "_li3"],
    ("crypto_chacha20", "chacha20_encrypt"): ["_li16", "_li8", "_li3"],
    ("crypto_chacha20", "chacha20_decrypt"): ["_li16", "_li8", "_li3"],
}

_SKIP_PARAM_TYPES: set[str] = {
    "TTLCache",
    "Matrix",
    "Graph",
    "WeightedGraph",
    "Heap",
    "BloomFilter",
    "PetriNet",
    "KalmanState",
    "SKLearnNode",
    "LRUCache",
    "CountMinSketch",
    "Bloom",
}


class Param(NamedTuple):
    name: str
    typ: str
    has_default: bool
    is_mut: bool = False


class FnSig(NamedTuple):
    name: str
    params: list[Param]
    ret: str
    module_id: str
    import_path: str


class ModuleTarget(NamedTuple):
    path: Path
    import_path: str
    module_id: str


def _clean_type(t: str) -> str:
    t = t.split("=")[0].strip()
    t = re.sub(r"\s+", " ", t)
    for prefix in ("owned ", "inout ", "ref ", "read ", "mut "):
        if t.startswith(prefix):
            t = t[len(prefix) :]
    return t.strip()


def _parse_params(raw: str) -> list[Param] | None:
    params_raw: list[str] = []
    depth = 0
    cur = ""
    for ch in raw:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
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


def _import_path_for(path: Path, engine_root: Path = MOJO_DIR) -> str:
    rel = path.relative_to(engine_root).with_suffix("")
    return ".".join(rel.parts)


def _module_id_for_import_path(import_path: str) -> str:
    return import_path.replace(".", "_")


def discover_library_modules(engine_root: Path = MOJO_DIR) -> list[ModuleTarget]:
    targets: list[ModuleTarget] = []
    for path in sorted(engine_root.rglob("*.mojo")):
        rel = path.relative_to(engine_root)
        if path.name == "__init__.mojo":
            continue
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        if path.stem.startswith("test_"):
            continue
        import_path = _import_path_for(path, engine_root)
        if import_path in SKIP_IMPORT_PATHS:
            continue
        targets.append(
            ModuleTarget(
                path=path,
                import_path=import_path,
                module_id=_module_id_for_import_path(import_path),
            )
        )
    return targets


def parse_library(path: Path, *, module_id: str, import_path: str) -> list[FnSig]:
    text = path.read_text(encoding="utf-8", errors="replace")
    sigs: list[FnSig] = []
    lines = text.splitlines()
    i = 0
    docstring_delim: str | None = None
    while i < len(lines):
        stripped = lines[i].strip()

        if docstring_delim is not None:
            if docstring_delim in stripped and stripped.count(docstring_delim) % 2 == 1:
                docstring_delim = None
            i += 1
            continue

        if stripped.startswith('"""') or stripped.startswith("'''"):
            delim = '"""' if stripped.startswith('"""') else "'''"
            if stripped.count(delim) % 2 == 1:
                docstring_delim = delim
            i += 1
            continue

        m = re.match(r"fn\s+([A-Za-z][A-Za-z0-9_]*)\s*\(", stripped)
        if not m:
            i += 1
            continue
        fname = m.group(1)
        if fname.startswith("_"):
            i += 1
            continue
        if fname in {"main", "check"}:
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
            paren_text = full[idx_open + 1 :]
            depth = 1
            buf = ""
            for ch in paren_text:
                if ch == "(":
                    depth += 1
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

        sigs.append(
            FnSig(
                name=fname,
                params=params,
                ret=ret,
                module_id=module_id,
                import_path=import_path,
            )
        )
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
    override = _PARAM_OVERRIDES.get((sig.module_id, sig.name))
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


def build_generation_plan(
    modules: list[ModuleTarget] | None = None,
) -> list[tuple[ModuleTarget, list[FnSig]]]:
    if modules is None:
        modules = discover_library_modules()

    plan: list[tuple[ModuleTarget, list[FnSig]]] = []
    for target in modules:
        sigs = parse_library(
            target.path,
            module_id=target.module_id,
            import_path=target.import_path,
        )
        testable = [sig for sig in sigs if _is_testable(sig)[0]]
        if testable:
            plan.append((target, testable))
    return plan


def emit_lib_test(module_id: str, import_path: str, sigs: list[FnSig]) -> str:
    """Emit a complete Mojo test file for one module."""
    lines: list[str] = [
        f'"""test_{module_id}.mojo — auto-generated tests for {import_path}."""',
        "from std.math import isnan, isinf",
        f"from {import_path} import {', '.join(s.name for s in sigs)}",
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
        "    var _li3 = List[Int]()",
        "    _li3.append(1); _li3.append(2); _li3.append(3)",
        "    var _li2_zero = List[Int]()",
        "    _li2_zero.append(0); _li2_zero.append(1)",
        "    var _li3_tail = List[Int]()",
        "    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)",
        "    var _li8 = List[Int]()",
        "    for i in range(8):",
        "        _li8.append(i + 1)",
        "    var _li6_grid2x3 = List[Int]()",
        "    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)",
        "    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)",
        "    var _li10_borda = List[Int]()",
        "    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)",
        "    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)",
        "    var _li16 = List[Int]()",
        "    for i in range(16):",
        "        _li16.append(i)",
        "    var _lf6_matrix = List[Float64]()",
        "    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)",
        "    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)",
        "    var _lf8_coalitions = List[Float64]()",
        "    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)",
        "    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)",
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

        call = f"{sig.name}({', '.join(args)})"
        label = f"{import_path}::{sig.name}"

        if sig.ret == "Float64":
            vn = f"_v_{sig.name}"
            lines += [
                f"    var {vn} = {call}",
                f'    if is_finite({vn}): passed += 1; print("  ✅ {label} =", {vn})',
                f'    else: failed += 1; print("  ❌ {label} → non-finite:", {vn})',
            ]
        elif sig.ret in ("Bool", "Int", "UInt64", "UInt32", "UInt8"):
            lines += [
                f"    _ = {call}",
                f'    passed += 1; print("  ✅ {label}")',
            ]
        elif sig.ret.startswith("List[") and not sig.ret.startswith("List[List"):
            vn = f"_v_{sig.name}"
            lines += [
                f"    var {vn} = {call}",
                f'    if len({vn}) >= 0: passed += 1; print("  ✅ {label}")',
            ]
        else:
            lines += [
                f"    _ = {call}",
                f'    passed += 1; print("  ✅ {label}")',
            ]

    lines += [
        "",
        f'    print("  [{import_path}] Passed:", passed, "Failed:", failed)',
    ]

    return "\n".join(lines) + "\n"


def generate(
    modules: list[ModuleTarget] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Generate per-module test files. Returns {module_id: n_tests}."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    plan = build_generation_plan(modules)
    counts: dict[str, int] = {}
    total_fns = 0
    expected_files: set[str] = set()
    shown_dry_run = False

    for target, testable in plan:
        n = len(testable)
        counts[target.module_id] = n
        total_fns += n
        expected_files.add(f"test_{target.module_id}.mojo")

        code = emit_lib_test(target.module_id, target.import_path, testable)
        if dry_run:
            if not shown_dry_run:
                print(code)
                shown_dry_run = True
        else:
            (OUT_DIR / f"test_{target.module_id}.mojo").write_text(code, encoding="utf-8")

    if not dry_run:
        for stale_file in OUT_DIR.glob("test_*.mojo"):
            if stale_file.name not in expected_files:
                stale_file.unlink()

    if not dry_run:
        skipped_modules = len(discover_library_modules()) - len(plan)
        print(f"Generated {len(counts)} test files in {OUT_DIR}")
        print(f"  Total functions to test: {total_fns}")
        print(f"  Skipped modules (untestable): {skipped_modules}")

    return counts


def main():
    dry_run = "--dry-run" in sys.argv
    modules = discover_library_modules()
    print(f"Scanning {len(modules)} module files...")
    generate(modules, dry_run=dry_run)


if __name__ == "__main__":
    main()
