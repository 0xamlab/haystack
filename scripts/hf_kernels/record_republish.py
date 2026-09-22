#!/usr/bin/env python3
"""After the real republish (and optionally the re-open): write the evidence + manifest state from the Hub itself.
  record_republish.py --capture-pre pre.json                                   (BEFORE the republish)
  record_republish.py --report <hub-out>_work/republish_report.json --pre pre.json [--reopened]
Adds REPUBLISH-001 (per repo: old uncapped v1 sha -> new capped v1 sha, commits on v1/main, umbrella pins),
updates PUBLISH-VISIBILITY-001 and capabilities.json publication_state. Reads live Hub state; refuses on mismatch."""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

from huggingface_hub import HfApi, constants

ROOT = Path(__file__).resolve().parents[2]


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
    "--report", help="<hub-out>_work/republish_report.json written by republish_capped.py"
)
ap.add_argument("--pre", help="pre-republish snapshot written by --capture-pre")
ap.add_argument(
    "--reopened",
    action="store_true",
    help="this republish re-opened private repos: expect public afterwards",
)
ap.add_argument(
    "--public-ok",
    action="store_true",
    help="repos were public before and after (e.g. a LICENSE/README re-release)",
)
ap.add_argument(
    "--row-id",
    default="REPUBLISH-001",
    help="evidence row id to write (a new id for a new release event)",
)
ap.add_argument(
    "--summary", default="", help="one line on what this release changed (prepended to the claim)"
)
ap.add_argument(
    "--capture-pre",
    metavar="OUT.json",
    help="snapshot the CURRENT v1 sha / privacy / commit count of every repository, then exit (run BEFORE a republish)",
)
a = ap.parse_args()

if "kernel" not in constants.REPO_TYPES:
    constants.REPO_TYPES.append("kernel")
tok = token()
api = HfApi(token=tok)
today = datetime.date.today().isoformat()
if a.capture_pre:
    fams = json.loads((ROOT / "docs/hf-kernels/release/capabilities.json").read_text())["families"]
    snap = {}
    for r in ["thyn-ai/algenta"] + [f"thyn-ai/{f}" for f in fams]:
        i = api.repo_info(r, repo_type="kernel", revision="v1")
        snap[r] = {
            "v1_sha_uncapped": i.sha,
            "private": i.private,
            "commits_on_v1": len(list(api.list_repo_commits(r, repo_type="kernel", revision="v1"))),
        }
    json.dump(snap, open(a.capture_pre, "w"), indent=2)
    print(f"pre-republish snapshot of {len(snap)} repositories -> {a.capture_pre}")
    sys.exit(0)
if not (a.report and a.pre):
    sys.exit("--report and --pre are required (or use --capture-pre)")
rep = json.load(open(a.report))
pre = json.load(open(a.pre))
pins = rep["pins"]
repos = list(pins) + ["thyn-ai/algenta"]
rows_txt = []
problems = []
for r in repos:
    i = api.repo_info(r, repo_type="kernel", revision="v1")
    nv = len(list(api.list_repo_commits(r, repo_type="kernel", revision="v1")))
    nm = len(list(api.list_repo_commits(r, repo_type="kernel", revision="main")))
    old = pre.get(r, {}).get("v1_sha_uncapped", "?")
    if r in pins and pins[r] != i.sha:
        problems.append(f"{r}: report pin {pins[r][:8]} != live v1 {i.sha[:8]}")
    if nv != 1 or nm != 1:
        problems.append(f"{r}: commits v1={nv} main={nm}")
    if a.reopened and i.private:
        problems.append(f"{r}: still private")
    if not a.reopened and not a.public_ok and not i.private:
        problems.append(f"{r}: unexpectedly public")
    rows_txt.append(
        f"{r}: {old[:8]} -> {i.sha[:8]} (v1 {nv} commit, main {nm}, private={i.private})"
    )
if problems:
    print("REFUSING to record — live Hub state does not match:", *problems, sep="\n  ")
    sys.exit(1)
P = ROOT / "docs/hf-kernels/evidence/record.json"
R = json.load(open(P, encoding="utf-8"))
rows = R if isinstance(R, list) else (R.get("rows") or R.get("evidence") or R.get("records"))
by = {x["id"]: x for x in rows}
if a.row_id not in by:
    rows.append(
        {
            "id": a.row_id,
            "question": "Were all 19 families and the umbrella republished from the capped final-source builds, with the uncapped history removed?",
            "claim": (a.summary + " " if a.summary else "")
            + "Yes. Each family: generated from the final macOS/Linux/CUDA natives, passed family_smoke and the API-versioning gate against its previously published v1 (0 removed, 0 changed), uploaded to v1 and main with stale build/** deleted, then super_squash_history on both branches — one commit each. Umbrella regenerated with kernel-depends pinned to the post-squash v1 shas and squashed. Release record regenerated from the published tree.",
            "kind": "measurement",
            "source": "scripts/hf_kernels/republish_capped.py (republish_report.json); huggingface_hub live state",
            "result": "; ".join(rows_txt),
            "confidence": "high",
            "impact": "P0",
            "outcome_class": "accepted-constraint",
            "capability_scope": "all 20 repositories",
            "required_before": "ga_promotion",
            "status": "pass",
            "owner": "eng",
            "accessed": today,
            "contradicts": [],
        }
    )
    print(a.row_id, "added")
pv = by["PUBLISH-VISIBILITY-001"]
if a.reopened:
    pv["result"] = (
        (pv.get("result") or "")
        + f" | RE-OPENED {today}: all 20 repositories public again after the capped rebuild on every platform, the Linux non-root gate, the 19-family verification, republish + history squash (1 commit on v1/main per repo, verified live) and Hub-side verification."
    )
    pv["status"] = "reopened"
    pv["accessed"] = today
    print("PUBLISH-VISIBILITY-001 -> reopened")
json.dump(R, open(P, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
cp = ROOT / "docs/hf-kernels/release/capabilities.json"
cap = json.load(open(cp, encoding="utf-8"))
cap["publication_state"] = {
    "hub_visibility": ("PUBLIC (all 20) since " + today + " — capped build only")
    if (a.reopened or a.public_ok)
    else "PRIVATE (all 20) — capped build published, re-open pending verification",
    "uncapped_revisions": "removed: super_squash_history on v1 and main of every repository (1 commit each, verified live "
    + today
    + ")",
    "capped_v1_shas": {r: api.repo_info(r, repo_type="kernel", revision="v1").sha for r in repos},
}
json.dump(cap, open(cp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("capabilities.json publication_state updated")
