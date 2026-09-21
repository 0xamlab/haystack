#!/usr/bin/env python3
"""Publish a generated kernel repository directory to the Hub as a `kernel`-type repo.

`kernel-builder upload` is the first-party path; it needs Nix, which this host does not have.
This helper uses huggingface_hub directly. huggingface_hub 1.26 recognises the `kernel` repo type
in create_repo/delete_repo/repo_info but its upload helpers still validate against the model/
dataset/space list, so the type is registered before use (the URL prefix `kernels/` is already
known to the library). Uploads go to branch `v<version>` (created from main on first publish) and
to `main`; stale files on the branch are removed so a variant that disappeared cannot linger.

Usage: publish_hub.py --repo thyn-ai/algenta-stats --dir hub/algenta-stats [--version 1] [--dry-run]
Token: HF_TOKEN env, or HF_API_KEY, or the repo .env.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from huggingface_hub import HfApi, constants

for name in ("REPO_TYPES",):
    lst = getattr(constants, name)
    if "kernel" not in lst:
        lst.append("kernel")


def token() -> str:
    for var in ("HF_TOKEN", "HF_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.is_file():
        m = re.search(r"^HF_API_KEY=(.+)$", env.read_text(), re.M)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("no HF token (HF_TOKEN / HF_API_KEY / .env)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--message", default=None)
    a = ap.parse_args()
    variants = sorted(p.name for p in (a.dir / "build").iterdir() if p.is_dir())
    size = sum(p.stat().st_size for p in a.dir.rglob("*") if p.is_file())
    print(f"{a.repo}: {len(variants)} variants, {size/1e6:.1f} MB from {a.dir}")
    if a.dry_run:
        print("\n".join(variants)); return 0
    api = HfApi(token=token())
    url = api.create_repo(a.repo, repo_type="kernel", exist_ok=True, private=False)
    print("repo:", url)
    branch = f"v{a.version}"
    refs = api.list_repo_refs(a.repo, repo_type="kernel")
    if branch not in {b.name for b in refs.branches}:
        api.create_branch(a.repo, repo_type="kernel", branch=branch, exist_ok=True)
        print("created branch", branch)
    msg = a.message or f"{a.repo} v{a.version}: {len(variants)} build variants"
    for revision in (branch, "main"):
        info = api.upload_folder(folder_path=str(a.dir), repo_id=a.repo, repo_type="kernel", revision=revision,
                                 commit_message=msg, delete_patterns=["build/**", "README.md", "LICENSE", ".gitattributes"],
                                 ignore_patterns=["**/__pycache__/**", "**/*.pyc"])
        print(f"uploaded to {revision}: {getattr(info, 'commit_url', info)}")
    print(json.dumps({"repo": a.repo, "branch": branch, "variants": variants}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
