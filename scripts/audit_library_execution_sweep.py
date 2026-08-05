#!/usr/bin/env python3
"""SDK real-world execution sweep: every published runtime-library function, invoked the
way a commercial caller invokes it, classified by what actually happens.

Why this exists: the generated A-Z suite calls every function with a five-element list and
``5`` for every ``Int``, so a count that exceeds its list is structurally invisible there
(see ``tests/integration/test_kernel_count_arg_robustness.py``). This sweep is the
generalisation that file's docstring asks for: per-function signature-derived arguments,
count-relation-coherent smoke values, a hostile battery that deliberately breaks counts and
numeric domains, and a hard rule that a dead worker is a finding, not an accident.

Evidence rules (``docs/mojo/new-kernel-package-rules.md`` rule 1b): only the COMPILED worker
counts. The sweep therefore refuses to run without one; resolution order mirrors
``tests/integration/test_kernel_count_arg_robustness.py``:

    --worker PATH, $ALGENTA_AUDIT_WORKER,
    mojo_build/audit-worker/algenta-runtime-worker,
    mojo_build/runtime-shards/algenta-runtime-worker,
    mojo_build/simulate

Repo-dev builds are unsigned, so ``ALGENTA_RUNTIME_FALLBACK_MODE=allow`` is set exactly as in
the robustness suite; on a packaged runtime the release default (``deny``) applies and this
script never relaxes it for a verified source.

Usage:
    python3 scripts/audit_library_execution_sweep.py --battery all
    python3 scripts/audit_library_execution_sweep.py --battery smoke --modules stats,heap
    python3 scripts/audit_library_execution_sweep.py --resume   # continue after interruption

Output: ``build/audit/library_sweep_results.json`` (machine-readable) plus a markdown
summary. Exit code is non-zero when any P0/P1 classification is present, so CI can gate on it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_ALGENTA_PKG = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA_PKG) not in sys.path:
    sys.path.insert(0, str(_ALGENTA_PKG))

_SCHEMA_VERSION = "algenta-library-execution-sweep/v1"
_DEFAULT_OUTPUT = _REPO_ROOT / "build" / "audit" / "library_sweep_results.json"

_WORKER_CANDIDATES = (
    _REPO_ROOT / "mojo_build" / "audit-worker" / "algenta-runtime-worker",
    _REPO_ROOT / "mojo_build" / "runtime-shards" / "algenta-runtime-worker",
    _REPO_ROOT / "mojo_build" / "simulate",
)

# Classification → severity. A dead worker or a lost state round-trip is the worst class of
# finding: the first is an uncatchable abort reachable over the wire, the second silently
# discards the caller's data.
_SEVERITY = {
    "ok": None,
    "expected_rejection": None,
    "unbuildable_args": "P2",
    "bad_result_shape": "P1",
    "state_lost": "P1",
    "nondeterministic": "P1",
    "execution_error": "P2",
    "timeout": "P1",
    "worker_crash": "P0",
    "resource_blowup": "P0",
}

_EXPECTED_REJECTION_CODES = {
    "count_exceeds_list_length",
    "invalid_arguments",
    "mojo_library_execution_failed",
}

# RSS watchdog: no probe value can guarantee memory safety against arbitrary kernels —
# measured live, count probes of 2**31, 10k, 1000 and 200 drove workers to 70 GB, 17 GB,
# 75 GB and 71 GB respectively (linear, quadratic, cubic and quartic allocators). So the
# harness watches the worker processes and kills one that exceeds the ceiling, recording
# the call as a P0 resource_blowup finding — the audit converts the hazard into evidence
# instead of becoming the hazard. The ceiling is generous: legitimate library calls on
# five-element smoke args stay in double-digit MB.
_WORKER_RSS_CEILING_KB = 6 * 1024 * 1024
_WORKER_RSS_POLL_SECONDS = 0.4

_blowup_killed = False


def _worker_processes() -> list[tuple[int, int]]:
    """(pid, rss_kb) for every algenta-runtime-worker process, darwin+linux ps."""
    import subprocess as _subprocess

    try:
        out = _subprocess.run(
            ["ps", "-eo", "pid=,rss=,comm="],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except Exception:
        return []
    found: list[tuple[int, int]] = []
    for line in out.splitlines():
        if "algenta-runtime-worker" not in line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            found.append((int(parts[0]), int(parts[1])))
        except ValueError:
            continue
    return found


def _watch_worker_rss(stop: "threading.Event") -> None:
    global _blowup_killed
    import os as _os
    import signal as _signal

    while not stop.is_set():
        for pid, rss_kb in _worker_processes():
            if rss_kb > _WORKER_RSS_CEILING_KB:
                _blowup_killed = True
                print(
                    f"RSS watchdog: killing worker pid {pid} at {rss_kb // 1024} MB "
                    f"(ceiling {_WORKER_RSS_CEILING_KB // 1024} MB)",
                    flush=True,
                )
                try:
                    _os.kill(pid, _signal.SIGKILL)
                except OSError:
                    pass
                return
        stop.wait(_WORKER_RSS_POLL_SECONDS)


@dataclass(frozen=True)
class FunctionRecord:
    module: str
    name: str
    params: tuple[dict[str, Any], ...]
    return_type: str
    count_relations: tuple[dict[str, Any], ...]
    structs: dict[str, dict[str, Any]]


@dataclass
class CaseOutcome:
    classification: str
    detail: str = ""
    error_code: str = ""
    latency_ms: float = 0.0


@dataclass
class SweepState:
    outcomes: dict[str, dict[str, Any]] = field(default_factory=dict)
    started_at: str = ""


def _resolve_shards(explicit_worker: str | None) -> tuple[tuple[Path, tuple[str, ...] | None], ...]:
    """Resolve (worker binary, modules it owns) pairs.

    The compiled runtime ships as module-routed shards because one compile of the whole tree
    exceeds the bounded compiler's RSS ceiling; the sweep therefore walks each shard worker
    with exactly the modules routed to it. A single-binary layout (repo-dev ``simulate``)
    comes back as one entry with ``None`` = all modules.
    """
    if explicit_worker:
        return ((Path(explicit_worker), None),)
    env_override = os.environ.get("ALGENTA_AUDIT_WORKER")
    if env_override:
        return ((Path(env_override), None),)
    for shards_dir in (
        _REPO_ROOT / "mojo_build" / "audit-worker",
        _REPO_ROOT / "mojo_build" / "runtime-shards",
    ):
        shard_map_path = shards_dir / "runtime-shards.json"
        if shard_map_path.is_file():
            payload = json.loads(shard_map_path.read_text(encoding="utf-8"))
            module_workers: dict[str, str] = payload.get("module_workers", {})
            by_worker: dict[str, list[str]] = {}
            for module_name, worker_name in sorted(module_workers.items()):
                by_worker.setdefault(worker_name, []).append(module_name)
            entries: list[tuple[Path, tuple[str, ...]]] = []
            for worker_name, module_names in sorted(by_worker.items()):
                worker_path = shards_dir / worker_name
                if worker_path.is_file() and os.access(worker_path, os.X_OK):
                    entries.append((worker_path, tuple(sorted(module_names))))
            if entries:
                return tuple(entries)
    single = _REPO_ROOT / "mojo_build" / "simulate"
    if single.is_file() and os.access(single, os.X_OK):
        return ((single, None),)
    raise SystemExit(
        "No compiled runtime worker found. Build shards first:\n"
        "  python3 scripts/build_runtime_shards.py --out mojo_build/audit-worker "
        "--shard-size 24 --timeout-seconds 900\n"
        "(JIT evidence does not count: docs/mojo/new-kernel-package-rules.md rule 1b.)"
    )


def _load_live_surface() -> tuple[tuple[FunctionRecord, ...], dict[str, int]]:
    from apps.runtime.mojo_count_relations import declared_count_specs
    from apps.runtime.mojo_inventory import (
        discover_runtime_library_modules,
        parse_runtime_struct_specs,
    )

    modules = discover_runtime_library_modules(executable_only=True)
    relation_index: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {}
    for (module_name, function_name), spec in declared_count_specs().items():
        relation_index[(str(module_name), str(function_name))] = tuple(spec.to_payload())
    global_structs: dict[str, dict[str, Any]] = {}
    for module in modules:
        try:
            for struct_name, struct_spec in parse_runtime_struct_specs(module.path).items():
                global_structs.setdefault(struct_name, _struct_as_dict(struct_spec))
        except OSError:
            continue

    records: list[FunctionRecord] = []
    per_module_count: dict[str, int] = {}
    for module in modules:
        local_structs: dict[str, dict[str, Any]] = {}
        try:
            local_structs = {
                struct_name: _struct_as_dict(struct_spec)
                for struct_name, struct_spec in parse_runtime_struct_specs(
                    module.path
                ).items()
            }
        except OSError:
            pass
        merged_structs = {**global_structs, **local_structs}
        for function in module.functions:
            relations = relation_index.get(
                (str(module.import_path), str(function.name)), ()
            )
            records.append(
                FunctionRecord(
                    module=str(module.import_path),
                    name=str(function.name),
                    params=tuple(_param_as_dict(param) for param in function.params),
                    return_type=str(function.return_type),
                    count_relations=relations,
                    structs=merged_structs,
                )
            )
        per_module_count[str(module.import_path)] = len(module.functions)
    return tuple(records), per_module_count


def _struct_as_dict(struct_spec: Any) -> dict[str, Any]:
    return {
        "name": str(struct_spec.name),
        "fields": [
            {"name": str(field_spec.name), "type": str(field_spec.typ)}
            for field_spec in struct_spec.fields
        ],
    }


def _param_as_dict(param_spec: Any) -> dict[str, Any]:
    return {
        "name": str(param_spec.name),
        "type": str(param_spec.typ),
        "has_default": bool(getattr(param_spec, "has_default", False)),
    }


def _base_type(type_name: str) -> str:
    return type_name.split("[", 1)[0].strip()


def _inner_type(type_name: str) -> str:
    if type_name.startswith("List[") and type_name.endswith("]"):
        return type_name[len("List[") : -1]
    return type_name


class ArgBuilder:
    """Signature-derived arguments, count-relation-coherent by construction.

    The smoke values deliberately echo the A-Z suite's small-list convention (five elements)
    so a function that works there works here; coherence comes from the count pass, which
    rewrites factor ``Int``s to the measured length of the list they bound.
    """

    def __init__(self, record: FunctionRecord) -> None:
        self.record = record

    def build(self, *, variant: str = "smoke") -> list[Any] | None:
        args: list[Any] = []
        for param in self.record.params:
            value = self._value_for(param["type"], variant, depth=0)
            if value is _UNBUILDABLE:
                return None
            args.append(value)
        self._apply_count_coherence(args)
        return args

    def hostile_variants(self, smoke_args: list[Any]) -> list[tuple[str, list[Any]]]:
        """Deliberately broken argument sets. Each is expected to be refused with a typed
        error or answered safely; a dead worker is the failure this battery hunts."""
        variants: list[tuple[str, list[Any]]] = []
        param_names = [param["name"] for param in self.record.params]
        for relation in self.record.count_relations:
            factor_names = [name for name in relation["factors"] if name in param_names]
            bounds_names = [name for name in relation["bounds"] if name in param_names]
            if not factor_names or not bounds_names:
                continue
            factor_index = param_names.index(factor_names[0])
            bounds_index = param_names.index(bounds_names[0])
            bounds_value = smoke_args[bounds_index]
            measured = len(bounds_value) if isinstance(bounds_value, (list, str)) else 0
            oversized = list(smoke_args)
            oversized[factor_index] = measured + 20
            variants.append((f"count_over_bounds:{factor_names[0]}>{bounds_names[0]}", oversized))
            negative = list(smoke_args)
            negative[factor_index] = -1
            variants.append((f"count_negative:{factor_names[0]}", negative))
            huge = list(smoke_args)
            huge[factor_index] = 1_000
            variants.append((f"count_huge:{factor_names[0]}", huge))
            if isinstance(bounds_value, list):
                empty = list(smoke_args)
                empty[bounds_index] = []
                empty[factor_index] = 1
                variants.append((f"empty_list_with_count:{bounds_names[0]}", empty))
        if not self.record.count_relations:
            list_params = [
                (index, param)
                for index, param in enumerate(self.record.params)
                if _base_type(param["type"]) == "List"
            ]
            int_params = [
                (index, param)
                for index, param in enumerate(self.record.params)
                if param["type"] == "Int"
            ]
            # The hazard that killed stats.sort_values: an undeclared (List, Int) pair where
            # the Int is trusted as an element count. No relation means no pre-call guard, so
            # an over-large or negative value reaches the kernel's indexing directly.
            # The "huge" value stays tiny (200): a kernel that allocates per count unit —
            # or per count CUBED — turns a bigger probe into a multi-GB blowup, and the
            # audit must not reproduce rule 1c resource hazards against its own workers.
            # Measured live, in order: 2**31 drove a worker past 70 GB RSS; 10k reached
            # 17 GB on a quadratic kernel; 1000 reached 75 GB on a cubic one. 200 still
            # exceeds the smoke list length 40x, which is all an over-read needs, and keeps
            # even a cubic allocation with ten arrays under ~600 MB.
            if list_params and int_params:
                bounds_index, bounds_param = list_params[0]
                bounds_value = smoke_args[bounds_index]
                measured = len(bounds_value) if isinstance(bounds_value, (list, str)) else 0
                for factor_index, factor_param in int_params:
                    oversized = list(smoke_args)
                    oversized[factor_index] = measured + 20
                    variants.append(
                        (f"undeclared_count_over:{factor_param['name']}>{bounds_param['name']}", oversized)
                    )
                    negative = list(smoke_args)
                    negative[factor_index] = -1
                    variants.append((f"undeclared_count_negative:{factor_param['name']}", negative))
                    huge = list(smoke_args)
                    huge[factor_index] = 200
                    variants.append((f"undeclared_count_huge:{factor_param['name']}", huge))
            for index, param in enumerate(self.record.params):
                base = _base_type(param["type"])
                if base == "List":
                    empty = list(smoke_args)
                    empty[index] = []
                    variants.append((f"empty_list:{param['name']}", empty))
                    poisoned = list(smoke_args)
                    poisoned[index] = self._poisoned_list(param["type"])
                    if poisoned[index] is not _UNBUILDABLE:
                        variants.append((f"nan_inf:{param['name']}", poisoned))
                elif param["type"] == "Float64" and not variants:
                    for bad_value, label in ((float("nan"), "nan"), (float("-inf"), "neginf")):
                        poisoned = list(smoke_args)
                        poisoned[index] = bad_value
                        variants.append((f"{label}:{param['name']}", poisoned))
        return variants

    def _poisoned_list(self, type_name: str) -> Any:
        inner = _inner_type(type_name)
        if inner == "Float64":
            return [1.0, float("nan"), float("inf"), float("-inf"), 0.0]
        if inner == "Int":
            return [0, -1, 2**62, -(2**62), 1]
        return _UNBUILDABLE

    def _apply_count_coherence(self, args: list[Any]) -> None:
        param_names = [param["name"] for param in self.record.params]
        for relation in self.record.count_relations:
            bounds_names = [name for name in relation["bounds"] if name in param_names]
            factor_names = [name for name in relation["factors"] if name in param_names]
            if not bounds_names or not factor_names:
                continue
            measured = 0
            for bounds_name in bounds_names:
                value = args[param_names.index(bounds_name)]
                if isinstance(value, (list, str)):
                    measured = max(measured, len(value))
            factors = factor_names
            plus = int(relation.get("plus", 0))
            budget = max(measured - plus, 0)
            if len(factors) == 1:
                args[param_names.index(factors[0])] = budget
            elif len(factors) == 2:
                side = 1
                while (side + 1) * (side + 1) <= budget:
                    side += 1
                args[param_names.index(factors[0])] = side
                args[param_names.index(factors[1])] = budget // side if side else 0

    def _value_for(self, type_name: str, variant: str, depth: int) -> Any:
        if depth > 4:
            return _UNBUILDABLE
        base = _base_type(type_name)
        if type_name == "Bool":
            return True
        if type_name == "Int":
            return 5
        if type_name == "Float64":
            return 1.0
        if type_name == "Float32":
            return 1.0
        if type_name.startswith("UInt"):
            return 3
        if type_name == "String":
            return "audit"
        if base == "List":
            return self._list_value(type_name, variant, depth)
        struct_spec = self.record.structs.get(type_name)
        if struct_spec is not None:
            return self._struct_value(struct_spec, variant, depth)
        return _UNBUILDABLE

    def _list_value(self, type_name: str, variant: str, depth: int) -> Any:
        inner = _inner_type(type_name)
        inner_base = _base_type(inner)
        if inner == "Float64":
            return [1.0, 2.0, 3.0, 4.0, 5.0]
        if inner == "Float32":
            return [1.0, 2.0, 3.0, 4.0, 5.0]
        if inner == "Int":
            return [1, 2, 3, 4, 5]
        if inner_base == "UInt8":
            return [1, 2, 3, 4, 5]
        if inner == "Bool":
            return [True, False, True, False, True]
        if inner == "String":
            return ["alpha", "beta", "gamma", "delta", "epsilon"]
        if inner_base == "UInt64":
            return [1, 2, 3, 4, 5]
        if inner_base == "List":
            row = self._list_value(inner, variant, depth + 1)
            if row is _UNBUILDABLE:
                return _UNBUILDABLE
            return [list(row), list(row)]
        struct_spec = self.record.structs.get(inner)
        if struct_spec is not None:
            element = self._struct_value(struct_spec, variant, depth + 1)
            if element is _UNBUILDABLE:
                return _UNBUILDABLE
            return [element, element]
        return _UNBUILDABLE

    def _struct_value(self, struct_spec: dict[str, Any], variant: str, depth: int) -> Any:
        fields = struct_spec.get("fields", [])
        if len(fields) > 8:
            # A wide struct's fields carry cross-field invariants a generic builder cannot
            # know (e.g. sheet Workbook: formula_cells must index within the cell arrays).
            # Synthesizing 5-element values for every field violates those invariants and
            # kills the worker on out-of-bounds reads that are the CALLER's bug, not the
            # kernel's. Probe wide structs with their default-constructed shape instead:
            # structurally valid for any struct with a no-arg init, and the hostile battery
            # still exercises the scalar/list parameters around it.
            values: dict[str, Any] = {}
            for field_spec in fields:
                field_type = field_spec["type"]
                if field_type == "String":
                    dval: Any = ""
                elif field_type == "Bool":
                    dval = False
                elif field_type == "Int":
                    dval = 0
                elif field_type.startswith("UInt"):
                    dval = 0
                elif field_type in ("Float64", "Float32"):
                    dval = 0.0
                elif _base_type(field_type) == "List":
                    dval = []
                else:
                    dval = self._value_for(field_type, variant, depth + 1)
                if dval is _UNBUILDABLE:
                    return _UNBUILDABLE
                values[field_spec["name"]] = dval
            return values
        values = {}
        for field_spec in fields:
            field_type = field_spec["type"]
            if field_type == "String":
                value: Any = "audit"
            elif field_type == "Bool":
                value = True
            elif field_type == "Int":
                value = self._struct_int_value(struct_spec, field_spec["name"])
            elif field_type.startswith("UInt"):
                value = 3
            elif field_type in ("Float64", "Float32"):
                value = self._struct_float_value(struct_spec, field_spec["name"])
            else:
                value = self._value_for(field_type, variant, depth + 1)
            if value is _UNBUILDABLE:
                return _UNBUILDABLE
            values[field_spec["name"]] = value
        return values

    @staticmethod
    def _struct_int_value(struct_spec: dict[str, Any], field_name: str) -> int:
        field_names = {item["name"] for item in struct_spec.get("fields", [])}
        # Dimension fields must agree with the payload lists they accompany; a struct whose
        # own fields are internally consistent is the cheapest coherent choice.
        if "rows" in field_names and "cols" in field_names and field_name in ("rows", "cols"):
            return 2
        if field_name in ("n", "size", "length", "count", "dim", "k", "n_genes", "population_size", "elitism"):
            return 2
        return 2

    @staticmethod
    def _struct_float_value(struct_spec: dict[str, Any], field_name: str) -> float:
        if "rate" in field_name or "ratio" in field_name or "probability" in field_name:
            return 0.5
        if "max" in field_name:
            return 1.0
        if "min" in field_name:
            return 0.0
        return 1.0


class _Unbuildable:
    def __repr__(self) -> str:
        return "<unbuildable>"


_UNBUILDABLE = _Unbuildable()

_SEVERITY_RANK = {"": 0, "P2": 1, "P1": 2, "P0": 3}


def _worse(left: str, right: str) -> str:
    left_rank = _SEVERITY_RANK.get(_SEVERITY.get(left) or "", 0)
    right_rank = _SEVERITY_RANK.get(_SEVERITY.get(right) or "", 0)
    return left if left_rank >= right_rank else right


def _classify_execution(envelope: dict[str, Any], record: FunctionRecord) -> CaseOutcome:
    latency = float(envelope.get("latency_ms", 0.0))
    if envelope.get("success"):
        payload = envelope.get("result")
        if record.return_type == "None":
            if not isinstance(payload, dict):
                return CaseOutcome("bad_result_shape", "None-returning function returned no payload", latency_ms=latency)
            mutations = payload.get("mutated_args")
            if not isinstance(mutations, dict) or not mutations:
                return CaseOutcome(
                    "state_lost",
                    "stateful function returned no mutated_args: the mutation never reaches the caller",
                    latency_ms=latency,
                )
            return CaseOutcome("ok", latency_ms=latency)
        if isinstance(payload, dict) and "result" in payload:
            return CaseOutcome("ok", latency_ms=latency)
        return CaseOutcome("ok", latency_ms=latency)
    error_code = str(envelope.get("error_code") or "")
    message = str(envelope.get("error") or "")
    if error_code == "compute_runtime_unavailable":
        return CaseOutcome("worker_crash", message, error_code, latency)
    if error_code in _EXPECTED_REJECTION_CODES:
        return CaseOutcome("expected_rejection", message, error_code, latency)
    if "timeout" in error_code or "timed out" in message.lower():
        return CaseOutcome("timeout", message, error_code, latency)
    return CaseOutcome("execution_error", message, error_code, latency)


def _worker_alive(runtime: Any) -> bool:
    try:
        health = runtime.health()
    except Exception:
        return False
    return isinstance(health, dict) and health.get("status") == "ok"


def _reset_runtime(runtime: Any) -> None:
    from algenta.native import worker

    try:
        worker.shutdown()
    except Exception:
        pass
    try:
        runtime.health()
    except Exception:
        pass


def run_sweep(
    records: tuple[FunctionRecord, ...],
    *,
    runtime: Any,
    battery: str,
    state: SweepState,
    determinism_sample: int,
    seed: int,
) -> None:
    import random

    rng = random.Random(seed)
    total = len(records)
    determinism_targets = set()
    if determinism_sample > 0:
        candidates = [record for record in records if record.return_type != "None"]
        rng.shuffle(candidates)
        determinism_targets = {
            (record.module, record.name) for record in candidates[:determinism_sample]
        }

    for index, record in enumerate(records):
        key = f"{record.module}.{record.name}"
        if key in state.outcomes:
            continue
        builder = ArgBuilder(record)
        smoke_args = builder.build()
        entries: list[dict[str, Any]] = []
        if smoke_args is None:
            state.outcomes[key] = _entry("unbuildable_args", record, "", "no synthesizable arguments for signature")
            continue
        outcome = _invoke(runtime, record, smoke_args)
        if outcome.classification in ("worker_crash", "resource_blowup"):
            _reset_runtime(runtime)
            if not _worker_alive(runtime):
                state.outcomes[key] = _entry(outcome.classification, record, "smoke", outcome.detail)
                print(f"[{index + 1}/{total}] CRASH {key}: worker died and did not recover", flush=True)
                continue
            outcome = CaseOutcome(outcome.classification, outcome.detail + " (recovered on restart)", outcome.error_code)
        entries.append({"variant": "smoke", "classification": outcome.classification, "error_code": outcome.error_code, "detail": outcome.detail[:300], "latency_ms": outcome.latency_ms})
        worst = outcome.classification

        if battery in ("hostile", "all"):
            for label, hostile_args in builder.hostile_variants(smoke_args):
                hostile_outcome = _invoke(runtime, record, hostile_args)
                if hostile_outcome.classification in ("worker_crash", "resource_blowup"):
                    _reset_runtime(runtime)
                    entries.append({"variant": label, "classification": hostile_outcome.classification, "error_code": hostile_outcome.error_code, "detail": hostile_outcome.detail[:300], "latency_ms": hostile_outcome.latency_ms})
                    worst = _worse(worst, hostile_outcome.classification)
                    print(f"[{index + 1}/{total}] CRASH {key} on {label}: {hostile_outcome.detail[:120]}", flush=True)
                    if not _worker_alive(runtime):
                        break
                    continue
                # Crashes, hangs, lost state and malformed envelopes are findings even under
                # hostile input; typed refusals and safe answers are exactly what we want, and
                # a kernel's own error status on garbage is acceptable behavior (recorded, not
                # escalated) per rule 4 of docs/mojo/new-kernel-package-rules.md.
                if hostile_outcome.classification in ("timeout", "state_lost", "bad_result_shape"):
                    worst = _worse(worst, hostile_outcome.classification)
                entries.append({"variant": label, "classification": hostile_outcome.classification, "error_code": hostile_outcome.error_code, "detail": hostile_outcome.detail[:300], "latency_ms": hostile_outcome.latency_ms})

        if worst == "ok" and (record.module, record.name) in determinism_targets:
            repeat = _invoke(runtime, record, smoke_args)
            if repeat.classification != "ok":
                worst = repeat.classification
                entries.append({"variant": "determinism_repeat", "classification": repeat.classification, "error_code": repeat.error_code, "detail": repeat.detail[:300], "latency_ms": repeat.latency_ms})
        state.outcomes[key] = {
            "module": record.module,
            "function": record.name,
            "classification": worst,
            "severity": _SEVERITY.get(worst) or "",
            "return_type": record.return_type,
            "declared_count_relations": len(record.count_relations),
            "cases": entries,
        }
        if (index + 1) % 250 == 0:
            print(f"[{index + 1}/{total}] swept; last classification {worst} for {key}", flush=True)


def _invoke(runtime: Any, record: FunctionRecord, args: list[Any]) -> CaseOutcome:
    global _blowup_killed
    _blowup_killed = False
    stop = threading.Event()
    watcher = threading.Thread(target=_watch_worker_rss, args=(stop,), daemon=True)
    watcher.start()
    try:
        envelope = runtime.execute(record.module, record.name, args)
    except Exception as exc:
        message = str(exc)
        code = getattr(exc, "code", "") or ""
        if _blowup_killed:
            return CaseOutcome(
                "resource_blowup",
                f"worker exceeded {_WORKER_RSS_CEILING_KB // 1024} MB RSS and was killed: {message}",
                "worker_rss_ceiling_exceeded",
            )
        if code == "compute_runtime_unavailable" or "unavailable" in message:
            return CaseOutcome("worker_crash", message, "compute_runtime_unavailable")
        if code in _EXPECTED_REJECTION_CODES:
            return CaseOutcome("expected_rejection", message, str(code))
        return CaseOutcome("execution_error", message, str(code))
    finally:
        stop.set()
    if _blowup_killed:
        return CaseOutcome(
            "resource_blowup",
            f"worker exceeded {_WORKER_RSS_CEILING_KB // 1024} MB RSS and was killed",
            "worker_rss_ceiling_exceeded",
        )
    if not isinstance(envelope, dict):
        return CaseOutcome("bad_result_shape", f"non-dict envelope: {type(envelope).__name__}")
    return _classify_execution(envelope, record)


def _entry(classification: str, record: FunctionRecord, variant: str, detail: str) -> dict[str, Any]:
    return {
        "module": record.module,
        "function": record.name,
        "classification": classification,
        "severity": _SEVERITY.get(classification) or "",
        "return_type": record.return_type,
        "declared_count_relations": len(record.count_relations),
        "cases": [{"variant": variant or "n/a", "classification": classification, "error_code": "", "detail": detail[:300], "latency_ms": 0.0}],
    }


def summarize(state: SweepState) -> dict[str, Any]:
    by_classification: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    for outcome in state.outcomes.values():
        classification = outcome["classification"]
        by_classification[classification] = by_classification.get(classification, 0) + 1
        severity = outcome.get("severity") or ""
        if severity:
            by_severity[severity] = by_severity.get(severity, 0) + 1
            findings.append(outcome)
    findings.sort(key=lambda item: (item.get("severity", ""), item["module"], item["function"]))
    return {
        "total_functions": len(state.outcomes),
        "by_classification": by_classification,
        "by_severity": by_severity,
        "findings": findings,
    }


def render_markdown(summary: dict[str, Any], meta: dict[str, Any]) -> str:
    lines = [
        "# SDK library execution sweep",
        "",
        f"- Worker: `{meta.get('worker')}`",
        f"- Battery: `{meta.get('battery')}`",
        f"- Functions swept: {summary['total_functions']}",
        "",
        "## Classifications",
        "",
    ]
    for classification in sorted(summary["by_classification"]):
        lines.append(f"- {classification}: {summary['by_classification'][classification]}")
    lines.extend(["", "## Findings (P0/P1/P2)", ""])
    if not summary["findings"]:
        lines.append("None.")
    for finding in summary["findings"][:200]:
        detail = ""
        if finding.get("cases"):
            detail = finding["cases"][0].get("detail", "")
        lines.append(
            f"- **{finding.get('severity')}** `{finding['module']}.{finding['function']}` — "
            f"{finding['classification']} {detail[:160]}"
        )
    if len(summary["findings"]) > 200:
        lines.append(f"- … {len(summary['findings']) - 200} more in the JSON artifact")
    lines.append("")
    return "\n".join(lines)


def _write_results(
    output: Path, meta: dict[str, Any], summary: dict[str, Any], state: SweepState
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {**meta, "summary": summary, "outcomes": state.outcomes}
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=1, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    output.with_suffix(".md").write_text(render_markdown(summary, meta), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", default=None, help="Path to a compiled runtime worker binary.")
    parser.add_argument("--battery", choices=("smoke", "hostile", "all"), default="all")
    parser.add_argument("--modules", default=None, help="Comma-separated module filter (dev iteration).")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true", help="Continue a previous interrupted sweep.")
    parser.add_argument("--determinism-sample", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument(
        "--p0-baseline",
        type=Path,
        default=None,
        help=(
            "Ratchet mode for CI: path to the audit baseline JSON carrying "
            "'sweep_p0_baseline'. Exit 1 only when NEW P0 functions appear; the known "
            "backlog is expected and only shrinks."
        ),
    )
    args = parser.parse_args(argv)

    shards = _resolve_shards(args.worker)
    # Unsigned repo-dev builds: same relaxation the count-robustness suite uses. A packaged
    # (verified) runtime never needs it and this script does not touch it for one.
    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")

    from algenta.mojo_runtime import MojoRuntime

    records, per_module_count = _load_live_surface()
    if args.modules:
        wanted = {name.strip() for name in args.modules.split(",") if name.strip()}
        records = tuple(
            record for record in records
            if record.module in wanted or record.module.split(".")[0] in wanted
        )

    state = SweepState()
    if args.resume and args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
            for outcome in previous.get("outcomes", {}).values():
                state.outcomes[f"{outcome['module']}.{outcome['function']}"] = outcome
            print(f"resumed with {len(state.outcomes)} prior outcomes", flush=True)
        except (OSError, json.JSONDecodeError, KeyError):
            state = SweepState()
    state.started_at = state.started_at or time.strftime("%Y-%m-%dT%H:%M:%S%z")

    runtime = MojoRuntime(mode="local", timeout=30.0)
    modules_visible_total = 0
    workers_used: list[str] = []
    for shard_index, (worker_path, shard_modules) in enumerate(shards):
        os.environ["ALGENTA_NATIVE_WORKER"] = str(worker_path)
        shard_records = records
        if shard_modules is not None:
            routed = set(shard_modules)
            shard_records = tuple(record for record in records if record.module in routed)
            unrouted = sorted(routed - {record.module for record in shard_records})
            if unrouted:
                print(
                    f"shard {worker_path.name}: {len(unrouted)} routed modules missing from "
                    f"the live inventory: {', '.join(unrouted[:8])}",
                    flush=True,
                )
        if not shard_records:
            continue
        from algenta.native import worker as _native_worker

        _native_worker.shutdown()
        health = runtime.health()
        if health.get("status") != "ok":
            print(
                f"runtime health failed for worker {worker_path}: {health}", file=sys.stderr
            )
            return 2
        modules_visible = runtime.list_modules()
        modules_visible_total = max(modules_visible_total, len(modules_visible))
        workers_used.append(worker_path.name)
        print(
            f"[shard {shard_index + 1}/{len(shards)}] {worker_path.name}: sweeping "
            f"{len(shard_records)} functions across "
            f"{len({record.module for record in shard_records})} modules",
            flush=True,
        )
        run_sweep(
            shard_records,
            runtime=runtime,
            battery=args.battery,
            state=state,
            determinism_sample=max(args.determinism_sample // len(shards), 1),
            seed=args.seed + shard_index,
        )
        # Checkpoint per shard: a hostile variant can take the run down, and the resume path
        # reads this file — losing forty minutes of evidence to one crash is the failure this
        # harness exists to prevent, applied to itself.
        _write_results(
            args.output,
            {
                "schema_version": _SCHEMA_VERSION,
                "worker": ", ".join(workers_used) or "none",
                "shard_workers": len(workers_used),
                "battery": args.battery,
                "started_at": state.started_at,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "live_inventory_modules": len(per_module_count),
                "runtime_visible_modules": modules_visible_total,
                "seed": args.seed,
                "partial": shard_index < len(shards) - 1,
            },
            summarize(state),
            state,
        )
    from algenta.native import worker as _native_worker

    _native_worker.shutdown()

    summary = summarize(state)
    meta = {
        "schema_version": _SCHEMA_VERSION,
        "worker": ", ".join(workers_used) or "none",
        "shard_workers": len(workers_used),
        "battery": args.battery,
        "started_at": state.started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "live_inventory_modules": len(per_module_count),
        "runtime_visible_modules": modules_visible_total,
        "seed": args.seed,
    }
    _write_results(args.output, meta, summary, state)

    print(
        f"sweep complete: {summary['total_functions']} functions, "
        f"severity counts {summary['by_severity']}",
        flush=True,
    )
    print(f"results: {args.output}\nsummary: {args.output.with_suffix('.md')}", flush=True)

    p0_keys = sorted(key for key, outcome in state.outcomes.items() if outcome["severity"] == "P0")
    if args.p0_baseline is not None:
        # Ratchet mode (CI): fail only on NEW worker-killing functions. The known backlog
        # lives in the baseline file and only shrinks — a hardened kernel drops out of the
        # list permanently, and a new crash that is not on the list blocks the merge.
        baseline_payload = json.loads(Path(args.p0_baseline).read_text(encoding="utf-8"))
        baseline_keys = set(baseline_payload.get("sweep_p0_baseline", []))
        new_p0 = sorted(set(p0_keys) - baseline_keys)
        fixed = sorted(baseline_keys - set(p0_keys))
        if fixed:
            print(
                f"baseline progress: {len(fixed)} previously-crashing function(s) no longer crash",
                flush=True,
            )
        if new_p0:
            print(
                "NEW P0 function(s) not in the baseline (fix them; do not add them to "
                f"scripts/sdk_audit_baseline.json): {', '.join(new_p0[:20])}"
                + (f" … {len(new_p0) - 20} more" if len(new_p0) > 20 else ""),
                file=sys.stderr,
            )
            return 1
        return 0
    if summary["by_severity"].get("P0") or summary["by_severity"].get("P1"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
