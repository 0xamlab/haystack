# Releasing the kernel repositories

The release mechanics are four scripts in `scripts/hf_kernels/`, each gated on the previous step's actual
output. They produced the evidence rows `CAP-REBUILD-*`, `REPUBLISH-001`, `PUBLISH-VISIBILITY-001` and
`CAP-ANON-001`; run them in this order.

| Step | Command | Proves |
|---|---|---|
| 0 | `build_hf_kernel_family.py` (macOS CPU and `--backend metal`); `linux_container_build.sh --arch arm64` / `--arch amd64`; `--backend cuda --cuda-targets <sm>`, one target per run | the artifacts, all from one source commit (`abi.mojo` unchanged) |
| 1 | `community_cap_redteam.py <lib> <req>` on the stats build of **each platform** (as a non-root user in containers) | the compiled Community worker cap holds (ABI §9): nine scenarios, ≤ 1.0 effective workers |
| 2 | `record_republish.py --capture-pre pre.json` | the "before" state (old `v1` shas, privacy, commit counts) for the audit trail |
| 3 | `republish_capped.py --mac … --linux … --hub-out hub --dry-run` | every family regenerates and passes the crash gate, the API-versioning gate (0 removed / 0 changed) and the §9 gate; CUDA targets merge |
| 4 | `republish_capped.py … --hub-out hub` (no `--dry-run`) | upload to `v1` and `main` with stale `build/**` deleted; history squashed to one commit per branch; umbrella re-pinned; release record regenerated into `docs/hf-kernels/release/record.json` |
| 5 | `verify_hub_capped.py` (authenticated while private; `--anon` once public) | from a **fresh cache**: `get_kernel` returns correct results; the *downloaded* library imports `flock`, carries the refusal code, has no `getenv`, and holds the nine-scenario gate; one commit on `v1`/`main` for every repository |
| 6 | `reopen_verified.py`, then `reopen_verified.py --apply` | re-verifies every repository from the Hub immediately before flipping it public; refuses on any mismatch |
| 7 | `record_republish.py --report hub_work/republish_report.json --pre pre.json --reopened` | writes `REPUBLISH-001`, updates `PUBLISH-VISIBILITY-001` and the manifest's `publication_state` from the **live** Hub state; refuses on mismatch |

Standing health check of the public Hub at any time: `reopen_verified.py --check-only`.

Rules learned the hard way (each recorded in the evidence record):

- Only **wall time against the serialised sum of warm heavy calls** proves a blocking lock; call counts and
  call-window overlap both produce false "bypasses". Never run a lock probe as root in a container, and never
  hardcode a module name in a probe: take it from the heavy request.
- A dry run stops before upload, so read the code path of every step it skips (squash, umbrella, release
  record) before the real run. `release_record.py --hub-dir` treats every subdirectory that has `build/` as a
  family: keep scratch and the umbrella out of `hub/`.
- Container CUDA builds die silently under concurrent host load: run them alone, one target per invocation,
  to a host path Docker actually shares (`/Users` on this machine; `/tmp` mounts empty).
- Never publish a binary whose §9 gate has not held on **that** platform's artifact.
