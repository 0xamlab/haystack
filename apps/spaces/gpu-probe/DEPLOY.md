# Deploying the GPU probe

The probe is not a table in `apps/spaces/spaces.toml` on purpose. The fleet manifest has no
`private` key and requires `api_names`, `tests/spaces/test_manifest.py` asserts the fleet is the
flagship alone with no GPU stage, and a manifest entry would put a paid GPU Space on
`deploy.py --all` and on the `spaces=all` dispatch of `deploy-spaces.yml`, which waits for
`RUNNING` and never pauses. The probe is deployed by hand with the steps below, which mirror
`apps/spaces/tools/deploy.py` (create, one atomic upload, hardware, poll) and add the two steps a
paid probe needs: read the record, then pause.

Needs: `huggingface_hub>=1.26,<2` on CPython 3.12+, and `HF_TOKEN` in the environment with write
access to the `thyn-ai` Spaces (fine-grained; never read from a `.env` file). Run from the
repository root on the commit you want to deploy.

## 1. Create the private Space and upload the folder

```python
import os
import subprocess
from pathlib import Path

from huggingface_hub import HfApi

REPO_ID = "thyn-ai/algenta-gpu-probe"
SOURCE = Path("apps/spaces/gpu-probe")
IGNORE = ["**/__pycache__/**", "*.pyc", "tests/**", "**/tests/**", "*.whl", "*.so", "*.dylib"]

api = HfApi(token=os.environ["HF_TOKEN"])
sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
api.create_repo(REPO_ID, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
info = api.upload_folder(
    folder_path=str(SOURCE),
    repo_id=REPO_ID,
    repo_type="space",
    commit_message=f"deploy {sha}",
    delete_patterns=["**"],
    ignore_patterns=IGNORE,
)
print(info.commit_url, info.oid)
```

The README frontmatter (`sdk: docker`, `hardware: l4x1`) sets the SDK; `delete_patterns`
removes every old file in the same commit.

## 1b. Ship the sm_89 engine (restores lane A on the L4)

The wheel's engine is `sm_90a` and the f32 conformance session; on the L4 lane A refuses it
with `engine_target_mismatch`. The packed-int8 captured-graph driver of the published cells,
`qwen3_p3_graph_cuda`, built for `sm_89` with its runtime closure, restores the lane. It is
proprietary and above the 500 KB commit ceiling, so it never enters git: it is copied into the
Space folder right before the upload and travels with it (`engine/` is git-ignored; the
Dockerfile exposes it at `/home/user/engine` when present).

Build it (about three minutes; an `ubuntu:22.04` linux/amd64 container with the pinned Mojo
toolchain, the recipe of `.github/scripts/build_cuda_engine_linux_amd64.sh` without the CUDA
toolkit and the tensor-core shim, `-D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89`):

```sh
bash "/Volumes/Samsung SSD 990 PRO 4TB Media/algenta-tooling/cuda-engine-sm89/scripts/run_build.sh"
# -> cuda-engine-sm89/out/{qwen3_p3_graph_cuda, lib*.so, manifest.json, engine-build.json}
#    cuda-engine-sm89/BUILD.md records every command, the ELF gate and the sha256 of each file
```

