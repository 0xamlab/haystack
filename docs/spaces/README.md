# Spaces fleet runbook

Operating notes for the `thyn-ai` Spaces: three live Spaces (`algenta` and `governed-agent`
on the Docker SDK, `speed-arena` on the Gradio SDK until its Dockerfile lands in M2) and
three static redirects, all described by one manifest, `apps/spaces/spaces.toml`.
Everything below is a command you can run from the repository root today.

## Layout

| Path | Purpose |
|---|---|
| `apps/spaces/spaces.toml` | Fleet manifest: repo id, SDK, source dir, Python, hardware, sleep policy, `shared_shell`, secret names, variables, verify entry, expected `api_names`. |
| `apps/spaces/_shared/algenta_spaces/` | Shared package (shell, design tokens, cards, bench, boot, facts). Vendored into each Space at stage time, never hand-copied. |
| `apps/spaces/{algenta,speed-arena,governed-agent}/` | The live Spaces. |
| `apps/spaces/_redirects/*/` | Static redirect stubs for the retired Spaces (`README.md`, `index.html`, `style.css`). |
| `apps/spaces/_retired/*/` | The retired Space sources, kept for reference; never deployed. |
| `apps/spaces/tools/` | `manifest.py`, `stage.py`, `deploy.py`, `verify_remote.py`, `copy_lint.py`, `pin_drift.py`, `board_check.py`. |
| `tests/spaces/` | Tests for the shared package and the tooling; no network, no heavy dependencies. |

## Manifest

```bash
python3 -c '
import sys; sys.path.insert(0, "apps/spaces/tools")
import manifest
for s in manifest.load_manifest().spaces.values():
    hw = s.hardware or "-"
    print(f"{s.name:20} {s.repo_id:36} {s.sdk:7} {hw:12} sleep={s.sleep_time} shell={s.shared_shell}")
'
```

`sdk` is what the Space's own `README.md` frontmatter declares: `docker` or `gradio` for a
live Space, `static` for a redirect. `tests/spaces/test_manifest.py` cross-checks every live
Space against its sources: frontmatter `sdk` (and `python_version` where present), a
`Dockerfile` present exactly when `sdk = "docker"`, `app_port` for Docker and `sdk_version`
for Gradio.

`shared_shell` records whether the app renders the shared `algenta_spaces` footer with its
build stamp. It is `false` for all three live Spaces today (the same test asserts it against
the app imports) and flips to `true` per Space when M2 moves that app onto the shared shell;
`verify_remote` reads it to decide whether the footer stamp check runs or is skipped.

Unknown keys, wrong types, a repo outside the `thyn-ai` org, a hardware flavour the Hub does
not sell, or a name that is both a secret and a variable fail the load with the table and key
named. Static redirects carry `redirect_to` and nothing else; live Spaces carry `python`,
`hardware`, `sleep_time`, `shared_shell`, `secrets`, `variables`, `api_names`.

## Stage

Stage one Space into an empty directory. The result is the exact tree the Hub receives:
the Space files, `algenta_spaces/` (the shared package), `.shared_sha` (sha256 over the
shared package, sorted paths and bytes) and `.git_sha` (`git rev-parse HEAD`).

```bash
python3 apps/spaces/tools/stage.py --space algenta --out /tmp/stage-algenta
```

Ignored on the way out: `__pycache__/`, `*.pyc`, `tests/`, `*.whl`, `*.so`, `*.dylib`,
`leaderboard.json`. Any file over 500 KB (the pre-commit ceiling) aborts the stage before
a byte is written.

## Deploy

```bash
# inspect: stage, list the files, show the hardware / sleep / variable diff; no writes
python3 apps/spaces/tools/deploy.py --space algenta --dry-run
python3 apps/spaces/tools/deploy.py --all --dry-run

# deploy one Space or the fleet (HF_TOKEN from the environment only, never from .env)
HF_TOKEN=... python3 apps/spaces/tools/deploy.py --space speed-arena
HF_TOKEN=... python3 apps/spaces/tools/deploy.py --all

# roll back: stage from a detached git worktree of that commit and deploy it
HF_TOKEN=... python3 apps/spaces/tools/deploy.py --space algenta --rollback-to <sha>
```

Per Space the tool runs `create_repo(repo_type="space", space_sdk=..., exist_ok=True)`,
one atomic `upload_folder(delete_patterns=["**"], commit_message="deploy <git sha>")`,
then `request_space_hardware` / `set_space_sleep_time` / `add_space_variable` only where
the live runtime differs from the manifest, waits for the new revision (below) and finishes
with the remote verification. Any failure exits non-zero; `BUILD_ERROR`, `RUNTIME_ERROR`,
`CONFIG_ERROR` and `NO_APP_FILE` stop the poll immediately.

The first `RUNNING` after an upload is the previous revision still serving while the Hub
rebuilds, so it is never accepted. The poll (`get_space_runtime().stage`, 40 min budget on
CPU hardware, 60 min on GPU) declares the new revision live once it has observed a rebuild
stage and then `RUNNING`, or, when the runtime never leaves `RUNNING` for 90 s, once
`space_info(repo).sha` equals the commit `oid` that `upload_folder` returned. A live sha
that still differs after those 90 s fails the deploy instead of blessing the old revision.

The dry run uses an anonymous client (`HfApi(token=False)`, so no cached login is borrowed),
reads the runtime where the Hub allows it and says `runtime not readable` otherwise; it
never needs a token.

