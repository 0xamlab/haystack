#!/usr/bin/env python3
"""Generate the umbrella kernel repository `thyn-ai/algenta`: one `get_kernel` that brings every
published family in, pinned to exact Hub revisions.

The umbrella is a torch-universal, pure-Python kernel whose `metadata.json` lists each family in
`kernel-depends` with a `revision` (an immutable commit), so an umbrella release can never acquire
a mixed set of family builds (plan v3, Stage 5). Its `__init__.py` fetches the dependencies through
`kernels.deps.get_kernel_dep`, the loader's own dependency channel, and exposes them as attributes
(`algenta.stats`, `algenta.llm`, ...). The loader resolves each family's own variant for the host.

    scripts/hf_kernels/generate_umbrella.py --out hub/algenta --pin thyn-ai/algenta-stats=<sha> --pin thyn-ai/algenta-llm=<sha> ...
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILTERS = json.loads((ROOT / "scripts" / "hf_kernel_filters.json").read_text())["filters"]


def digest_dir(variant_dir: Path) -> dict:
    files = {}
    for p in sorted(variant_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(variant_dir).as_posix()
        if rel in ("metadata.json", "metadata.json.sigstore") or "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        files[rel] = base64.b64encode(hashlib.sha256(p.read_bytes()).digest()).decode()
    return {"algorithm": "sha256", "files": files}


def attribute_name(repo_id: str) -> str:
    return repo_id.split("/")[-1].replace("algenta-", "").replace("-", "_")


def render_init(pins: dict[str, str]) -> str:
    lines = ['"""algenta — every published Algenta kernel family, pinned to exact Hub revisions."""',
             "from kernels.deps import get_kernel_dep", ""]
    names = []
    for repo in pins:
        name = attribute_name(repo)
        lines.append(f"{name} = get_kernel_dep({repo!r})")
        names.append(name)
    lines += ["", f"families = {dict((attribute_name(r), r) for r in pins)!r}", f"revisions = {pins!r}", "", f"__all__ = {sorted(names) + ['families', 'revisions']!r}", ""]
    return "\n".join(lines)


def render_card(pins: dict[str, str], commit: str) -> str:
    rows = []
    for repo, rev in pins.items():
        fam = repo.split("/")[-1]
        spec = FILTERS.get(fam, {})
        rows.append(f"| `{repo}` | `algenta.{attribute_name(repo)}` | {spec.get('summary', '')} | {' · '.join(b.upper() if b == 'cpu' else b.capitalize() for b in spec.get('backends', ['cpu']))} | `{rev[:8]}` |")
    trust = ", ".join(f'"{r}"' for r in ["thyn-ai/algenta", *pins])
    return f"""---
library_name: kernels
license: other
license_name: algenta-community-license-1.0
license_link: LICENSE
tags:
- algenta
- mojo
---

# algenta

Every published Algenta kernel family in one load, each pinned to an exact revision. Compiled
Mojo, loaded in-process.

## Get started

```bash
pip install kernels torch
```

```python
from kernels import get_kernel

algenta = get_kernel(
    "thyn-ai/algenta",
    version=1,
    trust_remote_code=[{trust}],
)
algenta.stats.ab_testing.z_test_proportions(50, 1000, 65, 1000)
```

`trust_remote_code` has to name every repository in the tree: the umbrella and each family it
brings in. The loader picks each family's build for your machine (CPU everywhere, Metal on
macOS 26, CUDA on NVIDIA hosts with a CUDA build of PyTorch); pass `backend="cpu"` to stay on the
CPU.

## Families

| Repository | Attribute | What's inside | Backends | Pinned revision |
|---|---|---|---|---|
{chr(10).join(rows)}

An umbrella release moves only when every family it pins has been re-verified together; loading
`thyn-ai/algenta` at a given revision therefore always yields the same set of family builds.

## License

Algenta Community License 1.0 (`LICENSE`). Free for personal, research and open-source use, and
for internal use at organizations with fewer than 50 employees and under $5M in annual revenue.
Beyond that, a commercial license is required: https://algenta.ai/pricing.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--pin", action="append", required=True, help="<repo-id>=<40-hex revision>")
    ap.add_argument("--kernel-version", type=int, default=1)
    a = ap.parse_args()
    pins: dict[str, str] = {}
    for spec in a.pin:
        repo, _, rev = spec.partition("=")
        if len(rev) != 40 or any(c not in "0123456789abcdef" for c in rev):
            raise SystemExit(f"{repo}: the pin must be a full 40-hex commit, got {rev!r}")
        pins[repo] = rev
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = a.out
    if (out / "build").exists():
        shutil.rmtree(out / "build")
    vdir = out / "build" / "torch-universal"
    pkg = vdir / "algenta"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(render_init(pins))
    (vdir / "__init__.py").write_text('"""algenta (torch-universal)."""\nfrom .algenta import *  # noqa: F401,F403\nfrom .algenta import __all__  # noqa: F401\n')
    metadata = {
        "name": "algenta",
        "id": f"_algenta_umbrella_{commit[:7]}",
        "version": a.kernel_version,
        "license": "other",
        "python-depends": [],
        "kernel-depends": [{"repo-id": repo, "revision": rev} for repo, rev in pins.items()],
        "backend": {"type": "cpu"},
    }
    metadata["digest"] = digest_dir(vdir)
    (vdir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (out / "README.md").write_text(render_card(pins, commit))
    shutil.copy2(ROOT / "LICENSE", out / "LICENSE")
    print(f"umbrella: {len(pins)} families pinned -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
