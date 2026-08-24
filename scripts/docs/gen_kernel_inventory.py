#!/usr/bin/env python3
"""Generate the Kernel inventory page from the packaged public contract.

Source of truth: the ``engine_kernels`` section of
``packages/algenta/algenta/runtime_library_contract.json`` (regenerated from the Mojo
sources by ``scripts/generate_algenta_runtime_contract.py``). The page renders the PUBLIC
surface of the pointer-based CUDA/Metal kernels the engine races — capability declaration,
not callability: these kernels take device pointers and never cross a JSON frame, so they
are deliberately not runtime-library modules.

Writes ``gitbook/engine/kernel-inventory.md``. ``--check`` fails if it is stale
(CI no-drift gate).
Regression floor: the published kernel count must not silently collapse.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json"
OUT = ROOT / "gitbook" / "engine" / "kernel-inventory.md"

# The published surface may only grow. Adding kernels never requires touching this file;
# RAISE it deliberately after `make inventory-refresh` when the inventory grows past it,
# and never lower it — a collapse below the floor means extraction broke or kernels
# vanished, and either is a stop-the-world event.
KERNEL_FLOOR = 137

ROLE_LABELS: dict[str, str] = {
    "embed": "Embedding gather",
    "projection": "Fused norm + projection (QKV / O / FFN GEMV)",
    "ffn_projection": "FFN gate/up projection + norm",
    "ffn_epilogue": "FFN activation combine (SwiGLU / GeGLU)",
    "prefill_gemm": "Prefill GEMM tile",
    "decode_attention": "Decode attention (split-K flash-decoding / SDPA)",
    "prefill_attention": "Prefill attention (tiled / windowed)",
    "flash_attention": "Flash-style attention",
    "kv_producer": "KV-cache producer",
    "rope": "RoPE + KV-cache write",
    "norm": "Norm / RMSNorm rows",
    "lm_head": "LM head + argmax",
    "graph_capture": "CUDA graph advance",
    "dequant": "Dequantize / unpack",
    "tc_shim": "Tensor-core shim (cuBLAS HMMA escape hatch)",
    "other": "Utility",
}

FAMILY_LABELS: dict[str, str] = {
    "qwen3_llama": "qwen3/llama",
    "gemma3": "gemma3",
}

BACKEND_TITLES: dict[str, str] = {
    "metal": "Metal (Apple Silicon)",
    "cuda": "CUDA (NVIDIA)",
    "portable": "Portable (CPU)",
}


def _backend_staging_note() -> dict[str, str]:
    """Staging tiers per backend, read from the capability table (single source of truth)."""
    pkg = ROOT / "packages" / "algenta"
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))
    from algenta.model_capabilities import BACKEND_FACT_RANGES  # noqa: PLC0415

    return {
        backend: ", ".join(str(tier) for tier in ranges["staging_tiers"])
        for backend, ranges in BACKEND_FACT_RANGES.items()
    }


def extract() -> dict:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    section = payload.get("engine_kernels")
    if not isinstance(section, dict):
        raise SystemExit("contract has no engine_kernels section — run `make inventory-refresh`")
    kernels = section.get("kernels")
    modules = section.get("modules")
    if not isinstance(kernels, list) or not isinstance(modules, list):
        raise SystemExit("engine_kernels section is malformed — run `make inventory-refresh`")
    return {"kernels": kernels, "modules": modules}


def render(section: dict) -> str:
    kernels = section["kernels"]
    modules = section["modules"]
    staging = _backend_staging_note()

    by_backend: dict[str, list[dict]] = defaultdict(list)
    for kernel in kernels:
        by_backend[kernel["backend"]].append(kernel)

    families_by_backend: dict[str, set[str]] = defaultdict(set)
    for kernel in kernels:
        families_by_backend[kernel["backend"]].update(kernel["families"])

    lines: list[str] = [
        "---",
        "icon: microchip",
        (
            "description: The public inventory of the engine's CUDA and Metal kernels — "
            "what ships, per backend, per model family, and the evidence behind each module."
        ),
        "---",
        "",
        "# Kernel inventory",
        "",
        (
            "The engine's racing kernels — the fused CUDA and Metal kernels a resident decode, "
            "prefill, or batched step is made of — are published here as a capability "
            "inventory. They are **not** runtime-library functions: their signatures take "
            "device pointers, which never cross a JSON frame, so they are declared, not "
            "callable. Every kernel that ships is listed; the inventory is generated from the "
            "engine sources and ratcheted, so a kernel can never silently disappear from the "
            "public surface."
        ),
        "",
        "## Surface at a glance",
        "",
        "| Backend | Kernels | Model families | Staging tiers (elements) |",
        "| --- | --- | --- | --- |",
    ]
    for backend in sorted(by_backend):
        families = ", ".join(
            FAMILY_LABELS.get(family, family)
            for family in sorted(families_by_backend[backend])
        )
        lines.append(
            f"| {BACKEND_TITLES.get(backend, backend)} | {len(by_backend[backend])} "
            f"| {families} | {staging.get(backend, '—')} |"
        )
    lines.extend(
        [
            "",
            (
                "Staging is the decode kernels' shared-memory ceiling per build tier — one "
                "binary per tier; a checkpoint whose staged vectors exceed every tier of a "
                "backend is refused naming the value and the tiers. See the "
                "[Model support matrix](model-support-matrix.md) for the fact ranges that "
                "decide support."
            ),
            "",
        ]
    )

    for backend in sorted(by_backend):
        lines.extend(
            [
                f"## {BACKEND_TITLES.get(backend, backend)} kernels",
                "",
                "| Kernel | Role | Family profile |",
                "| --- | --- | --- |",
            ]
        )
        ordered = sorted(
            by_backend[backend],
            key=lambda kernel: (kernel["role"], kernel["module"], kernel["name"]),
        )
        for kernel in ordered:
            families = ", ".join(
                FAMILY_LABELS.get(family, family) for family in sorted(kernel["families"])
            )
            lines.append(
                f"| `{kernel['name']}` | {ROLE_LABELS.get(kernel['role'], kernel['role'])} "
                f"| {families} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Evidence by module",
            "",
            (
                "Each kernel module declares its own evidence in its `@capability-module` "
                "block: the golden vectors its correctness runs against and the benchmark it "
                "is raced under. The conformance battery gates every release on these paths."
            ),
            "",
            "| Module | Backend | Kernels | Golden vectors | Benchmark |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for module in sorted(modules, key=lambda item: item["name"]):
        lines.append(
            f"| `{module['name']}` | {module['backend']} | {module['kernel_count']} "
            f"| `{module.get('golden_vectors', '—')}` | `{module.get('benchmark', '—')}` |"
        )
    lines.extend(
        [
            "",
            "## Querying the inventory from the SDK",
            "",
            (
                "The same inventory ships in the runtime contract and is queryable from "
                "`algenta` — filters compose:"
            ),
            "",
            "```python",
            "from algenta import engine_kernels, engine_kernel_backends",
            "",
            'engine_kernel_backends()                      # ("cuda", "metal")',
            'len(engine_kernels(backend="metal"))         # every Metal kernel that ships',
            'engine_kernels(backend="cuda", family="gemma3")   # the Gemma 3 CUDA lane',
            'engine_kernels(role="tc_shim")               # the tensor-core escape hatch',
            "```",
            "",
            (
                "Kernel entries map a stable public name to the private engine symbol, its "
                "backend, its model-family profile, and its role class. A kernel leaving the "
                "inventory is a contract change, enforced by the SDK audit gates — never a "
                "silent regen side effect."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the page is stale")
    args = ap.parse_args()

    section = extract()
    kernel_count = len(section["kernels"])
    if kernel_count < KERNEL_FLOOR:
        print(f"EXTRACTION BROKEN: {kernel_count} kernels < floor {KERNEL_FLOOR}")
        return 1
    content = render(section)

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != content:
            print(f"DRIFT: {OUT.relative_to(ROOT)} is stale vs the contract — run `make docs-gen`")
            return 1
        print(f"kernel-inventory.md OK ({kernel_count} kernels)")
        return 0

    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({kernel_count} kernels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
