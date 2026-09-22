#!/usr/bin/env python3
"""Re-open the 20 kernel repositories ONLY if what is on the Hub is the capped build with buried history.
Per repo it verifies, from the Hub itself (not from local files):
  * currently private (containment still in force)
  * exactly ONE commit on v1 and on main (the uncapped revisions are gone)
  * (families) the darwin CPU family library at v1 imports flock and carries the §9 refusal code
  * (umbrella) kernel-depends pins every family to its CURRENT v1 sha
Refuses (exit 1) on any mismatch. Without --apply: dry run. With --apply: flips every repository public and re-checks.
With --check-only: standing health check of an already-public Hub (same checks minus the privacy assertion; never flips).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def token() -> str:
    """HF token: HF_TOKEN or HF_API_KEY from the environment, else HF_API_KEY in the repo .env; a clear error otherwise."""
    for var in ("HF_TOKEN", "HF_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    env = ROOT / ".env"
    if not env.exists():
        raise SystemExit("no HF token: set HF_TOKEN (or HF_API_KEY), or add HF_API_KEY=... to the repository .env")
    m = re.search(r"^HF_API_KEY=(.+)$", env.read_text(), re.M)
    if not m:
        raise SystemExit("no HF token: HF_API_KEY is not set in the repository .env and HF_TOKEN is not in the environment")
    return m.group(1).strip().strip('"').strip("'")

APPLY="--apply" in sys.argv
CHECK_ONLY="--check-only" in sys.argv  # standing health check of an already-PUBLIC hub: same checks minus privacy; never flips
from huggingface_hub import HfApi, constants, hf_hub_download

if "kernel" not in constants.REPO_TYPES: constants.REPO_TYPES.append("kernel")
tok=token(); api=HfApi(token=tok)
fams=json.loads((ROOT/"docs/hf-kernels/release/capabilities.json").read_text())["families"]; repos=[f"thyn-ai/{f}" for f in fams]+["thyn-ai/algenta"]
cache=tempfile.mkdtemp(prefix="reopen-verify-"); problems=[]; v1={}
def bad(r,msg): problems.append(f"{r}: {msg}"); print("  ❌",r,msg)
for r in repos:
    info=api.repo_info(r,repo_type="kernel",revision="v1"); v1[r]=info.sha
    if not info.private and not CHECK_ONLY: bad(r,"is ALREADY public")
    for br in ("v1","main"):
        n=len(list(api.list_repo_commits(r,repo_type="kernel",revision=br)))
        if n!=1: bad(r,f"{br} has {n} commits (history not buried)")
    if r!="thyn-ai/algenta":
        try:
            variants=sorted(t.path for t in api.list_repo_tree(r,repo_type="kernel",revision="v1",path_in_repo="build") if re.search(r"/torch\d+-cpu-aarch64-darwin$",t.path))
        except Exception as ex:  # noqa: BLE001 — any Hub error is a flagged problem, never a crash
            bad(r,f"could not list build/ on v1: {type(ex).__name__}"); continue
        if not variants: bad(r,"no *-cpu-aarch64-darwin variant on v1 (this check inspects the darwin CPU library)"); continue
        variant=variants[-1]  # newest torch tag
        try:
            tree=[t.path for t in api.list_repo_tree(r,repo_type="kernel",revision="v1",path_in_repo=variant,recursive=True)]
        except Exception as ex:  # noqa: BLE001
            bad(r,f"could not list {variant}: {type(ex).__name__}"); continue
        libs=[t for t in tree if re.search(r"/_native/libalgenta_[a-z0-9_]+\.dylib$",t)]
        if len(libs)!=1: bad(r,f"expected one family dylib in the darwin variant, found {len(libs)}"); continue
        p=hf_hub_download(r,libs[0],repo_type="kernel",revision="v1",token=tok,cache_dir=cache)
        st=subprocess.run(["strings",p],capture_output=True,text=True).stdout; nm=subprocess.run(["nm","-u",p],capture_output=True,text=True).stdout
        if "_flock" not in nm: bad(r,"v1 library does NOT import flock (uncapped build?)")
        if "community_worker_slot_unavailable" not in st: bad(r,"v1 library lacks the §9 refusal code")
        if not problems or all(not x.startswith(r+":") for x in problems): print("  ✅",r,"v1="+info.sha[:8],"1 commit, capped")
# umbrella pins must equal the families' CURRENT (post-squash) v1 shas
mp=hf_hub_download("thyn-ai/algenta","build/torch-universal/metadata.json",repo_type="kernel",revision="v1",token=tok,cache_dir=cache)
deps={d["repo-id"]:d["revision"] for d in json.load(open(mp)).get("kernel-depends",[])}
stale=[f"{k}: pinned {v[:8]} != v1 {v1.get(k,'?')[:8]}" for k,v in deps.items() if v1.get(k)!=v]
missing=[k for k in repos if k!="thyn-ai/algenta" and k not in deps]
if stale or missing: bad("thyn-ai/algenta", f"umbrella pins stale/missing: {stale[:3]} {missing[:3]}")
else: print("  ✅ thyn-ai/algenta umbrella pins all 19 families at their current v1 shas")
if problems: print(f"\nREFUSING to re-open: {len(problems)} problem(s)"); sys.exit(1)
print(f"\nAll {len(repos)} repositories verified: {'' if CHECK_ONLY else 'private, '}single capped commit on v1/main, umbrella pins current.")
if CHECK_ONLY: sys.exit(0)
if not APPLY: print("(dry run — pass --apply to flip public)"); sys.exit(0)
print("\n=== RE-OPENING (owner instruction: fix, test, then open again) ===")
for r in repos:
    api.update_repo_settings(repo_id=r, private=False, repo_type="kernel"); print("  public:", r, "private=", api.repo_info(r,repo_type="kernel").private)
print("DONE: 20 repositories public.")
