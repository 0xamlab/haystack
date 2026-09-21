"""The public engine-kernel inventory: source-driven discovery, adaptivity, and the floor.

The racing kernels are private (leading underscore) pointer-based CUDA/Metal functions, so
they are NOT JSON-callable runtime libraries; their public surface is the inventory this
file pins down. Three invariants matter:

1. STABILITY — the current tree publishes a known surface (floors + named entries), the
   payload is deterministic, and the two artifacts that publish it — the shipped contract
   and the GitBook inventory page — agree with discovery. Counts are DERIVED, never pinned:
   a kernel landing must not require editing this file.
2. ADAPTIVITY — a newly added kernel-shaped function in a scanned package flows into the
   inventory with the right backend/family/role WITHOUT any hand-maintained list (the PR
   #850 gemma3 add-ons must appear the day they merge).
3. LOUDNESS — a kernel module that cannot be attributed (no declared backend) fails
   discovery instead of publishing a half-described kernel.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.runtime import mojo_inventory  # noqa: E402
from apps.runtime.mojo_inventory import (  # noqa: E402
    EngineKernelDiscoveryError,
    discover_engine_kernels,
    engine_kernels_payload,
)
from scripts.generate_engine_kernel_floor import grow_floor, load_floor  # noqa: E402

# Regression floors for the published kernel surface. The surface may only grow; raise
# these deliberately after `make inventory-refresh`, never lower them.
KERNEL_MODULE_FLOOR = 19
KERNEL_COUNT_FLOOR = 137

# The two artifacts the discovered surface is published through. Both are GENERATED from
# discovery, so nothing about them is pinned here — they are read and compared:
#   contract  <- scripts/generate_algenta_runtime_contract.py  (gate: `make inventory-check`)
#   page      <- scripts/docs/gen_kernel_inventory.py          (gate: `make docs-check`)
CONTRACT_PATH = _REPO_ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json"
INVENTORY_PAGE = _REPO_ROOT / "gitbook" / "engine" / "kernel-inventory.md"

# A "Surface at a glance" data row: | <Backend title> | <count> | ... |. The header row's
# second cell is not a number and the separator row has no cells, so only data rows match.
_GLANCE_ROW = re.compile(r"^\| *([^|]+?) *\| *(\d+) *\|", re.MULTILINE)


def _published_contract_kernels() -> dict:
    """The ``engine_kernels`` section of the shipped SDK-facing contract."""
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    return payload["engine_kernels"]


def _published_page_backend_counts() -> dict[str, int]:
    """Per-backend counts exactly as the published inventory page advertises them.

    Parsed from the page a user reads rather than from the generator that wrote it, so a
    generator change cannot make the page and the tree agree by construction. The backend
    is the title's first word ("CUDA (NVIDIA)", "Metal (Apple Silicon)", "Portable (CPU)"),
    which also covers a backend gen_kernel_inventory has no title for.
    """
    text = INVENTORY_PAGE.read_text(encoding="utf-8")
    assert "## Surface at a glance" in text, f"{INVENTORY_PAGE} has no glance table"
    glance = text.split("## Surface at a glance", 1)[1].split("\n## ", 1)[0]
    counts: dict[str, int] = {}
    for title, count in _GLANCE_ROW.findall(glance):
        counts[title.strip().split()[0].lower()] = int(count)
    assert counts, f"no backend rows parsed out of {INVENTORY_PAGE}"
    return counts


_CUDA_CAPABILITY_BLOCK = '''"""
{module_doc}

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: {backend}
surfaces: none
golden_vectors: mojo/tests/libs/test_residentk_session.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate_metal.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""