Copy it in, check it, and upload with the closure allowed through (the default `IGNORE`
drops `*.so`, which would strip the engine's libraries):

```python
import hashlib
import json
import shutil
import sys
from pathlib import Path

OUT = Path("/Volumes/Samsung SSD 990 PRO 4TB Media/algenta-tooling/cuda-engine-sm89/out")
ENGINE_DIR = SOURCE / "engine"
shutil.rmtree(ENGINE_DIR, ignore_errors=True)
shutil.copytree(OUT, ENGINE_DIR)
subprocess.run([sys.executable, "scripts/hf_kernels/elf_check.py", str(ENGINE_DIR)], check=True)
manifest = json.loads((ENGINE_DIR / "manifest.json").read_text())
assert manifest["engine"]["cuda_target"] == "sm_89"
for entry in manifest["artifacts"]:
    assert hashlib.sha256((ENGINE_DIR / entry["name"]).read_bytes()).hexdigest() == entry["sha256"]

IGNORE_WITH_ENGINE = ["**/__pycache__/**", "*.pyc", "tests/**", "**/tests/**", "*.whl", "*.dylib"]
info = api.upload_folder(
    folder_path=str(SOURCE),
    repo_id=REPO_ID,
    repo_type="space",
    commit_message=f"deploy {sha} + sm_89 packed-int8 graph engine",
    delete_patterns=["**"],
    ignore_patterns=IGNORE_WITH_ENGINE,
)
api.add_space_variable(REPO_ID, "ALGENTA_CUDA_ENGINE", "/home/user/engine/qwen3_p3_graph_cuda")
```

The libraries (1 to 24 MB each) go through LFS on their own. `ALGENTA_CUDA_ENGINE` is the
resolver's first override (`algenta.serve.engine.CUDA_ENGINE_ENV_VARS`), exactly as `algenta
serve` honours it. The Hub exposes a Space variable to the image build only through a build
argument, so the Dockerfile declares `ARG ALGENTA_CUDA_ENGINE` right before the bake (after the
`/home/user/engine` symlink exists, as the runtime user): the bake then inspects this binary
and its manifest and records the selection, instead of the wheel's engine (run 16 recorded
`sm_90a` with the variable set); a variable naming a file that is not in the upload fails the
build with `engine_selected_missing`. With it set, lane A speaks the driver's protocol (`<checkpoint> --runs 3`:
the gate battery, then gen=64 and gen=256 in one process) and the whole run converts and
races the campaign prompt fixture the driver's oracle is bound to (`PROBE_PROMPT_FIXTURE`
overrides the choice; a mismatch fails the lane closed with `engine_prompt_fixture_mismatch`).
The page then names the engine as "packed-int8 captured-graph, sm_89, built <date> from
<source commit>" from the manifest beside the binary. To go back to the wheel's engine, delete
the variable (`api.delete_space_variable(REPO_ID, "ALGENTA_CUDA_ENGINE")`) and upload without
`engine/`. Setting the variable on a running Space restarts it. The Hub starts the image build at
once, on its own builders (the build itself is not GPU time): `llama-server` is copied from
ggml-org's prebuilt `server-cuda-b10223` image and the converter is a shallow checkout of the
same commit (a minute or two; nothing is compiled — the source build of run 15 was cut off by
the builder after 62 minutes at step 310 of 442), then torch cu128 plus the 1.2 GB
Qwen3-0.6B-Base snapshot and the GGUF conversion (10 to 20 minutes).

## 2. Request the GPU and wait for the new revision

```python
import time

api.request_space_hardware(REPO_ID, "l4x1", sleep_time=900)

deadline = time.monotonic() + 90 * 60
seen_build = False
while True:
    rt = api.get_space_runtime(REPO_ID)
    stage = str(getattr(rt.stage, "value", rt.stage))
    if stage in {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE"}:
        raise SystemExit(f"{REPO_ID} entered {stage}")
    if stage != "RUNNING":
        seen_build = True
    elif seen_build:
        break
    if time.monotonic() > deadline:
        raise SystemExit(f"{REPO_ID} still {stage} after 90 min")
    print(stage, rt.hardware, rt.requested_hardware)
    time.sleep(20)
```

A `RUNNING` seen before any build stage is the previous revision; only `RUNNING` after a build
stage is the new one (the `deploy.py` rule). `sleep_time=900` pauses the Space by itself after
15 minutes without traffic, the backstop if step 4 is forgotten. A Space that was paused before
this deploy needs `api.restart_space(REPO_ID)` after `request_space_hardware`, or it stays paused
(observed 2026-09-22). `t4-small` schedules within a few minutes; `l4x1` stalled for 31 minutes
without hardware on 2026-09-22, so the deadline above allows an hour and a half. The
`deploy_gpu_probe*.py` scripts in `algenta-tooling/scripts` do the same: for the race, change
their `request_space_hardware(REPO, "t4-small", sleep_time=900)` to `"l4x1"` and their output
directory to `gpu-probe-run15`.

## 3. Read the run

The Space is private, so its host answers only with the token:

```sh
H="Authorization: Bearer $HF_TOKEN"
curl -sS -H "$H" https://thyn-ai-algenta-gpu-probe.hf.space/health | python3 -m json.tool | head -60
# poll until "status": "ok" (about 6 to 8 minutes after RUNNING: 30 s conversion, the four lanes,
# the reference) or "status": "error" with the failing phase's code; `race.race[*].code` names a
# lane that could not run
curl -sS -H "$H" https://thyn-ai-algenta-gpu-probe.hf.space/run.json \
  > docs/hf-kernels/evidence/artifacts/gpu-probe-run15-l4x1-qwen3-0p6b-race.json
```

Commit the record next to the earlier ones and add or update the evidence rows
(`GPU-SPACE-DRIVER-001`, `GPU-SPACE-PARITY-001`, `GPU-SPACE-RACE-001` in
`docs/hf-kernels/evidence/record.json`) from its `evidence` block. The Space's container logs
(`api.get_space_runtime` has no log API; use the Space page's Logs tab) carry each stage's
stderr; `llama-server`'s own log is `~/work/llama-server.log` inside the container and its tail
is in the `llama` block.

## 4. Pause

```python
api.pause_space(REPO_ID)
```

Billing stops while paused; the hardware setting is kept. To run the probe again:
`api.restart_space(REPO_ID)` (a restart reruns the probe from boot; the image and its baked
assets are reused, the 4.8 GB conversion is redone because the Space's disk is ephemeral).
To run on another GPU, `request_space_hardware(REPO_ID, "<hardware>", sleep_time=900)` then
`restart_space`: `h100` is where the wheel's `sm_90a` engine loads (see
`docs/spaces/GPU-PROBE.md`); on `t4-small` lane B runs too (the prebuilt image carries PTX for
sm_75), lane A only when the selected engine's target loads there, and the published L4 cell
is not what a T4 measures.

## Cost

`l4x1` was $0.80 per hour on 2026-09-24 (`t4-small` $0.40). A build-to-pause cycle is about 10
minutes of GPU time (the build is not billed as GPU time), about $0.15. Paused, the Space costs
nothing.
