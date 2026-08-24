#!/usr/bin/env python3
"""Static gap checks for the Algenta SDK surface: drift, silent visibility loss, surface
leaks, test coverage, and the enterprise capability checklist.

Companion to ``scripts/audit_library_execution_sweep.py`` (which proves execution); this
script proves the SURFACE: what is published, what silently vanished, what leaks into the
commercial contract that was never a library, what has no test, and which capabilities an
enterprise caller would reach for and not find.

Severity model:
- ``gate``    — blocks CI (drift, silent drops, leaks, untested published modules)
- ``finding`` — reported, does not block (capability gaps are feature work, not regressions)
- ``info``    — context for the report

Everything here is deterministic and network-free. Output: ``build/audit/gap_checks.json``
plus markdown; exit code 1 when any ``gate`` check fails.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SCHEMA_VERSION = "algenta-sdk-gap-checks/v1"
_DEFAULT_OUTPUT = _REPO_ROOT / "build" / "audit" / "gap_checks.json"
_BASELINE_PATH = _REPO_ROOT / "scripts" / "sdk_audit_baseline.json"
_CONTRACT_PATH = (
    _REPO_ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json"
)
_ENGINE_DIR = _REPO_ROOT / "mojo" / "engine"

# Non-library scratch names that must never appear in the commercial contract. The
# ``vector_kernels.test_table`` incident is why this check exists: a compile-verification
# scratch file shipped as a published library module. Prefix-based on any path segment;
# deliberately NOT matching bare `probe` — capability probes like `residentk.probe` are
# legitimate runtime modules with their own capability blocks and golden vectors.
_LEAK_NAME_PATTERN = re.compile(r"(^|\.)(test_|bench_|tmp_|scratch)")


@dataclass
class Check:
    check_id: str
    area: str
    status: str  # pass | fail | info
    severity: str  # gate | finding | info
    summary: str
    details: list[str] = field(default_factory=list)


@dataclass
class CheckReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> None:
        self.checks.append(check)


def _live_inventory():
    from apps.runtime.mojo_inventory import discover_runtime_library_modules

    return discover_runtime_library_modules(executable_only=True)


def _full_inventory():
    from apps.runtime.mojo_inventory import discover_runtime_library_modules

    return discover_runtime_library_modules(executable_only=False)


def _checked_in_contract() -> dict[str, Any]:
    return json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))


def check_contract_drift(report: CheckReport) -> None:
    contract = _checked_in_contract()
    contract_functions = {
        (module["name"], function["name"])
        for module in contract["modules"]
        for function in module["functions"]
    }
    contract_modules = {module["name"] for module in contract["modules"]}
    live_modules = {str(module.import_path) for module in _live_inventory()}
    live_functions = {
        (str(module.import_path), str(function.name))
        for module in _live_inventory()
        for function in module.functions
    }
    missing_functions = sorted(live_functions - contract_functions)
    extra_functions = sorted(contract_functions - live_functions)
    drift_lines = []
    if contract_modules != live_modules:
        drift_lines.append(
            f"modules: contract {len(contract_modules)} vs live {len(live_modules)} "
            f"(new: {len(live_modules - contract_modules)}, "
            f"gone: {len(contract_modules - live_modules)})"
        )
    if missing_functions:
        drift_lines.append(f"{len(missing_functions)} live functions absent from the contract")
        drift_lines.extend(f"  + {module}.{name}" for module, name in missing_functions[:15])
    if extra_functions:
        drift_lines.append(f"{len(extra_functions)} contract functions missing from the tree")
        drift_lines.extend(f"  - {module}.{name}" for module, name in extra_functions[:15])
    if drift_lines:
        report.add(
            Check(
                "contract_drift",
                "drift",
                "fail",
                "gate",
                "checked-in runtime_library_contract.json does not match the live inventory; "
                "run `make inventory-refresh` and commit the result",
                drift_lines,
            )
        )
    else:
        report.add(
            Check(
                "contract_drift",
                "drift",
                "pass",
                "gate",
                f"contract matches live inventory ({len(contract_modules)} modules / "
                f"{len(contract_functions)} functions)",
            )
        )
    declared_modules = len(contract["modules"])
    declared_functions = sum(len(module["functions"]) for module in contract["modules"])
    if (declared_modules, declared_functions) != (
        contract.get("module_count"),
        contract.get("function_count"),
    ):
        report.add(
            Check(
                "contract_internal_consistency",
                "drift",
                "fail",
                "gate",
                "contract module_count/function_count disagree with its own payload",
                [
                    f"declared {contract.get('module_count')}/{contract.get('function_count')} "
                    f"vs actual {declared_modules}/{declared_functions}"
                ],
            )
        )
    else:
        report.add(
            Check(
                "contract_internal_consistency",
                "drift",
                "pass",
                "gate",
                "contract self-counts are consistent",
            )
        )


def check_silent_visibility(report: CheckReport) -> None:
    """Functions the source tree exports but the contract never publishes vanish without an
    error (nine-line signatures, return structs owned by another file, non-marshalable
    fields). This check diffs executable vs all discovery so a vanish is a finding, not a
    mystery."""
    executable = {
        (str(module.import_path), str(function.name))
        for module in _live_inventory()
        for function in module.functions
    }
    all_modules = _full_inventory()
    all_functions = {
        (str(module.import_path), str(function.name))
        for module in all_modules
        for function in module.functions
    }
    vanished = sorted(all_functions - executable)
    # Wire-incompatible families make a drop structural, not a silent regression: SIMD types
    # cannot cross the JSON wire (distributions.sample_*_simd4), ExprNode/SimRequest/arena
    # types belong to the engine's internal request layer, and ArcPointer cannot be
    # marshalled (new-kernel-package-rules.md rule 2). Only UNEXPLAINED vanishes gate: the
    # nine-line-signature and cross-file-struct modes leave no trace anywhere else.
    structural_markers = (
        "SIMD[",
        "ExprNode",
        "SimRequest",
        "LinearForm",
        "ArcPointer",
        "Span[",
    )
    module_paths = {
        str(module.import_path): module.path for module in all_modules
    }
    signature_re_cache: dict[Path, str] = {}
    structural: list[str] = []
    unexplained: list[str] = []
    for module_name, function_name in vanished:
        path = module_paths.get(module_name)
        if path is not None:
            if path not in signature_re_cache:
                try:
                    signature_re_cache[path] = path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    signature_re_cache[path] = ""
            source = signature_re_cache[path]
            pattern = re.compile(
                r"^\s*(?:fn|def)\s+" + re.escape(function_name) + r"\b[^\n]*"
                r"(?:\n(?!\s*(?:fn|def)\s)[^\n]*){0,3}",
                re.MULTILINE,
            )
            match = pattern.search(source)
            signature_text = match.group(0) if match else ""
            blocked = any(marker in signature_text for marker in structural_markers)
            if not blocked and signature_text:
                # A parameter struct whose own fields carry wire-incompatible types blocks
                # the function the same way (OptModel holds List[ExprNode], so every
                # OptModel-taking driver vanishes). Resolve one level of same-file structs.
                for struct_name in re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", signature_text):
                    struct_match = re.search(
                        r"struct\s+" + re.escape(struct_name) + r"\b[^\n]*\n"
                        r"((?:[ \t][^\n]*\n|\n){0,40})",
                        source,
                    )
                    if struct_match and any(
                        marker in struct_match.group(1) for marker in structural_markers
                    ):
                        blocked = True
                        break
            if blocked:
                structural.append(f"{module_name}.{function_name}")
                continue
        unexplained.append(f"{module_name}.{function_name}")
    details = list(unexplained[:50])
    if structural:
        details.append(
            f"[structural, wire-incompatible types — expected internals] {len(structural)}: "
            + ", ".join(item for item in structural[:8])
        )
    if len(unexplained) > 50:
        details.append(f"… {len(unexplained) - 50} more")
    if unexplained:
        report.add(
            Check(
                "silent_visibility",
                "visibility",
                "fail",
                "gate",
                f"{len(unexplained)} public source function(s) vanish from the executable "
                "contract without a structural reason (cross-file return structs, "
                "unsupported types, or >9-line signatures — see "
                "new-kernel-package-rules.md rule 2)",
                details,
            )
        )
    else:
        report.add(
            Check(
                "silent_visibility",
                "visibility",
                "pass",
                "gate",
                "every discovered public function is executable or vanishes for a known "
                f"structural reason ({len(structural)} wire-incompatible internals)",
                details,
            )
        )


def _engine_kernel_floor() -> dict[str, Any]:
    floor_path = _REPO_ROOT / "scripts" / "engine_kernel_floor.json"
    try:
        payload = json.loads(floor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": 1, "kernel_count": 0, "kernels": []}
    kernels = payload.get("kernels") if isinstance(payload, dict) else None
    if not isinstance(kernels, list):
        return {"schema": 1, "kernel_count": 0, "kernels": []}
    return {"schema": 1, "kernel_count": len(kernels), "kernels": kernels}


def _live_engine_kernels_payload() -> dict[str, Any]:
    from apps.runtime.mojo_inventory import discover_engine_kernels, engine_kernels_payload

    return engine_kernels_payload(discover_engine_kernels())


def _kernel_key(module: Any, name: Any) -> str:
    return f"{module}.{name}"


def check_engine_kernel_drift(report: CheckReport) -> None:
    """The contract's `engine_kernels` section must be the live source-driven discovery.

    The racing kernels are private symbols, so NOTHING else republishes them: if this
    section drifts from the tree, the public surface lies (an unrefreshed contract after a
    kernel landed, or a hand edit that quietly dropped one).
    """
    contract = _checked_in_contract()
    section = contract.get("engine_kernels")
    try:
        live = _live_engine_kernels_payload()
    except Exception as exc:  # noqa: BLE001 — discovery must fail the gate loudly, not crash it
        report.add(
            Check(
                "engine_kernel_drift",
                "drift",
                "fail",
                "gate",
                f"engine kernel discovery failed: {exc}",
            )
        )
        return
    if not isinstance(section, dict):
        report.add(
            Check(
                "engine_kernel_drift",
                "drift",
                "fail",
                "gate",
                "runtime_library_contract.json has no engine_kernels section; run "
                "`make inventory-refresh` and commit the result",
            )
        )
        return
    if section == live:
        report.add(
            Check(
                "engine_kernel_drift",
                "drift",
                "pass",
                "gate",
                f"engine_kernels matches live discovery ({live['module_count']} modules / "
                f"{live['kernel_count']} kernels)",
            )
        )
        return
    drift_lines: list[str] = []
    contract_keys = {
        _kernel_key(kernel.get("module"), kernel.get("name"))
        for kernel in section.get("kernels", [])
        if isinstance(kernel, dict)
    }
    live_keys = {_kernel_key(kernel["module"], kernel["name"]) for kernel in live["kernels"]}
    gone = sorted(contract_keys - live_keys)
    new = sorted(live_keys - contract_keys)
    if gone:
        drift_lines.append(f"{len(gone)} contract kernel(s) absent from the tree")
        drift_lines.extend(f"  - {key}" for key in gone[:15])
    if new:
        drift_lines.append(f"{len(new)} live kernel(s) absent from the contract")
        drift_lines.extend(f"  + {key}" for key in new[:15])
    common = contract_keys & live_keys
    if common:
        contract_by_key = {
            _kernel_key(kernel.get("module"), kernel.get("name")): kernel
            for kernel in section.get("kernels", [])
            if isinstance(kernel, dict)
        }
        live_by_key = {
            _kernel_key(kernel["module"], kernel["name"]): kernel
            for kernel in live["kernels"]
        }
        changed = sorted(
            key
            for key in common
            if {
                field: value
                for field, value in contract_by_key[key].items()
                if field in ("backend", "families", "role", "symbol", "prefix")
            }
            != {
                field: value
                for field, value in live_by_key[key].items()
                if field in ("backend", "families", "role", "symbol", "prefix")
            }
        )
        if changed:
            drift_lines.append(f"{len(changed)} kernel(s) with changed fields")
            drift_lines.extend(f"  ~ {key}" for key in changed[:15])
    if section.get("kernel_count") != len(section.get("kernels", [])):
        drift_lines.append("engine_kernels.kernel_count disagrees with its own kernels list")
    if section.get("module_count") != len(section.get("modules", [])):
        drift_lines.append("engine_kernels.module_count disagrees with its own modules list")
    report.add(
        Check(
            "engine_kernel_drift",
            "drift",
            "fail",
            "gate",
            "engine_kernels section does not match live discovery; run "
            "`make inventory-refresh` and commit the result",
            drift_lines,
        )
    )


def check_engine_kernel_visibility(report: CheckReport) -> None:
    """The silent-visibility-loss gate for the published kernel surface.

    Every entry in ``scripts/engine_kernel_floor.json`` must still exist in live discovery
    with the SAME backend and at least its families. A kernel disappearing from the public
    inventory — or quietly losing a backend/family — fails CI. Removing one is a loud,
    deliberate act: a manual edit of the floor file, never a side effect of a regen.
    """
    floor = _engine_kernel_floor()
    floor_kernels = [entry for entry in floor["kernels"] if isinstance(entry, dict)]
    try:
        live = _live_engine_kernels_payload()
    except Exception as exc:  # noqa: BLE001
        report.add(
            Check(
                "engine_kernel_visibility",
                "visibility",
                "fail",
                "gate",
                f"engine kernel discovery failed: {exc}",
            )
        )
        return
    live_by_key = {
        _kernel_key(kernel["module"], kernel["name"]): kernel for kernel in live["kernels"]
    }
    lost: list[str] = []
    for entry in sorted(floor_kernels, key=lambda item: _kernel_key(item.get("module"), item.get("name"))):
        key = _kernel_key(entry.get("module"), entry.get("name"))
        kernel = live_by_key.get(key)
        if kernel is None:
            lost.append(f"{key} — published in the floor, absent from live discovery")
            continue
        if entry.get("backend") and entry.get("backend") != kernel.get("backend"):
            lost.append(
                f"{key} — lost backend {entry.get('backend')!r} (now {kernel.get('backend')!r})"
            )
        floor_families = set(entry.get("families") or [])
        live_families = set(kernel.get("families") or [])
        dropped = sorted(floor_families - live_families)
        if dropped:
            lost.append(f"{key} — lost families: {', '.join(dropped)}")
    if lost:
        report.add(
            Check(
                "engine_kernel_visibility",
                "visibility",
                "fail",
                "gate",
                f"{len(lost)} published engine kernel(s) vanished or shrank; removing a "
                "kernel must be a loud, deliberate edit of scripts/engine_kernel_floor.json, "
                "never a silent side effect",
                lost[:30],
            )
        )
    else:
        report.add(
            Check(
                "engine_kernel_visibility",
                "visibility",
                "pass",
                "gate",
                f"all {len(floor_kernels)} published engine kernel(s) still ship with their "
                "backends and families intact",
            )
        )


def check_engine_kernel_floor_stale(report: CheckReport) -> None:
    """The floor must cover everything live discovery publishes (grow side of the ratchet).

    A new kernel lands in the source, flows into the contract via `make inventory-refresh`,
    and is NOT yet in the floor -> this gate fails until the floor is grown with
    `python3 scripts/generate_engine_kernel_floor.py`. That is the deliberate step which
    puts the new kernel under the visibility ratchet above.
    """
    floor = _engine_kernel_floor()
    floor_keys = {
        _kernel_key(entry.get("module"), entry.get("name"))
        for entry in floor["kernels"]
        if isinstance(entry, dict)
    }
    try:
        live = _live_engine_kernels_payload()
    except Exception as exc:  # noqa: BLE001
        report.add(
            Check(
                "engine_kernel_floor_stale",
                "visibility",
                "fail",
                "gate",
                f"engine kernel discovery failed: {exc}",
            )
        )
        return
    live_keys = {_kernel_key(kernel["module"], kernel["name"]) for kernel in live["kernels"]}
    missing = sorted(live_keys - floor_keys)
    if missing:
        report.add(
            Check(
                "engine_kernel_floor_stale",
                "visibility",
                "fail",
                "gate",
                f"{len(missing)} live engine kernel(s) are not under the visibility floor; "
                "run `python3 scripts/generate_engine_kernel_floor.py` and commit the grown "
                "floor",
                missing[:30],
            )
        )
    else:
        report.add(
            Check(
                "engine_kernel_floor_stale",
                "visibility",
                "pass",
                "gate",
                f"floor covers all {len(live_keys)} live engine kernel(s)",
            )
        )


def check_surface_leaks(report: CheckReport) -> None:
    leaks: list[str] = []
    for module in _live_inventory():
        import_path = str(module.import_path)
        if _LEAK_NAME_PATTERN.search(import_path):
            leaks.append(import_path)
    if leaks:
        report.add(
            Check(
                "surface_leaks",
                "visibility",
                "fail",
                "gate",
                f"{len(leaks)} scratch/test module(s) published in the commercial contract",
                leaks,
            )
        )
    else:
        report.add(
            Check(
                "surface_leaks",
                "visibility",
                "pass",
                "gate",
                "no scratch/test modules in the commercial contract",
            )
        )


def check_test_coverage(report: CheckReport) -> None:
    libs_dir = _REPO_ROOT / "mojo" / "tests" / "libs"
    dedicated = {
        path.stem.replace("test_", "", 1) for path in libs_dir.glob("test_*.mojo")
    }
    wave_imported: set[str] = set()
    import_re = re.compile(r"^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+", re.MULTILINE)
    for wave_path in (_REPO_ROOT / "tests" / "mojo").glob("test_wave*.mojo"):
        text = wave_path.read_text(encoding="utf-8", errors="replace")
        wave_imported.update(import_re.findall(text))
    untested: list[str] = []
    for module in _live_inventory():
        name = str(module.import_path)
        alias = name.replace(".", "_")
        if name in dedicated or alias in dedicated:
            continue
        if name in wave_imported or name.split(".")[0] in wave_imported:
            continue
        untested.append(name)
    if untested:
        report.add(
            Check(
                "test_coverage",
                "coverage",
                "fail",
                "gate",
                f"{len(untested)} contract module(s) have neither a dedicated libs suite nor "
                "wave-test imports",
                untested,
            )
        )
    else:
        report.add(
            Check(
                "test_coverage",
                "coverage",
                "pass",
                "gate",
                "every contract module has a dedicated suite or a wave-test import",
            )
        )
    legacy = _REPO_ROOT / "mojo" / "tests" / "test_all_libraries.mojo"
    if legacy.exists():
        header = legacy.read_text(encoding="utf-8", errors="replace")[:400]
        match = re.search(r"Tests (\d+) functions across (\d+) Mojo libraries", header)
        if match:
            live_count = sum(len(module.functions) for module in _live_inventory())
            legacy_functions = int(match.group(1))
            if legacy_functions < live_count:
                report.add(
                    Check(
                        "legacy_all_libraries_stale",
                        "coverage",
                        "info",
                        "info",
                        f"mojo/tests/test_all_libraries.mojo covers {legacy_functions} "
                        f"functions vs {live_count} live; per-module libs suites supersede it — "
                        "confirm nothing consumes it before removal",
                    )
                )


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_capability_checklist(report: CheckReport) -> None:
    query_dir = _ENGINE_DIR / "query"
    join_src = _read(query_dir / "join.mojo")
    plan_src = _read(query_dir / "plan.mojo")
    ir_src = _read(query_dir / "ir.mojo")
    window_src = _read(query_dir / "window.mojo")
    sdk_query_src = _read(
        _REPO_ROOT / "packages" / "algenta" / "algenta" / "query.py"
    )

    def capability(
        check_id: str,
        description: str,
        present: bool,
        evidence: str,
    ) -> None:
        report.add(
            Check(
                check_id,
                "capability",
                "pass" if present else "fail",
                "pass" if present else "finding",
                description + (" — present" if present else " — MISSING"),
                [evidence],
            )
        )

    capability(
        "query_set_ops_union",
        "query plane: UNION/UNION ALL between result sets",
        "union" in plan_src.lower() or "union_all" in sdk_query_src,
        "mojo/engine/query/plan.mojo + packages/algenta/algenta/query.py",
    )
    capability(
        "query_set_ops_intersect_except",
        "query plane: INTERSECT/EXCEPT set operations",
        "intersect" in plan_src.lower() or "except_op" in plan_src.lower(),
        "mojo/engine/query/plan.mojo",
    )
    capability(
        "query_join_right_full_cross",
        "query plane: RIGHT/FULL/CROSS joins (INNER+LEFT exist)",
        any(name in join_src for name in ("JOIN_RIGHT", "JOIN_FULL", "JOIN_CROSS")),
        "mojo/engine/query/join.mojo (constants JOIN_*)",
    )
    capability(
        "query_having",
        "query plane: HAVING-style post-aggregate filter",
        "having" in plan_src.lower() or "having" in sdk_query_src.lower(),
        "mojo/engine/query/plan.mojo",
    )
    expression_math = all(
        token in ir_src for token in ("OP_ABS", "OP_ROUND", "OP_SQRT")
    )
    capability(
        "query_expr_math",
        "query expressions: abs/round/sqrt-class math functions",
        expression_math,
        "mojo/engine/query/ir.mojo (OP_* vocabulary)",
    )
    capability(
        "query_expr_string",
        "query expressions: string functions (like/upper/substring-class)",
        any(token in ir_src for token in ("OP_LIKE", "OP_UPPER", "OP_LOWER", "OP_SUBSTR")),
        "mojo/engine/query/ir.mojo (OP_* vocabulary)",
    )
    capability(
        "query_expr_case_in_between",
        "query expressions: CASE / IN / BETWEEN forms",
        any(token in ir_src for token in ("OP_CASE", "OP_IN", "OP_BETWEEN")),
        "mojo/engine/query/ir.mojo",
    )
    window_extras = [
        name for name in ("ntile", "percent_rank", "cume_dist", "first_value", "last_value")
        if name in window_src or f"def {name}" in sdk_query_src
    ]
    capability(
        "query_window_variants",
        "query window: ntile/percent_rank/cume_dist/first_value/last_value "
        f"(found: {', '.join(window_extras) or 'none'})",
        bool(window_extras),
        "mojo/engine/query/window.mojo",
    )

    live_module_names = {str(module.import_path) for module in _live_inventory()}
    families = {
        "family_datetime": ("datetime handling", {"datetime"}),
        "family_string_text": ("string/text processing", {"string", "text"}),
        "family_checksum_hash": ("hashing/checksums", {"checksum", "hashing", "sha256"}),
        "family_json_config": ("JSON/config parsing", {"json", "config.toml_parser", "config.yaml_parser"}),
        "family_geospatial": ("geospatial", {"geospatial", "cartography", "map_matching"}),
        "family_retrieval": ("text retrieval/embeddings", {"retrieval", "embeddings"}),
        "family_ml": ("ML kernels", {"ml", "mlpk"}),
        "family_graph": ("graph algorithms", {"graph", "graph.algorithms", "network_analysis"}),
        "family_streaming": ("streaming sketches", {"streaming", "sketch"}),
        "family_optimization": ("optimization/solvers", {"optimization", "convex", "linear_programming"}),
    }
    for check_id, (description, candidates) in families.items():
        hits = sorted(
            name for name in live_module_names
            if any(name == candidate or name.startswith(candidate + ".") for candidate in candidates)
        )
        report.add(
            Check(
                check_id,
                "capability",
                "pass" if hits else "fail",
                "pass" if hits else "finding",
                f"horizontal family: {description}"
                + (f" — {len(hits)} module(s)" if hits else " — MISSING"),
                hits[:12],
            )
        )


def check_sdk_parity(report: CheckReport) -> None:
    ts_libraries_src = _read(_REPO_ROOT / "packages" / "ts-sdk" / "src" / "libraries.ts")
    ts_runtime_client_src = _read(
        _REPO_ROOT / "packages" / "ts-sdk" / "src" / "runtime_daemon_client.ts"
    )
    ts_blob = ts_libraries_src + ts_runtime_client_src
    parity = {
        "execute": "execute" in ts_blob,
        "execute_batch": "batch_execute" in ts_blob or "executeBatch" in ts_blob,
        "pipeline": "pipeline_execute" in ts_blob or "runPipeline" in ts_blob,
        "query_plan": "query_execute" in ts_blob,
        "datasets": "dataset_open" in ts_blob or "openDataset" in ts_blob,
        "stream": "stream" in ts_libraries_src,
        "capabilities": "capabilit" in ts_libraries_src,
    }
    missing = sorted(name for name, present in parity.items() if not present)
    report.add(
        Check(
            "sdk_surface_parity",
            "parity",
            "pass" if not missing else "fail",
            "pass" if not missing else "finding",
            "TS SDK local-runtime parity vs Python MojoRuntime "
            + (
                "— full parity"
                if not missing
                else f"— missing: {', '.join(missing)}"
            ),
            [
                "Python surface: execute/execute_batch/pipeline/query/datasets/stream/"
                "capabilities (packages/algenta/algenta/mojo_runtime.py)"
            ],
        )
    )
    ts_daemon_required = "ALGENTA_DAEMON_TCP" in ts_runtime_client_src
    report.add(
        Check(
            "ts_local_runtime_path",
            "parity",
            "info",
            "info",
            "TS local path requires a separately started runtime daemon "
            "(no bundled native dependency in the npm package)"
            if ts_daemon_required
            else "TS local path layout changed — re-verify encapsulation story",
            ["packages/ts-sdk/src/runtime_daemon_client.ts"],
        )
    )


def check_release_gate_style(report: CheckReport) -> None:
    workflow_src = _read(_REPO_ROOT / ".github" / "workflows" / "build-runtime.yml")
    if re.search(r"expected \d+ runtime modules", workflow_src):
        report.add(
            Check(
                "release_gate_hardcoded_counts",
                "drift",
                "fail",
                "gate",
                "build-runtime.yml still hardcodes module/function counts; origin/main "
                "compares live surface vs packaged contract dynamically — port that change",
                [".github/workflows/build-runtime.yml"],
            )
        )
    elif "runtime_modules()" in workflow_src:
        report.add(
            Check(
                "release_gate_hardcoded_counts",
                "drift",
                "pass",
                "gate",
                "release gate compares live surface against the packaged contract dynamically",
            )
        )


def render_markdown(report: CheckReport, meta: dict[str, Any]) -> str:
    lines = [
        "# SDK gap checks",
        "",
        f"- Generated: {meta['generated_at']}",
        "",
    ]
    by_area: dict[str, list[Check]] = {}
    for check in report.checks:
        by_area.setdefault(check.area, []).append(check)
    for area in sorted(by_area):
        lines.append(f"## {area}")
        lines.append("")
        for check in by_area[area]:
            marker = {"pass": "✅", "fail": "❌", "info": "ℹ️", "waived": "🟡"}[check.status]
            gate_note = " *(gate)*" if check.severity == "gate" and check.status == "fail" else ""
            waived_note = " *(waived — see scripts/sdk_audit_baseline.json)*" if check.status == "waived" else ""
            lines.append(f"- {marker} `{check.check_id}`: {check.summary}{gate_note}{waived_note}")
            for detail in check.details[:12]:
                lines.append(f"  - {detail}")
        lines.append("")
    return "\n".join(lines)


def run_all_checks() -> CheckReport:
    report = CheckReport()
    check_contract_drift(report)
    check_engine_kernel_drift(report)
    check_silent_visibility(report)
    check_engine_kernel_visibility(report)
    check_engine_kernel_floor_stale(report)
    check_surface_leaks(report)
    check_test_coverage(report)
    check_capability_checklist(report)
    check_sdk_parity(report)
    check_release_gate_style(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = run_all_checks()

    # Waivers live in scripts/sdk_audit_baseline.json with the same semantics as
    # capability_manifest_baseline.json: they excuse KNOWN in-flight failures and only ever
    # shrink (tests/test_sdk_audit_ratchet.py fails on a waiver whose check now passes).
    waived_ids: set[str] = set()
    try:
        baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        waived_ids = {str(item) for item in baseline.get("waived_gate_failures", [])}
    except (OSError, json.JSONDecodeError):
        pass
    gate_failures: list[Check] = []
    waived_failures: list[Check] = []
    for check in report.checks:
        if check.severity != "gate" or check.status != "fail":
            continue
        if check.check_id in waived_ids:
            check.status = "waived"
            waived_failures.append(check)
        else:
            gate_failures.append(check)
    findings = [
        check for check in report.checks
        if check.severity == "finding" and check.status == "fail"
    ]
    meta = {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "gate_failures": len(gate_failures),
        "waived_gate_failures": len(waived_failures),
        "findings": len(findings),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **meta,
        "checks": [vars(check) for check in report.checks],
    }
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(report, meta), encoding="utf-8")

    print(
        f"gap checks: {len(report.checks)} checks, {len(gate_failures)} gate failures, "
        f"{len(waived_failures)} waived, {len(findings)} findings",
        flush=True,
    )
    print(f"results: {args.output}\nsummary: {markdown_path}", flush=True)
    return 1 if gate_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
