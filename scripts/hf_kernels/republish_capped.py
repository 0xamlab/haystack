#!/usr/bin/env python3
"""Republish every family + the umbrella from the CAPPED builds, then bury the uncapped history.

Per family (19 published; algenta-host-interop stays withheld):
  generate package (all platform natives) -> family_smoke on the host-loadable variant
  -> ABI §9 gate on algenta-stats -> publish v1+main -> super_squash_history(v1) + (main)
  -> read the NEW v1 sha (squash rewrites it) for the umbrella pins.
Then the umbrella (pinned to the post-squash v1 shas) -> publish -> squash. Repos stay PRIVATE.

  republish_capped.py --mac <mac dir> --linux <linux dir> --hub-out <dir> [--dry-run] [--skip-cuda] [--families F ...] [--open]

Expected artifact layout (what build_hf_kernel_family.py / linux_container_build.sh produce):
  <mac>/<family>/_native/                       macOS CPU build per family     (build_hf_kernel_family.py --out <mac>/<family>)
  <mac>/algenta-llm-metal/_native/              Metal build of algenta-llm      (--backend metal)
  <linux>/arm64/<family>_cpu/_native/           Linux aarch64 CPU per family   (linux_container_build.sh --arch arm64 --out <linux>/arm64)
  <linux>/amd64/<family>_cpu/_native/           Linux x86-64 CPU per family    (--arch amd64 --out <linux>/amd64)
  <linux>/cuda-<sm>/algenta-llm_cuda/_native/   one CUDA build per target       (--backend cuda --cuda-targets <sm> --out <linux>/cuda-<sm>)
Scratch (CUDA merge, umbrella, API-gate cache, report) goes to <hub-out>_work/; <hub-out>/ holds exactly one
generated repository per family, which is what release_record.py --hub-dir expects. Every step is gated on the
previous one's actual output; --dry-run stops before any upload. Needs the pinned `kernels` loader installed.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from huggingface_hub import HfApi, constants

if "kernel" not in constants.REPO_TYPES: constants.REPO_TYPES.append("kernel")

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


def run(*cmd, check: bool = True, **kw):
    """Run a repository tool: list-form argv, no shell, cwd=ROOT. With check=False the CompletedProcess is
    returned for the caller to judge; otherwise a non-zero exit prints the output tail and raises."""
    print("  $", " ".join(str(c) for c in cmd)[:220], flush=True)
    r=subprocess.run([str(c) for c in cmd], cwd=ROOT, text=True, capture_output=True, **kw)
    if not check:
        return r
    if r.returncode!=0:
        print("  !! exit", r.returncode, "\n"+"\n".join((r.stdout+r.stderr).strip().splitlines()[-12:]), flush=True)
        raise subprocess.CalledProcessError(r.returncode, cmd, r.stdout, r.stderr)
    return r


def families() -> list[str]:
    """The published families: `families` in the release capability manifest (not the release record,
    which this script regenerates)."""
    return list(json.loads((ROOT / "docs/hf-kernels/release/capabilities.json").read_text())["families"])

def merge_cuda(target_dirs, out):
    """Four single-target builds -> one _native dir: union of files, cuda_targets and cuda_libraries.
    Shared closure files are byte-identical across targets (same toolchain); assert that."""
    out.mkdir(parents=True, exist_ok=True); merged=None; hashes={}
    for d in target_dirs:
        m=json.loads((d/"manifest.json").read_text())
        if merged is None:
            merged=dict(m); merged["cuda_targets"]=[]; merged["cuda_libraries"]={}; merged["files"]={}; merged["load_order"]=list(m.get("load_order",[]))
        for f,meta in m["files"].items():
            if f in merged["files"] and merged["files"][f]!=meta: raise SystemExit(f"cuda merge: {f} differs between targets")
            merged["files"][f]=meta
            if not (out/f).exists(): shutil.copy2(d/f, out/f)
        merged["cuda_targets"]+= [t for t in m.get("cuda_targets",[]) if t not in merged["cuda_targets"]]
        merged["cuda_libraries"].update(m.get("cuda_libraries",{}))
        for lo in m.get("load_order",[]):
            if lo not in merged["load_order"]: merged["load_order"].append(lo)
    # the build script's convention: the primary `library` is the NEWEST target (loader picks by device cc)
    newest=max(merged["cuda_targets"], key=lambda t:int(t.split("_")[1])); merged["library"]=merged["cuda_libraries"][newest]
    (out/"manifest.json").write_text(json.dumps(merged,indent=2)); return merged

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mac",type=Path,required=True); ap.add_argument("--linux",type=Path,required=True)
    ap.add_argument("--hub-out",type=Path,required=True); ap.add_argument("--skip-cuda",action="store_true"); ap.add_argument("--dry-run",action="store_true")
    ap.add_argument("--open",action="store_true",help="after EVERY family + umbrella is published and squashed, flip all repos public (owner instruction)")
    ap.add_argument("--families",nargs="*",help="subset of families to process (default: every published family)")
    ap.add_argument("--cuda-targets",nargs="*",default=["sm_75","sm_80","sm_89","sm_90"],help="per-target CUDA builds expected under <linux>/cuda-<target>/algenta-llm_cuda/_native")
    a=ap.parse_args()
    tok=token(); os.environ["HF_TOKEN"]=tok; api=HfApi(token=tok); fams=[f for f in families() if not a.families or f in a.families]; print("families:",len(fams)); a.hub_out.mkdir(parents=True,exist_ok=True)
    work=a.hub_out.parent/(a.hub_out.name+"_work"); work.mkdir(parents=True,exist_ok=True)  # scratch: keep hub-dir = one repo per family
    pins={}; report=[]
    cuda_dir=None
    if not a.skip_cuda:
        tds=[a.linux/f"cuda-{t}"/"algenta-llm_cuda"/"_native" for t in a.cuda_targets]
        tds=[d for d in tds if (d/"manifest.json").exists()]
        if len(tds)==len(a.cuda_targets): cuda_dir=work/"cuda_merged"; m=merge_cuda(tds,cuda_dir); print("cuda merged:",m["cuda_targets"],list(m["cuda_libraries"]))
        else: print(f"WARN only {len(tds)}/{len(a.cuda_targets)} cuda targets built -> llm ships without cuda this round")
    for fam in fams:
        natives=[("cpu",a.mac/fam/"_native"),("cpu",a.linux/"arm64"/f"{fam}_cpu"/"_native"),("cpu",a.linux/"amd64"/f"{fam}_cpu"/"_native")]
        if fam=="algenta-llm":
            natives.append(("metal",a.mac/"algenta-llm-metal"/"_native"))
            if cuda_dir: natives.append(("cuda",cuda_dir))
        missing=[str(p) for _,p in natives if not (p/"manifest.json").exists()]
        if missing: report.append((fam,"MISSING natives: "+", ".join(missing))); print("SKIP",fam,missing); continue
        out=a.hub_out/fam; shutil.rmtree(out,ignore_errors=True)
        run(sys.executable,"scripts/generate_hf_kernel_package.py","--family",fam,*sum([["--native",f"{b}={p}"] for b,p in natives],[]),"--out",out)
        repo=f"thyn-ai/{fam}"; step="smoke"
        try:
          darwin=sorted(out.glob("build/*-cpu-aarch64-darwin"))[-1]
          run(sys.executable,"scripts/hf_kernels/family_smoke.py","--variant",darwin)
          if fam=="algenta-stats":
            step="§9 gate"; lib=next(darwin.glob("*/_native/libalgenta_algenta_stats*.dylib"))
            run(sys.executable,"scripts/hf_kernels/community_cap_redteam.py",lib,work/"heavy_req.json")
        except (subprocess.CalledProcessError, StopIteration, IndexError) as e:
          # run() already printed the tail of the failing tool's output; record it and keep going so the
          # report covers every family and the --open guard sees the failure instead of a crash.
          report.append((fam,f"{step} FAILED"+(f" rc={e.returncode}" if isinstance(e,subprocess.CalledProcessError) else f" ({type(e).__name__})"))); print("SKIP",fam,step,"failed"); continue
        # Stage 5 versioning gate: the v1 API may only GROW. Compare against the currently published v1
        # before we overwrite it (repos are private: token via env; own cache so the fresh-cache tests stay clean).
        # The gate takes its cache directory as an argument, so no env= is built from os.environ; the child inherits
        # the parent's environment (incl. HF_TOKEN). `out`/`work` derive from --hub-out and `repo` from the
        # capability manifest, so validate them before the call; run() is list-form argv, no shell, cwd=ROOT.
        if not (re.fullmatch(r"thyn-ai/algenta-[a-z0-9-]+", repo) and out.is_dir() and out.resolve().is_relative_to(a.hub_out.resolve())
                and work.resolve().parent==a.hub_out.resolve().parent):
            report.append((fam,f"gate-input FAILED: unexpected inputs {repo} {out} {work}")); print("SKIP",fam,"gate-input check failed"); continue  # record, never abort the run
        g=run(sys.executable,"scripts/hf_kernels/api_manifest_gate.py","--repo",repo,"--revision","v1","--generated",out,"--json",work/f"{fam}.api.json","--cache",work/"api-gate-cache", check=False)
        gl=(g.stdout+g.stderr).strip().splitlines(); print("  api-gate:", gl[-1][:140] if gl else f"rc={g.returncode}")
        if g.returncode!=0: report.append((fam,"API GATE FAILED: "+(gl[-1][:160] if gl else "?"))); print("SKIP",fam,"api gate"); continue
        if a.dry_run: report.append((fam,"dry-run ok (api gate passed)")); continue
        try:
          step="publish"; run(sys.executable,"scripts/hf_kernels/publish_hub.py","--repo",repo,"--dir",out,"--version","1","--message","capped rebuild: ABI §9 device-wide worker cap")
          step="squash"
          for br in ("v1","main"):
              api.super_squash_history(repo, branch=br, repo_type="kernel", commit_message=f"{br}: capped build (ABI §9); prior uncapped revisions removed")
        except Exception as e:  # noqa: BLE001 — every failure must land in the report, never abort the run
          report.append((fam,f"{step} FAILED: {type(e).__name__}: {str(e)[:120]}")); print("FAIL",fam,step,type(e).__name__); continue
        sha=api.repo_info(repo,repo_type="kernel",revision="v1").sha; pins[repo]=sha
        n=len(list(api.list_repo_commits(repo,repo_type="kernel",revision="v1"))); report.append((fam,f"published+squashed v1={sha[:8]} commits_on_v1={n}"))
    if not a.dry_run and len(pins)==len(fams) and not a.families:  # umbrella only on a full run: it pins EVERY family
        uo=work/"algenta"; shutil.rmtree(uo,ignore_errors=True)  # OUTSIDE hub-out: release_record.py scans every hub-dir subdir with build/ as a family
        run(sys.executable,"scripts/hf_kernels/generate_umbrella.py","--out",uo,*sum([["--pin",f"{r}={s}"] for r,s in pins.items()],[]))
        run(sys.executable,"scripts/hf_kernels/publish_hub.py","--repo","thyn-ai/algenta","--dir",uo,"--version","1","--message","umbrella: pins re-pointed at the capped v1 heads")
        for br in ("v1","main"): api.super_squash_history("thyn-ai/algenta",branch=br,repo_type="kernel",commit_message=f"{br}: umbrella for the capped release")
        report.append(("algenta (umbrella)",f"published+squashed v1={api.repo_info('thyn-ai/algenta',repo_type='kernel',revision='v1').sha[:8]}"))
        # Stage 5 immutable release record: bind source/contract/toolchain to the POST-squash v1/main revisions.
        run(sys.executable,"scripts/hf_kernels/release_record.py","--hub-dir",a.hub_out,"--umbrella",uo,"--out",ROOT/"docs/hf-kernels/release/record.json")
        report.append(("release record","regenerated docs/hf-kernels/release/record.json (commit it with the evidence update)"))
    print("\n=== REPUBLISH REPORT ==="); [print(f"{f:<28} {s}") for f,s in report]
    json.dump({"pins":pins,"report":report},open(work/"republish_report.json","w"),indent=2)
    bad=[r for r in report if "FAILED" in r[1] or "MISSING" in r[1]]  # every failure entry carries one of these markers; informational entries (release record) do not
    if a.open and not a.dry_run:
        if bad or len(pins)!=len(fams) or not any("umbrella" in r[0] for r in report):
            print("REFUSING --open: not every family + umbrella was published and squashed"); sys.exit(1)
        print("\n=== RE-OPEN: flipping 20 repos public (owner instruction; capped build, history squashed) ===")
        for r in list(pins)+["thyn-ai/algenta"]:
            api.update_repo_settings(repo_id=r, private=False, repo_type="kernel"); print("  public:", r, "private=", api.repo_info(r,repo_type="kernel").private)
    sys.exit(1 if bad else 0)
if __name__=="__main__": main()
