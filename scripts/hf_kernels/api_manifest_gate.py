#!/usr/bin/env python3
"""Versioning gate: a family's public API may grow within `v1`; anything removed or changed needs `v2`.

Compares the contract shipped at a published revision (`build/<variant>/<pkg>/_contract.py`,
downloaded from the Hub) with the contract a freshly generated repository would publish. Every
function is keyed by module and name; its parameter names, types, defaults and return type form its
signature. Additions are reported and allowed; removals and signature changes fail the gate.

    scripts/hf_kernels/api_manifest_gate.py --repo thyn-ai/algenta-stats --revision v1 --generated hub/algenta-stats
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path


def _load_contract(path: Path) -> dict:
    spec = importlib.util.spec_from_file_location(f"_contract_{abs(hash(str(path)))}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CONTRACT


def _signatures(contract: dict) -> dict[str, dict]:
    out = {}
    for mname, m in contract["modules"].items():
        for fname, f in m["functions"].items():
            params = [(p["name"], p["type"], p.get("has_default", False), p.get("default", None)) for p in f["params"]]
            out[f"{mname}.{fname}"] = {"params": params, "returns": f["return_type"], "count_relations": f.get("count_relations") or []}
    return out


def _published_contract(repo: str, revision: str, cache: str) -> tuple[dict, str]:
    from huggingface_hub import HfApi, constants, hf_hub_download

    if "kernel" not in constants.REPO_TYPES:
        constants.REPO_TYPES.append("kernel")
    api = HfApi(token=os.environ.get("HF_TOKEN") or _env_token())
    info = api.repo_info(repo, repo_type="kernel", revision=revision, files_metadata=False)
    files = sorted(entry.path for entry in api.list_repo_tree(repo, repo_type="kernel", revision=revision, recursive=True)
                   if type(entry).__name__ == "RepoFile" and entry.path.endswith("/_contract.py"))
    if not files:
        raise SystemExit(f"{repo}@{revision}: no _contract.py published")
    path = hf_hub_download(repo, files[0], repo_type="kernel", revision=revision, cache_dir=cache, token=api.token)
    return _load_contract(Path(path)), info.sha


def _env_token() -> str | None:
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.is_file():
        m = re.search(r"^HF_API_KEY=(.+)$", env.read_text(), re.M)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def compare(old: dict, new: dict) -> dict:
    old_sig, new_sig = _signatures(old), _signatures(new)
    added = sorted(set(new_sig) - set(old_sig))
    removed = sorted(set(old_sig) - set(new_sig))
    changed = sorted(k for k in set(old_sig) & set(new_sig) if old_sig[k] != new_sig[k])
    return {"added": added, "removed": removed, "changed": changed, "old_functions": len(old_sig), "new_functions": len(new_sig)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--revision", default="v1")
    ap.add_argument("--generated", required=True, type=Path, help="generated repository directory (with build/)")
    ap.add_argument("--cache", default=os.environ.get("HF_HOME", "/tmp/hf-api-gate"))
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    new_contract_path = next((a.generated / "build").rglob("_contract.py"))
    new = _load_contract(new_contract_path)
    old, sha = _published_contract(a.repo, a.revision, a.cache)
    report = compare(old, new)
    report.update({"repo": a.repo, "revision": a.revision, "published_sha": sha})
    verdict = "PASS" if not report["removed"] and not report["changed"] else "FAIL (needs v2)"
    print(f"{a.repo}@{a.revision} ({sha[:8]}): {report['old_functions']} -> {report['new_functions']} functions; +{len(report['added'])} added, -{len(report['removed'])} removed, {len(report['changed'])} changed -> {verdict}")
    for k in report["removed"][:20]:
        print("  removed:", k)
    for k in report["changed"][:20]:
        print("  changed:", k)
    if a.json:
        a.json.write_text(json.dumps(report, indent=1) + "\n")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
