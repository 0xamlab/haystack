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

The README frontmatter (`sdk: docker`, `hardware: t4-small`) sets the SDK; `delete_patterns`
removes every old file in the same commit. The Hub starts the image build at once, on its own
builders (the build itself is not GPU time): torch cu128 plus the 4.1 GB Qwen3-1.7B snapshot
take about 10 to 20 minutes.

## 2. Request the GPU and wait for the new revision

```python
import time

api.request_space_hardware(REPO_ID, "t4-small", sleep_time=900)

deadline = time.monotonic() + 60 * 60
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
        raise SystemExit(f"{REPO_ID} still {stage} after 60 min")
    print(stage, rt.hardware, rt.requested_hardware)
    time.sleep(20)
```

A `RUNNING` seen before any build stage is the previous revision; only `RUNNING` after a build
stage is the new one (the `deploy.py` rule). `sleep_time=900` pauses the Space by itself after
15 minutes without traffic, the backstop if step 4 is forgotten. A Space that was paused before
this deploy needs `api.restart_space(REPO_ID)` after `request_space_hardware`, or it stays paused
(observed 2026-09-22). `t4-small` schedules within a few minutes; `l4x1` stalled for 31 minutes
without hardware on 2026-09-22.

## 3. Read the run

The Space is private, so its host answers only with the token:

```sh
H="Authorization: Bearer $HF_TOKEN"
curl -sS -H "$H" https://thyn-ai-algenta-gpu-probe.hf.space/health | python3 -m json.tool | head -40
# poll until "status": "ok" (about 3 to 4 minutes after RUNNING: 82 s conversion, 42 s session
# open, 20 s reference) or "status": "error" with the failing phase's code
curl -sS -H "$H" https://thyn-ai-algenta-gpu-probe.hf.space/run.json \
  > docs/hf-kernels/evidence/artifacts/gpu-probe-run13-t4-small-qwen3-1p7b.json
```

Commit the record next to run 12's and add or update the evidence rows
(`GPU-SPACE-DRIVER-001`, `GPU-SPACE-PARITY-001` in `docs/hf-kernels/evidence/record.json`) from
its `evidence` block. The Space's container logs (`api.get_space_runtime` has no log API; use the
Space page's Logs tab) carry each stage's stderr.

## 4. Pause

```python
api.pause_space(REPO_ID)
```

Billing stops while paused; the hardware setting is kept. To run the probe again:
`api.restart_space(REPO_ID)` (a restart reruns the probe from boot; the image and its baked
assets are reused, the 13.8 GB conversion is redone because the Space's disk is ephemeral).
To change the hardware for a run on another GPU (`l4x1`, sm_89, which run 12 did not
re-verify), `request_space_hardware(REPO_ID, "l4x1", sleep_time=900)` then `restart_space`.

## Cost

`t4-small` was $0.60 per hour on 2026-09-22. A build-to-pause cycle is about 10 minutes of
GPU time (the build is not billed as GPU time); run 12 billed about 2.7 minutes. Paused, the
Space costs nothing.
