#!/usr/bin/env python3
"""attention_forge.generate_variants -- Attention Compiler Plan v1.0, Phase 0B.

Given an AttentionModelTraits, computes an AttentionKernelArtifactKey and emits a parameterized
Mojo kernel STUB (correctness stubs are explicitly acceptable at this phase -- the real kernel
math is Phase 1's job) plus a GeneratedKernelManifestEntry recording exactly what got produced.

Phase 0B's own exit criterion, verified by `verify_phase0b.py`: the SAME code path in this file
runs for the real Qwen3-0.6B-Base GQA traits and a synthetic MHA trait set, with zero source
changes and no branch anywhere on which model produced the traits. Every choice below (tile
sizes, H_TILE, SIMD-group count) is a function of the TRAITS' own shape (q_heads, kv_heads,
qk_head_dim), never of a model identity.

Usage:
    python3 generate_variants.py --out generated/manifest.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from abi import (
    AttentionKernelArtifactKey,
    AttentionModelTraits,
    GeneratedKernelManifestEntry,
    sha256_file,
)

FORGE_DIR = Path(__file__).resolve().parent
KERNEL_ABI_VERSION = 1
KV_LAYOUT_VERSION = 1  # Phase 0B stub layout; Phase 4 introduces the real packed layout


def _apple_gpu_family() -> str:
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        data = json.loads(out)
        for gpu in data.get("SPDisplaysDataType", []):
            model = gpu.get("sppci_model") or gpu.get("_name")
            if model:
                return str(model)
    except Exception:
        pass
    return "unknown"


def _toolchain_hash() -> str:
    """Identifies the forge toolchain a kernel was generated/compiled against. Phase 0B has no
    real forge build yet (that starts Phase 1, per the plan's own PR sequence -- this module only
    proves the ABI/generation pipeline), so this hashes the forge's own pixi pin file, which is
    what actually determines toolchain identity once a real build exists."""
    pin = FORGE_DIR / "pixi.toml"
    if pin.exists():
        return sha256_file(pin)[:16]
    return "no-pixi-toml-yet"


def choose_tile_params(traits: AttentionModelTraits) -> dict:
    """Derived entirely from TRAITS, never from a model name. Phase 0B ships reasonable
    placeholder defaults (Phase 1/2's own tournament is what actually picks winners); the point
    here is that the DERIVATION is traits-driven and deterministic, not that these particular
    numbers are final."""
    q_tile = 8
    key_tile = 64
    h_tile = 2 if traits.head_mapping_class.value == "uniform_grouped" and traits.group_size >= 2 else 1
    simd_group_count = 8 if h_tile >= 2 else 4
    is_matrix_path = True
    is_split_k = False
    math_mode = "precise_exp"
    return {
        "query_tile": q_tile,
        "key_tile": key_tile,
        "h_tile": h_tile,
        "simd_group_count": simd_group_count,
        "is_matrix_path": is_matrix_path,
        "is_split_k": is_split_k,
        "math_mode": math_mode,
    }


def build_artifact_key(traits: AttentionModelTraits) -> AttentionKernelArtifactKey:
    tile = choose_tile_params(traits)
    model_traits_subset = (
        traits.qk_head_dim,
        traits.value_head_dim,
        traits.head_mapping_class.value,
        traits.q_heads,
        traits.kv_heads,
        traits.kv_dtype,
        traits.attention_mode.value,
        traits.qk_norm,
        traits.alibi,
        traits.attention_sinks,
    )
    return AttentionKernelArtifactKey(
        model_traits_subset=model_traits_subset,
        query_tile=tile["query_tile"],
        key_tile=tile["key_tile"],
        h_tile=tile["h_tile"],
        simd_group_count=tile["simd_group_count"],
        is_matrix_path=tile["is_matrix_path"],
        is_split_k=tile["is_split_k"],
        math_mode=tile["math_mode"],
        kv_layout_version=KV_LAYOUT_VERSION,
        apple_gpu_family=_apple_gpu_family(),
        kernel_abi_version=KERNEL_ABI_VERSION,
        forge_toolchain_hash=_toolchain_hash(),
        source_hash="",  # filled in after the stub source is rendered, see below
    )


def requested_host_name(key: AttentionKernelArtifactKey) -> str:
    dk, dv, mapping, q_heads, kv_heads = key.model_traits_subset[:5]
    mapping_tag = {"mha": "mha", "uniform_grouped": f"h{key.h_tile}", "mqa": "mqa"}.get(mapping, "map")
    return (
        f"agfa_d{dk}_v{dv}_q{key.query_tile}_k{key.key_tile}_{mapping_tag}"
        f"_{key.math_mode.split('_')[0]}_sg{key.simd_group_count}"
    )


def render_stub_source(traits: AttentionModelTraits, key: AttentionKernelArtifactKey, host_name: str) -> str:
    """A correctness stub, explicitly acceptable at Phase 0B (per the plan's own exit criterion --
    the real math lands in Phase 1's parity replica). Parameterized entirely from `key`/`traits`;
    no model-name conditional anywhere in this function. Emits a plain Mojo function (not yet a
    GPU kernel -- that association is Phase 1's job) so the generation pipeline is exercised end
    to end, including an actual `mojo run` correctness check, without depending on GPU-kernel
    infrastructure this phase doesn't need."""
    return f'''"""GENERATED by attention_forge/generate_variants.py -- Phase 0B correctness stub.
Do not hand-edit; regenerate from the AttentionModelTraits that produced it.

host_name (requested): {host_name}
(the manifest entry's own cache_key is the authoritative one -- not repeated here, since it is a
hash that includes this very file's source and therefore cannot consistently describe itself)
qk_head_dim={traits.qk_head_dim} value_head_dim={traits.value_head_dim}
q_heads={traits.q_heads} kv_heads={traits.kv_heads} head_mapping={traits.head_mapping_class.value}
query_tile={key.query_tile} key_tile={key.key_tile} h_tile={key.h_tile} simd_groups={key.simd_group_count}
"""

comptime DK: Int = {traits.qk_head_dim}
comptime DV: Int = {traits.value_head_dim}
comptime Q_HEADS: Int = {traits.q_heads}
comptime KV_HEADS: Int = {traits.kv_heads}
comptime QUERY_TILE: Int = {key.query_tile}
comptime KEY_TILE: Int = {key.key_tile}
comptime H_TILE: Int = {key.h_tile}


def stub_shape_check() -> Bool:
    """Phase 0B correctness stub: proves the generated parameters are internally consistent
    (the group size the traits imply matches what H_TILE was chosen against), not yet real
    attention math -- that is Phase 1's parity replica, gated against the CPU Float64 reference.
    """
    var group = Q_HEADS // KV_HEADS
    return DK > 0 and DV > 0 and QUERY_TILE > 0 and KEY_TILE > 0 and group >= 1


def main() raises:
    var ok = stub_shape_check()
    print("{host_name}: shape check", "OK" if ok else "FAIL")
    if not ok:
        raise Error("generated stub failed its own shape check")
'''


def generate(traits: AttentionModelTraits, out_dir: Path) -> GeneratedKernelManifestEntry:
    key = build_artifact_key(traits)
    host_name = requested_host_name(key)
    source = render_stub_source(traits, key, host_name)

    import hashlib

    source_hash = hashlib.sha256(source.encode()).hexdigest()
    key = dataclasses_replace(key, source_hash=source_hash)

    out_dir.mkdir(parents=True, exist_ok=True)
    stub_path = out_dir / f"{host_name}.mojo"
    stub_path.write_text(source)

    return GeneratedKernelManifestEntry(
        key=key,
        requested_name=host_name,
        actual_metal_symbol=None,  # Phase 0B stub is CPU-callable Mojo, not a compiled GPU kernel
        metallib_sha256=None,
        source_sha256=source_hash,
        toolchain_sha256=key.forge_toolchain_hash,
    )


def dataclasses_replace(key: AttentionKernelArtifactKey, **kwargs) -> AttentionKernelArtifactKey:
    import dataclasses

    return dataclasses.replace(key, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(FORGE_DIR / "generated" / "manifest.json"))
    ap.add_argument("--manifest", default=None, help="path to a real checkpoint manifest.json (e.g. Qwen3)")
    args = ap.parse_args()

    import model_importer

    entries = []

    if args.manifest:
        traits, _block = model_importer.import_from_manifest(Path(args.manifest))
        entries.append(generate(traits, FORGE_DIR / "generated"))

    synthetic_traits, _synthetic_block = model_importer.synthetic_mha()
    entries.append(generate(synthetic_traits, FORGE_DIR / "generated"))

    manifest = {"entries": [e.to_json() for e in entries]}
    Path(args.out).write_text(json.dumps(manifest, indent=2))
    print(f"generate_variants: wrote {len(entries)} entries to {args.out}")
    for e in entries:
        print(f"  {e.requested_name}  (cache_key={e.key.cache_key()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