## Verify a live Space

```bash
python3 apps/spaces/tools/verify_remote.py --space algenta --staged /tmp/stage-algenta
python3 apps/spaces/tools/verify_remote.py --space for-llm-agents
python3 apps/spaces/tools/verify_remote.py --space governed-agent --url https://thyn-ai-algenta-governed-agent.hf.space --shared-sha <sha>
```

Checks registered today: `/gradio_api/info` answers 200 with JSON inside the 30 s turn
budget; every `api_names` entry of the manifest is a named endpoint; the footer's
`build <sha>` stamp equals the staged `.shared_sha`; a redirect page carries a meta refresh
and a canonical link to its `redirect_to` URL. The stamp check runs only for a Space whose
manifest entry says `shared_shell = true`; otherwise it prints
`[SKIP] footer_stamp skipped: app not yet on the shared shell` and the verdict line names
the skip, so a passing report never hides an unchecked footer. Endpoint-level assertions
with real inputs are added per Space as the endpoints ship.

## Gates

Green today, and the set `deploy-spaces.yml` will run before every deploy:

```bash
python3 apps/spaces/tools/copy_lint.py apps/spaces/_shared apps/spaces/_redirects/for-llm-agents apps/spaces/_redirects/governed-tool-calls apps/spaces/_redirects/llm-modules
ruff check apps/spaces/_shared apps/spaces/tools apps/spaces/_redirects tests/spaces && ruff format --check apps/spaces/_shared apps/spaces/tools apps/spaces/_redirects tests/spaces
python3 -m pytest tests/spaces -q -p no:cacheprovider
```

Report only today; the three app directories join both gates in M2 when their copy and
code are migrated onto the shared package (each command exits 1 with its findings until
then):

```bash
python3 apps/spaces/tools/copy_lint.py apps/spaces/algenta apps/spaces/speed-arena apps/spaces/governed-agent
python3 apps/spaces/tools/pin_drift.py apps/spaces/algenta apps/spaces/speed-arena apps/spaces/governed-agent
```

`board_check` validates a leaderboard file against the hardware id of the machine reading it:

```bash
printf '%s\n' '{"hardware_id":"'"$HARDWARE_ID"'","space_id":"thyn-ai/algenta","ts_utc":"2026-09-22T14:02:00Z"}' > /tmp/board.jsonl
python3 apps/spaces/tools/board_check.py /tmp/board.jsonl --hardware-id "$HARDWARE_ID"
```

`copy_lint` reports banned phrases, jargon in primary strings, emoji outside README
frontmatter, exclamation marks, headline (6 words) and subline (14 words) budgets, and the
required pricing and Discord links: in the shell module for a live Space, in `index.html`
for a redirect stub. Markdown code spans and fences are not copy. `pin_drift` reports
pre-release tokens, unpinned requirements, missing `--hash` (with `--require-hashes`) and
version disagreements across Spaces. `board_check` fails on rows without `hardware_id`,
`space_id` or a UTC `ts_utc`, and splits the rest into measured-here and published-elsewhere.

## Secrets and variables

Values are set by the owner with `HfApi.add_space_secret` and `HfApi.add_space_variable`
(the deploy tool sets variables from the manifest; it never touches secrets). The GitHub
environment `hf-spaces-deploy` holds the deploy `HF_TOKEN` (fine-grained, write on the
`thyn-ai` Spaces and the two results Datasets).

| Name | Kind | algenta | speed-arena | governed-agent | Purpose |
|---|---|---|---|---|---|
| `ALGENTA_API_KEY` | secret | yes | no | yes | Hosted governed flow against `https://api.algenta.ai` (dedicated demo tenant, monthly rotation). |
| `HF_TOKEN` | secret | yes | yes | yes | Results Dataset writes; on governed-agent also Inference Providers billing. |
| `ALGENTA_BASE_URL` | variable | `https://api.algenta.ai` | no | `https://api.algenta.ai` | Hosted API endpoint. |
| `ALGENTA_PROVIDER` | variable | no | no | `nscale` | Inference Providers fallback lane. |
| `ALGENTA_PROVIDER_MODEL` | variable | no | no | `Qwen/Qwen3-4B-Instruct-2507` | Model served on the fallback lane. |

Redirect Spaces have no secrets and no variables.

## Cost

Prices read from the Hub on 2026-09-22, 730 h per month. Fleet budget in the manifest:
`budget_usd = 650`.

| Space | Hardware | Rate | Always on | Business-hours schedule |
|---|---|---|---|---|
| `thyn-ai/algenta` | cpu-upgrade | $0.03/h | $21.90 | $21.90 |
| `thyn-ai/algenta-speed-arena` | cpu-upgrade | $0.03/h | $21.90 | $21.90 |
| `thyn-ai/algenta-governed-agent` | l4x1 | $0.80/h | $584.00 | $245.00 (306 h) |
| Inference Providers fallback | pass-through | usage | single-digit $ | single-digit $ |
| 3 static redirects, 2 Datasets, Actions | free | 0 | $0 | $0 |
| Total | | | about $630 | about $290 |

Launch month runs always-on (`sleep_time = -1`). The org spending limit on the Hub is the
hard backstop; a hardware drift between the manifest and the live runtime is treated as a
cost alarm by the deploy diff.

## Community and commercial

Commercial plans: https://algenta.ai/pricing. Community: https://discord.gg/w8NDsph9an.
