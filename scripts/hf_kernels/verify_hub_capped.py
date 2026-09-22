#!/usr/bin/env python3
"""Post-republish verification, as a Hub consumer: what is ON THE HUB is capped and history is buried.
  1. fresh HF_HOME; get_kernel(thyn-ai/algenta-stats v1 cpu) -> call fit_normal -> correct result
  2. run the §9 gate against the CACHED Hub library (not a local build)
  3. cached library imports flock, carries anchor + refusal code, has no getenv
  4. every one of the 20 repos has exactly ONE commit on v1 and on main (uncapped history gone)
Usage: verify_hub_capped.py [--anon] [--repo thyn-ai/algenta-stats --module distribution_fit --function fit_normal]
  --anon: no token at all, like any internet user (repositories must be public). Prints the §9 gate's per-scenario
  numbers so an evidence record can quote them."""

import argparse
import glob
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_gate(library: str, request_file: str) -> subprocess.CompletedProcess:
    """Run the §9 red-team gate on one library: list-form argv, no shell. The caller validates `library` first."""
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/hf_kernels/community_cap_redteam.py"),
            library,
            request_file,
        ],
        capture_output=True,
        text=True,
    )


def token() -> str:
    """HF token: HF_TOKEN or HF_API_KEY from the environment, else HF_API_KEY in the repo .env; a clear error otherwise."""
    for var in ("HF_TOKEN", "HF_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    env = ROOT / ".env"
    if not env.exists():
        raise SystemExit(
            "no HF token: set HF_TOKEN (or HF_API_KEY), or add HF_API_KEY=... to the repository .env"
        )
    m = re.search(r"^HF_API_KEY=(.+)$", env.read_text(), re.M)
    if not m:
        raise SystemExit(
            "no HF token: HF_API_KEY is not set in the repository .env and HF_TOKEN is not in the environment"
        )
    return m.group(1).strip().strip('"').strip("'")


ap = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
ap.add_argument(
    "--anon",
    action="store_true",
    help="no token at all — behave like any internet user (repositories must be public)",
)
ap.add_argument("--repo", default="thyn-ai/algenta-stats", help="family repository to load")
ap.add_argument("--module", default="distribution_fit")
ap.add_argument(
    "--function", default="fit_normal", help="module.function to call on 20k seeded uniforms"
)
A = ap.parse_args()
ANON = A.anon
os.environ["HF_HOME"] = tempfile.mkdtemp(prefix="hf-verify-")
if ANON:
    for k in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        os.environ.pop(k, None)
else:
    os.environ["HF_TOKEN"] = token()
from huggingface_hub import HfApi, constants  # noqa: E402 — HF_HOME must be set before this import

if "kernel" not in constants.REPO_TYPES:
    constants.REPO_TYPES.append("kernel")
api = HfApi(token=False if ANON else os.environ["HF_TOKEN"])
ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"{'✅' if cond else '❌'} {name} {detail}")


from kernels import get_kernel  # noqa: E402 — HF_HOME must be set before this import

k = get_kernel(A.repo, version=1, backend="cpu", trust_remote_code=[A.repo])

random.seed(1)
xs = [random.random() for _ in range(20000)]
r = getattr(getattr(k, A.module), A.function)(xs)
if (A.module, A.function) == ("distribution_fit", "fit_normal"):
    check(
        "get_kernel + fit_normal on 20k uniforms",
        abs(r[0] - 0.5) < 0.01 and abs(r[1] - 0.2887) < 0.01,
        f"mean={r[0]:.4f} std={r[1]:.4f}",
    )
else:
    check(f"get_kernel + {A.module}.{A.function} returns", r is not None, str(r)[:60])
d = os.path.dirname(
    os.path.abspath(k.__file__)
)  # the variant root; search it recursively (layout-agnostic)
libs = sorted(glob.glob(os.path.join(d, "**", "_native", "libalgenta_*"), recursive=True))
print("kernel __file__:", k.__file__)
assert libs, f"no native library under {d}"
lib = libs[0]
print("cached Hub library:", lib)
nm = subprocess.run(["nm", "-u", lib], capture_output=True, text=True).stdout
st = subprocess.run(["strings", lib], capture_output=True, text=True).stdout
check("cached lib imports flock", "_flock" in nm or "flock" in nm)
check("cached lib carries the §9 refusal code", "community_worker_slot_unavailable" in st)
# NOTE: the '/dev/null' anchor literal is NOT a valid strings-check: in the final build the compiler inlines the
# 9-byte StaticString constant (split immediates), so `strings` never shows it although the lock is in use —
# gate scenario (h) ("user cannot delete the lock anchor") is the behavioural proof and runs below.
print(
    "   (anchor literal via strings: %s — informational only, see note)"
    % ("present" if "/dev/null" in st else "not visible")
)
check("cached lib has NO getenv", "getenv" not in nm)
req = os.path.join(tempfile.mkdtemp(prefix="hf-verify-req-"), "heavy_req.json")
# `lib` derives from --repo, so treat it as untrusted before it reaches a subprocess: it must be a regular file
# whose symlink and target both live inside the fresh HF_HOME this run created, with a family-library name.
# The SYMLINK path is passed (not its blob target): the gate preloads the runtime closure from the manifest
# that sits beside the symlink.
cache_root = os.path.realpath(os.environ["HF_HOME"]) + os.sep
# resolve BOTH sides: macOS aliases /tmp and /var to /private/...; the symlink's parent dir and its blob target
# must both resolve inside the cache root, and the symlink's own name must be a family library
_sym_dir_real = os.path.realpath(os.path.dirname(lib))
_target_real = os.path.realpath(lib)
if not (
    os.path.isfile(lib)
    and _sym_dir_real.startswith(cache_root)
    and _target_real.startswith(cache_root)
    and re.fullmatch(r"libalgenta_[a-z0-9_]+\.(dylib|so)", os.path.basename(lib))
):
    raise SystemExit(
        f"refusing to run the gate on an unexpected library path: {lib}"
    )  # not an assert: survives python -O
g = _run_gate(lib, req)
# print the gate's per-scenario lines, not only its verdict: an evidence record needs the numbers
for line in (g.stdout or "").splitlines():
    if line.startswith("(") or "VERDICT" in line or line.startswith("warm single"):
        print("   " + line)
if g.returncode != 0 and g.stderr.strip():
    print(g.stderr.strip()[-600:])
check("§9 gate on the CACHED Hub library", g.returncode == 0)
repos = ["thyn-ai/algenta"] + [
    f"thyn-ai/{f}"
    for f in json.loads((ROOT / "docs/hf-kernels/release/capabilities.json").read_text())[
        "families"
    ]
]
multi = []
for rp in repos:
    for br in ("v1", "main"):
        n = len(list(api.list_repo_commits(rp, repo_type="kernel", revision=br)))
        if n != 1:
            multi.append(f"{rp}@{br}={n}")
check(
    f"history buried: 1 commit on v1 and main for all {len(repos)} repos",
    not multi,
    ", ".join(multi[:6]),
)
print("\n=== HUB VERIFICATION:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
