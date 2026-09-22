#!/usr/bin/env python3
"""Immutable release record (plan v3, Stage 5): what was built from what, and where it lives.

Binds the Algenta source commit, the contract and filter-table hashes, the toolchain identity, and
for every family the generated variants (metadata id, digest algorithm, native library and runtime
closure hashes, platform, backend, CUDA targets) with the exact Hub revisions of `v1` and `main`
after publishing. The umbrella's pinned `kernel-depends` graph is recorded alongside.

    scripts/hf_kernels/release_record.py --hub-dir hub --out docs/hf-kernels/release/record.json [--umbrella hub/algenta]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token() -> str | None:
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    env = ROOT / ".env"
    if env.is_file():
        m = re.search(r"^HF_API_KEY=(.+)$", env.read_text(), re.M)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def hub_revisions(repo: str) -> dict:
    from huggingface_hub import HfApi, constants

    if "kernel" not in constants.REPO_TYPES:
        constants.REPO_TYPES.append("kernel")
    api = HfApi(token=_token())
    out = {}
    for rev in ("v1", "main"):
        try:
            out[rev] = api.repo_info(repo, repo_type="kernel", revision=rev).sha
        except Exception as exc:  # noqa: BLE001 - recorded, not hidden
            out[rev] = f"unavailable: {type(exc).__name__}"
    return out


def family_entry(repo_dir: Path, repo: str) -> dict:
    variants = {}
    for vdir in sorted((repo_dir / "build").iterdir()):
        meta_path = vdir / "metadata.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text())
        pkg = next((d for d in vdir.iterdir() if d.is_dir() and d.name.startswith("algenta")), None)
        native = {}
        if pkg and (pkg / "_native" / "manifest.json").is_file():
            m = json.loads((pkg / "_native" / "manifest.json").read_text())
            native = {"platform": m.get("platform"), "backend": m.get("backend"), "library": m.get("library"), "cuda_targets": m.get("cuda_targets", []),
                      "source_commit": m.get("source_commit"), "mojo_version": m.get("mojo_version"), "runtime_tag": m.get("runtime_tag"),
                      "files": {k: v.get("sha256") for k, v in (m.get("files") or {}).items()}}
        variants[vdir.name] = {"metadata_id": meta.get("id"), "metadata_sha256": sha256(meta_path), "backend": meta.get("backend"), "native": native}
    return {"repo": repo, "revisions": hub_revisions(repo), "variants": variants, "card_sha256": sha256(repo_dir / "README.md") if (repo_dir / "README.md").is_file() else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hub-dir", required=True, type=Path, help="directory holding one generated repository per family (hub/<family>)")
    ap.add_argument("--umbrella", type=Path, help="generated umbrella repository directory")
    ap.add_argument("--org", default="thyn-ai")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    mojo_version = subprocess.run(["pixi", "run", "mojo", "--version"], cwd=ROOT / "mojo_env", capture_output=True, text=True).stdout.strip().splitlines()[0]
    record = {
        "schema": 1,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source": {"repository": f"{a.org}/algenta", "commit": commit},
        "inputs": {
            "runtime_library_contract_sha256": sha256(ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json"),
            "hf_kernel_filters_sha256": sha256(ROOT / "scripts" / "hf_kernel_filters.json"),
            "abi_sha256": sha256(ROOT / "mojo" / "hfkernel" / "abi.mojo"),
            "cuda_decode_session_sha256": sha256(ROOT / "mojo" / "hfkernel" / "cuda_decode_session.mojo"),
            "generator_sha256": sha256(ROOT / "scripts" / "generate_hf_kernel_package.py"),
            "builder_sha256": sha256(ROOT / "scripts" / "build_hf_kernel_family.py"),
            "templates_sha256": {p.name: sha256(p) for p in sorted((ROOT / "scripts" / "hf_kernels" / "templates").glob("*.py"))},
        },
        "toolchain": {"mojo": mojo_version, "pixi_lock_sha256": sha256(ROOT / "mojo_env" / "pixi.lock")},
        "families": {},
        "umbrella": None,
    }
    for repo_dir in sorted(p for p in a.hub_dir.iterdir() if p.is_dir() and (p / "build").is_dir()):
        record["families"][repo_dir.name] = family_entry(repo_dir, f"{a.org}/{repo_dir.name}")
    if a.umbrella and (a.umbrella / "build").is_dir():
        meta = json.loads(next((a.umbrella / "build").rglob("metadata.json")).read_text())
        record["umbrella"] = {"repo": f"{a.org}/algenta", "revisions": hub_revisions(f"{a.org}/algenta"), "kernel_depends": meta.get("kernel-depends", []), "metadata_id": meta.get("id")}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(record, indent=1) + "\n")
    print(f"release record: {len(record['families'])} families -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