'''

_KERNEL_SOURCE = (
    "def {symbol}(y: Int, x: Int, n_i64: Int64):\n"
    '    """One kernel."""\n'
    "    pass\n"
)


def _write_kernel_module(
    engine_root: Path,
    package: str,
    file_name: str,
    symbols: tuple[str, ...],
    *,
    backend: str = "cuda",
    doc: str = "a synthetic kernel module for discovery tests.",
) -> Path:
    path = engine_root / package / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    body = _CUDA_CAPABILITY_BLOCK.format(module_doc=doc, backend=backend)
    body += "\n".join(_KERNEL_SOURCE.format(symbol=symbol) for symbol in symbols)
    path.write_text(body, encoding="utf-8")
    return path


def test_real_tree_publishes_the_racing_kernels() -> None:
    modules = discover_engine_kernels()
    payload = engine_kernels_payload(modules)

    assert len(modules) >= KERNEL_MODULE_FLOOR
    assert payload["kernel_count"] >= KERNEL_COUNT_FLOOR
    assert payload["kernel_count"] == len(payload["kernels"])
    assert payload["module_count"] == len(payload["modules"])
    assert sum(module["kernel_count"] for module in payload["modules"]) == payload[
        "kernel_count"
    ]

    # ── DERIVED per-backend surface — floors and equalities, never a pinned count ──
    # The engine tree is the source of truth, so the per-backend numbers are computed from
    # the kernels just discovered: a kernel landing changes them WITHOUT anyone editing this
    # file. (This assertion used to pin `{"cuda": 80, "metal": 57}`; the CUDA lane then grew
    # to 142 across race rounds 4-19 and the pin went red — invisible, because no CI leg runs
    # this file. Same rule the sibling gates follow: "floors, not fixtures".)
    discovered_counts = dict(Counter(kernel["backend"] for kernel in payload["kernels"]))
    assert payload["backend_counts"] == discovered_counts
    # Every published backend actually publishes kernels — a backend emptying out is the
    # visibility loss the floors exist to stop.
    assert discovered_counts and all(count > 0 for count in discovered_counts.values())

    # The shipped SDK-facing contract is generated from this same discovery
    # (`make inventory-refresh`, gated by `make inventory-check`), so it must agree
    # kernel-for-kernel — anything else is a contract that was not regenerated.
    contract = _published_contract_kernels()
    assert contract["kernel_count"] == payload["kernel_count"], "run: make inventory-refresh"
    assert contract["module_count"] == payload["module_count"], "run: make inventory-refresh"
    assert contract["backend_counts"] == discovered_counts, "run: make inventory-refresh"
    assert {(kernel["module"], kernel["name"]) for kernel in contract["kernels"]} == {
        (kernel["module"], kernel["name"]) for kernel in payload["kernels"]
    }, "run: make inventory-refresh"

    # The published GitBook page is generated from the contract
    # (scripts/docs/gen_kernel_inventory.py, gated by `make docs-check`), so what it
    # advertises must be what the tree ships — counted per backend and named per kernel.
    assert _published_page_backend_counts() == discovered_counts, "run: make docs-gen"
    page = INVENTORY_PAGE.read_text(encoding="utf-8")
    unpublished = sorted(
        kernel["name"] for kernel in payload["kernels"] if f"| `{kernel['name']}` |" not in page
    )
    assert not unpublished, (
        f"{len(unpublished)} discovered kernel(s) missing from "
        f"gitbook/engine/kernel-inventory.md (e.g. {unpublished[:5]}) — run: make docs-gen"
    )

    by_key = {
        (kernel["module"], kernel["name"]): kernel for kernel in payload["kernels"]
    }
    # The fused Metal decode chain (residentk.kernels) — the lane every Apple Silicon race runs.
    for name in (
        "norm_gemv_kernel",
        "qk_rope_write_kernel",
        "sdpa_kernel",
        "gemv_accum_kernel",
        "norm_gemv2_swiglu_kernel",
        "lmhead_argmax_kernel",
    ):
        kernel = by_key[("residentk.kernels", name)]
        assert kernel["backend"] == "metal"
        assert kernel["families"] == ["qwen3_llama"]
        assert kernel["symbol"] == f"_{name}"
    # The Gemma 3 CUDA lane — a distinct kernel set, own family profile.
    g3 = by_key[("residentk.kernels_gemma3", "g3_norm_gemv2_geglu_kernel")]
    assert g3["backend"] == "cuda"
    assert g3["families"] == ["gemma3"]
    assert g3["prefix"] == "g3"
    # The tensor-core escape hatch is published as the tc_shim role class.
    tc = [kernel for kernel in payload["kernels"] if kernel["role"] == "tc_shim"]
    assert tc and all(kernel["module"] == "residentk.tc_shim_bridge" for kernel in tc)


def test_public_names_are_readable_never_private_or_truncated() -> None:
    payload = engine_kernels_payload(discover_engine_kernels())
    for kernel in payload["kernels"]:
        assert not kernel["name"].startswith("_"), kernel
        assert kernel["symbol"] == f"_{kernel['name']}", kernel
        assert kernel["module"] and "." in kernel["module"]
        assert kernel["families"], kernel
        assert kernel["role"], kernel


def test_backend_and_family_sets() -> None:
    payload = engine_kernels_payload(discover_engine_kernels())
    backends = {kernel["backend"] for kernel in payload["kernels"]}
    families = {family for kernel in payload["kernels"] for family in kernel["families"]}
    assert backends == {"cuda", "metal"}
    assert families == {"qwen3_llama", "gemma3"}
    # Metal ships the qwen3/llama lane only (the capability table's backend fact ranges).
    assert all(
        kernel["families"] == ["qwen3_llama"]
        for kernel in payload["kernels"]
        if kernel["backend"] == "metal"
    )


def test_payload_is_deterministic() -> None:
    first = engine_kernels_payload(discover_engine_kernels())
    second = engine_kernels_payload(discover_engine_kernels())
    assert first == second


def test_new_kernel_file_flows_into_the_inventory_automatically(tmp_path: Path) -> None:
    """PR #850 shape: a brand-new gemma3 kernel file appears -> discovered, no lists edited."""
    engine_root = tmp_path / "engine"
    _write_kernel_module(
        engine_root,
        "residentk",
        "kernels_prefill_gemma3.mojo",
        ("_pf_gemm_newlane_kernel", "_g3_ropewrt_batched_kernel"),
        backend="cuda",
        doc="residentk.kernels_prefill_gemma3 — synthetic gemma3 add-on.",
    )

    payload = engine_kernels_payload(discover_engine_kernels(engine_root))
    by_name = {kernel["name"]: kernel for kernel in payload["kernels"]}

    # Module name carries gemma3 -> whole file lands in the gemma3 family profile.
    plain = by_name["pf_gemm_newlane_kernel"]
    assert plain["backend"] == "cuda"
    assert plain["families"] == ["gemma3"]
    assert plain["role"] == "prefill_gemm"
    assert plain["prefix"] == "pf"
    # The _g3_ marker works too, and rope classification beats the batched decode shape.
    rope = by_name["g3_ropewrt_batched_kernel"]
    assert rope["families"] == ["gemma3"]
    assert rope["role"] == "rope"
    assert rope["prefix"] == "g3"


def test_new_kernel_in_existing_metal_package_flows_in_automatically(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    _write_kernel_module(
        engine_root,
        "metaldispatch",
        "session_prefill.mojo",
        ("_pf_attn_synthetic_kernel",),
        backend="metal",
        doc="metaldispatch.session_prefill — synthetic metal kernel.",
    )
    payload = engine_kernels_payload(discover_engine_kernels(engine_root))
    (kernel,) = payload["kernels"]
    assert kernel["module"] == "metaldispatch.session_prefill"
    assert kernel["backend"] == "metal"
    assert kernel["families"] == ["qwen3_llama"]
    assert kernel["role"] == "prefill_attention"


def test_host_helpers_stay_out_of_the_inventory(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    path = engine_root / "residentk" / "session.mojo"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _CUDA_CAPABILITY_BLOCK.format(
            module_doc="residentk.session — host-side session glue.", backend="cuda"
        )
        + "def _ceil_div(a: Int, b: Int) -> Int:\n    return a\n\n"
        + "def public_probe() -> Int:\n    return 1\n",
        encoding="utf-8",
    )
    assert discover_engine_kernels(engine_root) == ()


def test_kernel_module_without_backend_fails_loudly(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    path = engine_root / "residentk" / "kernels_noattr.mojo"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '"""residentk.kernels_noattr — no capability block at all."""\n\n'
        + _KERNEL_SOURCE.format(symbol="_orphan_kernel"),
        encoding="utf-8",
    )
    with pytest.raises(EngineKernelDiscoveryError, match="backend"):
        discover_engine_kernels(engine_root)


def test_missing_package_dirs_discover_nothing(tmp_path: Path) -> None:
    assert discover_engine_kernels(tmp_path / "empty") == ()


def test_floor_only_grows_never_removes() -> None:
    live = [
        {
            "name": "kept_kernel",
            "module": "residentk.kernels",
            "backend": "metal",
            "families": ["qwen3_llama"],
        },
        {
            "name": "new_kernel",
            "module": "residentk.kernels_gemma3",
            "backend": "cuda",
            "families": ["gemma3"],
        },
    ]
    floor = {
        "schema": 1,
        "kernel_count": 2,
        "kernels": [
            {
                "name": "kept_kernel",
                "module": "residentk.kernels",
                "backend": "metal",
                "families": ["qwen3_llama"],
            },
            {
                "name": "gone_kernel",
                "module": "residentk.kernels",
                "backend": "metal",
                "families": ["qwen3_llama"],
            },
        ],
    }
    grown, added = grow_floor(floor, live)
    grown_keys = {(entry["module"], entry["name"]) for entry in grown["kernels"]}
    # The new kernel is added, the live one kept, and the GONE entry is NOT removed —
    # removal stays a manual edit, which is exactly the ratchet's point.
    assert ("residentk.kernels_gemma3", "new_kernel") in grown_keys
    assert ("residentk.kernels", "kept_kernel") in grown_keys
    assert ("residentk.kernels", "gone_kernel") in grown_keys
    assert added == ["residentk.kernels_gemma3.new_kernel"]
    assert grown["kernel_count"] == len(grown["kernels"]) == 3


def test_checked_in_floor_covers_the_live_surface() -> None:
    floor = load_floor()
    assert floor["schema"] == 1
    assert floor["kernel_count"] >= KERNEL_COUNT_FLOOR
    assert floor["kernel_count"] == len(floor["kernels"])
    live = engine_kernels_payload(discover_engine_kernels())["kernels"]
    live_keys = {(kernel["module"], kernel["name"]) for kernel in live}
    floor_keys = {(entry["module"], entry["name"]) for entry in floor["kernels"]}
    assert live_keys <= floor_keys, (
        "live kernels missing from the floor — run scripts/generate_engine_kernel_floor.py"
    )


def test_inventory_is_not_part_of_the_json_callable_modules() -> None:
    """Pointer kernels must never leak into the JSON-frameable runtime-library contract."""
    # One full-tree scan (all discovered functions, executable or not): kernel modules have
    # NO public functions, so they never become runtime-library modules, and no kernel name
    # may collide with a published callable name.
    modules = mojo_inventory.discover_runtime_library_modules(executable_only=False)
    assert "residentk.kernels" not in {module.import_path for module in modules}
    kernel_names = {
        kernel.name
        for kernel_module in discover_engine_kernels()
        for kernel in kernel_module.kernels
    }
    library_functions = {
        function.name for module in modules for function in module.functions
    }
    assert kernel_names.isdisjoint(library_functions)
