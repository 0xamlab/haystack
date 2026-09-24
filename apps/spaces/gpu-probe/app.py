"""The GPU probe Space: one page, `/health`, `/run.json`, and the run itself at boot.

The probe starts in a background thread when the server starts (`PROBE_AUTOSTART`, default on)
and runs the measuring stages of `probe.py` one after another, each in its own process with a
wall-clock budget, then writes `run.json`. `/health` is the live record: the phase that is
running, every phase's status, code and time, and each fact once it is measured. The page at
`/` renders that same record in plain HTML; every number on it was measured in this container
during this boot, and what has not been measured yet is shown as absent, never as a stored
result. A failed phase or lane is its code and one sentence, never a traceback. The first
section is the published race, live: the shipped Algenta engine beside llama.cpp F16 on the
same GPU, with the published figures of the same cell printed as such beneath the measured
ones; the second section is the secondary rows, the Hub kernels' parity path and plain
transformers, same GPU, same prompt, same tokens.

Environment: `PROBE_WORK_DIR` (the converted checkpoint and stage reports; default
`~/work`), `PROBE_RUN_JSON` (default `<work>/run.json`), `PROBE_AUTOSTART` (`0` to serve
without running, for tests), `PORT` (default 7860, the Hub's `app_port`).
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import probe
import probe_config as cfg
import probe_core as core

log = logging.getLogger("gpu_probe.app")

APP_DIR = Path(__file__).resolve().parent
TITLE = "Algenta GPU probe"
HEADLINE = "Qwen3-0.6B-Base, the published race, live"
SUBLINE = (
    "Algenta's shipped CUDA engine beside llama.cpp F16 on one GPU: gen=64, the benchmarked shape."
)
STAGE_PHASES: tuple[str, ...] = tuple(p for p in core.PHASES if p != "record")
HEALTH_PATH = "/health"
RUN_JSON_PATH = "/run.json"
ABSENT = "—"
RACE_TITLE = "The published race, live on this {gpu}"
SECONDARY_TITLE = "Secondary rows on the same {gpu}: the Hub kernels and the naive stack"
RACE_PREDATES = (
    "This record predates the race stages: the Algenta engine and llama.cpp were not part of "
    "this run, so only the secondary rows are shown."
)
OPPONENT_BUILD_NOTE = (
    "The published cell's opponent was llama.cpp build {published_build} compiled from source "
    "for sm_{published_arch} alone; this run's is build {build} from ggml-org's official CUDA "
    "image ({tag}, by digest), which carries the common architectures — a build "
    "{later} tags later, not the identical one."
)
RACE_CAPTION = (
    "Same checkpoint, the same {n_prompt}-token prompt (the benchmark battery's eight-id cycle), "
    "{gen} greedy tokens requested, the same GPU in the same run; {warmup} warm-up run excluded, "
    "then {runs} timed runs, each figure the median. Decode tokens per second is each engine's "
    "own definition, the one the published cells used: for Algenta the tokens after the first "
    "over the time of their steps (CONFORM_TIMING decode_tok_s), for llama.cpp its "
    "predicted_per_second. Prefill tokens per second is the prompt over the prefill time; time "
    "to first token is that prefill (the first token is computed by it). Device memory is the "
    "peak nvidia-smi memory.used while the lane's process ran, minus the idle baseline. Every "
    "lane's tokens are compared with a transformers float32 CPU reference on the same ids; the "
    "published gate's form, the first {oracle} tokens, is printed as the oracle."
)
SECONDARY_CAPTION = (
    "Same prompt, same {gen} greedy tokens requested, same GPU; decode tokens per second is the "
    "tokens after the first over the time of their steps, the race's definition. The Hub lane "
    "pays its prefill inside the session open together with the f64 to f32 weight upload, so "
    "its time to first token is the session open; the transformers lanes load the model once "
    "and pay the prefill as step 1 of each generate. Steady per-token is the mean of steps "
    "{steady_from} onwards. One warm-up session or generate is excluded, then {runs} timed runs."
)
P3_LANE_NOTE = (
    "Algenta engine: the packed-int8 captured-graph driver of the published cells ran here, "
    "selected by ALGENTA_CUDA_ENGINE. It runs its gate battery first (16 greedy tokens against "
    "its campaign oracle through one graph chain, 3 seeds x 128 steps graph == per-dispatch "
    "token for token, per-step wall flat and faster than per-dispatch at four depths), then "
    "gen=64 and gen=256 for three arms in one process, one untimed warm-up and {runs} timed "
    "runs per cell, each figure the cell's median with its relative IQR against the frozen 5 % "
    "bar. Its decode figure is the generated tokens over the replay window, prefill excluded, "
    "the published cell's definition; it prints no prefill time and, when the oracle passes, "
    "no token beyond the 16 it checked, so the whole run uses the campaign prompt fixture that "
    "oracle is bound to and the token row shows those 16."
)
PUBLISHED_LABEL = "Published {date}, same cell"
_MIB_RE = re.compile(r"^\s*(\d+)\s*MiB\s*$")

PAGE_CSS = """
:root { color-scheme: light dark; }
body { margin: 0; padding: 24px 16px 48px; font: 16px/1.5 -apple-system, BlinkMacSystemFont,
  "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1d1d1f; background: #ffffff; }
main { max-width: 900px; margin: 0 auto; }
h1 { font-size: 28px; line-height: 1.2; margin: 0 0 8px; letter-spacing: -0.01em; }
h2 { font-size: 18px; margin: 32px 0 8px; }
p { margin: 0 0 16px; }
.alg-subline { color: #515154; }
.status { padding: 8px 16px; border: 1px solid #d2d2d7; border-radius: 8px; margin: 16px 0 24px; }
.status.ok { border-color: #34c759; }
.status.error { border-color: #ff3b30; }
table { border-collapse: collapse; width: 100%; font-size: 15px; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e5ea; vertical-align: top; }
th { width: 34%; font-weight: 500; color: #515154; }
code { font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; word-break: break-all; }
table.lanes th { width: auto; }
table.lanes th[scope="row"] { width: 22%; }
table.lanes th[scope="col"] { font-weight: 600; color: inherit; }
table.lanes td { width: 26%; }
table.lanes tr.hero td { font-size: 22px; font-weight: 600; }
table.lanes tr.published { background: #f5f5f7; color: #515154; font-style: italic; }
table.lanes tr.published th[scope="row"] { color: #515154; }
.lanes-wrap { overflow-x: auto; }
.caption { color: #515154; font-size: 14px; margin-top: 8px; }
footer { margin-top: 48px; color: #515154; font-size: 14px; }
footer a { color: inherit; }
@media (prefers-color-scheme: dark) {
  body { color: #f5f5f7; background: #000000; }
  .alg-subline, th, footer, .caption { color: #a1a1a6; }
  table.lanes th[scope="col"] { color: inherit; }
  table.lanes tr.published { background: #1c1c1e; color: #a1a1a6; }
  table.lanes tr.published th[scope="row"] { color: #a1a1a6; }
  .status { border-color: #424245; }
  th, td { border-bottom-color: #2c2c2e; }
}
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<main>
<h1>{headline}</h1>
<p class="alg-subline">{subline}</p>
<div class="status {status_class}">{status_line}</div>
{sections}
<footer>
<p>The run record is at <a href="{run_json_path}">run.json</a> and the live state at
<a href="{health_path}">/health</a>. Space source: <code>apps/spaces/gpu-probe</code> in the
Algenta repository. Model: <a href="{model_url}">{model_repo}</a> (Apache-2.0). Kernel:
<a href="{kernel_url}">{kernel_repo}</a>, Algenta Community License 1.1. Opponent:
<a href="{llama_url}">llama.cpp</a> (MIT), build {llama_build} from ggml-org's official CUDA
image, by digest.</p>
<p><a href="{docs_url}">Documentation</a> &middot; <a href="{pricing_url}">Commercial plans</a>
&middot; <a href="{discord_url}">Discord</a></p>
</footer>
</main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# State and orchestration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageOutcome:
    """What a stage subprocess left behind."""

    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    wall_s: float


StageRunner = Callable[[str, float], StageOutcome]


class ProbeState:
    """The one run of this boot: the phase machine plus the facts the page and `/health` need."""

    def __init__(
        self,
        *,
        work: Path,
        run_json: Path | None = None,
        versions: Mapping[str, Any] | None = None,
        space: Mapping[str, Any] | None = None,
        build: Mapping[str, Any] | None = None,
    ) -> None:
        self.work = Path(work)
        self.run_json = Path(run_json) if run_json else self.work / "run.json"
        self.stage_dir = self.work / "stages"
        self.versions = dict(versions if versions is not None else probe.environment_facts())
        self.space = dict(space if space is not None else probe.space_facts())
        self.build = dict(build if build is not None else probe.read_build_facts())
        self.machine = core.PhaseMachine()
        self.lock = threading.Lock()
        self.run_json_written = False

    def health(self) -> dict[str, Any]:
        with self.lock:
            return core.health_body(
                self.machine,
                versions=self.versions,
                space=self.space,
                build=self.build,
                run_json_written=self.run_json_written,
            )

    def run_record_text(self) -> str | None:
        with self.lock:  # the flag is written under the lock; read it the same way
            written = self.run_json_written
        if not written:
            return None
        try:
            return self.run_json.read_text(encoding="utf-8")
        except OSError:
            return None


def subprocess_runner(
    name: str, timeout_s: float, *, python: str = sys.executable, stage_dir: Path | None = None
) -> StageOutcome:
    """Run `probe.py --stage <name>` in a fresh interpreter with a wall-clock budget."""
    cmd = [python, str(APP_DIR / "probe.py"), "--stage", name]
    if stage_dir is not None:
        cmd += ["--out", str(Path(stage_dir) / f"{name}.json")]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv built from constants
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        return StageOutcome(
            stdout=_text(exc.stdout),
            stderr=_text(exc.stderr),
            returncode=-1,
            timed_out=True,
            wall_s=time.perf_counter() - t0,
        )
    except OSError as exc:
        return StageOutcome(
            "", f"{type(exc).__name__}: {exc}", 127, False, time.perf_counter() - t0
        )
    return StageOutcome(proc.stdout, proc.stderr, proc.returncode, False, time.perf_counter() - t0)


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value or "")


def run_probe(
    state: ProbeState,
    runner: StageRunner | None = None,
    *,
    timeouts: Mapping[str, float] = cfg.STAGE_TIMEOUTS_S,
    budget_s: float = cfg.RUN_BUDGET_S,
) -> None:
    """The whole run: the stages in order, then `run.json`. Never raises.

    A lane whose dependency is not ok (`decode` needs `kernel`) is recorded as
    `upstream_failed` without running; a lane that would start after `budget_s` seconds of run
    is recorded as `run_budget_exhausted`. The reference and the record always run.
    """
    if runner is None:
        state.stage_dir.mkdir(parents=True, exist_ok=True)

        def runner(name: str, timeout_s: float) -> StageOutcome:
            return subprocess_runner(name, timeout_s, stage_dir=state.stage_dir)

    t_start = time.perf_counter()
    for name in STAGE_PHASES:
        with state.lock:
            state.machine.start(name)
        dependency = core.DEPENDS.get(name)
        if dependency is not None:
            dep = state.machine.records[dependency]
            if dep.status != core.OK:
                with state.lock:
                    state.machine.fail(
                        name,
                        "upstream_failed",
                        f"not run: {dependency} is {dep.status} ({dep.code or 'no code'})",
                        wall_s=0.0,
                    )
                log.warning("phase %s: not run, %s is %s", name, dependency, dep.status)
                continue
        elapsed = time.perf_counter() - t_start
        if name in state.machine.soft and elapsed > budget_s:
            with state.lock:
                state.machine.fail(
                    name,
                    "run_budget_exhausted",
                    f"not run: {elapsed:.0f} s into the {budget_s:.0f} s run budget",
                    wall_s=0.0,
                )
            log.warning("phase %s: not run, the run budget is spent", name)
            continue
        log.info("phase %s: started", name)
        try:
            outcome = runner(name, float(timeouts.get(name, 600.0)))
        except Exception as exc:  # noqa: BLE001 - the runner itself failing is still a phase code
            outcome = StageOutcome("", f"{type(exc).__name__}: {exc}", 126, False, 0.0)
        result = core.stage_result_from_output(
            outcome.stdout, outcome.returncode, timed_out=outcome.timed_out
        )
        tail = core.log_tail(outcome.stderr)
        with state.lock:
            if result.get("ok") is True:
                data = {k: v for k, v in result.items() if k not in ("ok", "stage")}
                state.machine.finish(name, data, wall_s=outcome.wall_s, log_tail=tail)
                log.info("phase %s: ok in %.1f s", name, outcome.wall_s)
            else:
                code = str(result.get("code") or "stage_failed")
                message = str(result.get("message") or "")
                state.machine.fail(name, code, message, wall_s=outcome.wall_s, log_tail=tail)
                log.error("phase %s: %s — %s", name, code, message)
                if name not in state.machine.soft:
                    return
                log.warning("phase %s is soft: the run goes on without it", name)
    with state.lock:
        state.machine.start("record")
    t0 = time.perf_counter()
    try:
        record = core.run_record(state.health())
        state.run_json.parent.mkdir(parents=True, exist_ok=True)
        tmp = state.run_json.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, state.run_json)
        with state.lock:
            state.run_json_written = True
            state.machine.finish(
                "record",
                {"path": str(state.run_json), "bytes": state.run_json.stat().st_size},
                wall_s=time.perf_counter() - t0,
            )
        log.info("run.json written: %s (decision %s)", state.run_json, record.get("decision"))
    except Exception as exc:  # noqa: BLE001
        err = core.public_error(exc)
        with state.lock:
            state.machine.fail("record", err.code, err.message, wall_s=time.perf_counter() - t0)
        log.error("phase record: %s — %s", err.code, err.message)


def start_probe_thread(state: ProbeState, runner: StageRunner | None = None) -> threading.Thread:
    thread = threading.Thread(target=run_probe, args=(state, runner), name="gpu-probe", daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def _fmt(value: Any, *, plain: bool = False) -> str:
    """Quantities get thousands separators; identifiers (`plain`: token ids, a tier name) do
    not, so `59604` and `6144` print as they are named."""
    if value is None or value == "" or value == []:
        return ABSENT
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return str(value) if plain else f"{value:,}"
    if isinstance(value, list | tuple):
        return ", ".join(_fmt(v, plain=plain) for v in value)
    return str(value)


def _env_text(env: Any) -> str | None:
    """A launch environment as `NAME=value` pairs, in the record's order."""
    if not isinstance(env, Mapping) or not env:
        return None
    return " ".join(f"{name}={value}" for name, value in env.items())


def _row(label: str, value: Any, *, code: bool = False, plain: bool = False) -> str:
    text = html.escape(_fmt(value, plain=plain))
    cell = f"<code>{text}</code>" if code and text != ABSENT else text
    return f'<tr><th scope="row">{html.escape(label)}</th><td>{cell}</td></tr>'


def _table(title: str, rows: list[str]) -> str:
    return f"<h2>{html.escape(title)}</h2>\n<table>\n" + "\n".join(rows) + "\n</table>"


def _bytes(value: Any) -> str:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return ABSENT
    return f"{value / 1024**3:.2f} GiB ({int(value):,} bytes)"


def _gb(value: Any) -> str | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    return f"{value / 1e9:.2f} GB ({int(value):,} bytes)"


def _memory(smi_total: Any, total_bytes: Any) -> str:
    """`15360 MiB` from nvidia-smi as `15,360 MiB`, with the driver's byte count beside it."""
    text = str(smi_total or "")
    match = _MIB_RE.match(text)
    shown = f"{int(match.group(1)):,} MiB" if match else (text or ABSENT)
    if isinstance(total_bytes, int) and not isinstance(total_bytes, bool):
        shown += f" ({total_bytes:,} bytes)"
    return shown


def _with_note(value: str | None, note: str | None) -> str | None:
    if value is None:
        return None
    return f"{value} ({note})" if note else value


def _tok_s(value: Any) -> str | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    return f"{float(value):,.1f} tok/s"


def _ms_value(value: Any) -> str | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    ms = float(value)
    return f"{ms / 1000.0:.2f} s" if ms >= 1000.0 else f"{ms:.1f} ms"


def status_line(body: Mapping[str, Any]) -> str:
    status = str(body.get("status"))
    phase = str(body.get("phase"))
    failure = body.get("failure")
    if status == core.OK:
        view = body.get("race") if isinstance(body.get("race"), Mapping) else core.race_view(body)
        parts = []
        for lane in view["race"]:
            if lane["status"] == core.OK_LANE:
                rate = _tok_s(lane.get("decode_tok_per_s")) or ABSENT
                identity = (lane.get("identity") or {}).get("verdict")
                parts.append(
                    f"{lane['title']} {rate}" + (f" (identity {identity})" if identity else "")
                )
            elif lane["status"] == core.UNAVAILABLE:
                parts.append(f"{lane['title']} unavailable ({lane.get('code') or 'no code'})")
            else:
                parts.append(f"{lane['title']} not measured")
        ratio = (view.get("ratio") or {}).get("decode_gen64")
        tail = f"; ratio {ratio:.2f}" if isinstance(ratio, float) else ""
        return f"Run complete. {'; '.join(parts)}{tail}."
    if status == core.ERROR and isinstance(failure, Mapping):
        return (
            f"Stopped at {failure.get('phase')}: {failure.get('code')} "
            f"({failure.get('message') or 'no message'})"
        )
    if status == core.PENDING:
        return "Waiting to start."
    return f"Running: {phase}."


def _graph_nodes_text(block: Mapping[str, Any]) -> str | None:
    """`200 (vs 171 per-dispatch enqueues)` from the packed-int8 driver's node count."""
    nodes = block.get("graph_nodes")
    if not isinstance(nodes, int) or isinstance(nodes, bool):
        return None
    budget = block.get("dispatch_budget")
    return f"{nodes}" + (f" (vs {budget} per-dispatch enqueues)" if budget is not None else "")


def _gates_text(gates: Any) -> str | None:
    """`G0 passed, G1 passed, G2 passed` from the packed-int8 driver's gate records."""
    if not isinstance(gates, Mapping) or not gates:
        return None
    parts = []
    for name in sorted(gates):
        rec = gates[name]
        passed = rec.get("passed") if isinstance(rec, Mapping) else rec
        parts.append(f"{name} {'passed' if passed else 'failed'}")
    return ", ".join(parts)


def _identity_text(lane: Mapping[str, Any]) -> str | None:
    identity = lane.get("identity") or lane.get("parity")
    if not isinstance(identity, Mapping):
        return None
    verdict = str(identity.get("verdict") or ABSENT)
    text = f"{verdict}"
    if identity.get("oracle"):
        text += f", oracle {identity['oracle']}"
    div = identity.get("first_divergence")
    if isinstance(div, Mapping):
        text += f", first divergence at index {div.get('index')}"
        margin = identity.get("reference_top2_margin_at_divergence")
        if margin is not None:
            text += f" (reference top-2 margin {float(margin):.3f})"
    return text


def _tokens_text(lane: Mapping[str, Any], reference: list[int] | None) -> str | None:
    tokens = lane.get("tokens") or []
    decoded = lane.get("decoded")
    if not tokens and decoded is None:
        return None
    shown = (
        str(decoded).strip()
        if decoded
        else _fmt(tokens[:12], plain=True) + (", …" if len(tokens) > 12 else "")
    )
    if len(shown) > 160:
        shown = shown[:157] + "…"
    note = f"{len(tokens)} tokens"
    verified = lane.get("tokens_verified")
    if isinstance(verified, int) and not isinstance(verified, bool) and verified > 0:
        note += " checked by the driver's oracle gate"
        if reference:
            same = list(tokens) == list(reference)[: len(tokens)]
            note += ", the reference's first" if same else ", differ from the reference"
    elif reference:
        note += ", the reference's" if tokens == reference else ", differ from the reference"
    if lane.get("runs_agree") is False:
        note += "; the timed runs did not all agree"
    return f"{shown} ({note})"


def _runs_text(lane: Mapping[str, Any]) -> str | None:
    n = lane.get("n_runs")
    if n is None:
        return None
    text = f"{n} timed, {cfg.WARMUP_RUNS} warm-up excluded"
    if lane.get("runs_agree") is True:
        text += "; identical tokens in every run"
    elif lane.get("runs_agree") is False:
        text += "; tokens differed between runs"
    if lane.get("iqr_note"):
        text += f"; {lane['iqr_note']}"
    return text


def _memory_text(lane: Mapping[str, Any]) -> str | None:
    taken = _gb(lane.get("vram_bytes"))
    peak = _gb(lane.get("peak_allocated_bytes"))
    parts = []
    if taken:
        parts.append(taken)
    if peak:
        parts.append(f"peak allocated by torch {peak}")
    return "; ".join(parts) or None


def _unavailable_first_cell(lane: Mapping[str, Any]) -> str:
    status = lane.get("status")
    if status == core.UNAVAILABLE:
        return f"unavailable ({lane.get('code') or 'no code'})"
    if status == core.PENDING_LANE:
        return "not measured yet"
    return "not measured in this run"


def _race_cells(lane: Mapping[str, Any], reference: list[int] | None) -> dict[str, Any]:
    if lane.get("status") != core.OK_LANE:
        return {"decode": _unavailable_first_cell(lane)}
    long_rate = _tok_s(lane.get("decode_tok_per_s_long"))
    if long_rate is None and lane.get("long_gen_skipped"):
        long_rate = f"not run ({lane['long_gen_skipped']})"
    return {
        "decode": _tok_s(lane.get("decode_tok_per_s")),
        "decode_long": long_rate,
        "prefill": _tok_s(lane.get("prefill_tok_per_s")),
        "ttft": _with_note(_ms_value(lane.get("ttft_ms")), lane.get("ttft_note")),
        "memory": _with_note(_memory_text(lane), lane.get("vram_note")),
        "tokens": _tokens_text(lane, reference),
        "identity": _identity_text(lane),
        "runs": _runs_text(lane),
        "precision": _with_note(lane.get("precision"), lane.get("session_note")),
        "stack": lane.get("stack"),
    }


def _secondary_cells(lane: Mapping[str, Any], reference: list[int] | None) -> dict[str, Any]:
    if lane.get("status") != core.OK_LANE:
        return {"decode": _unavailable_first_cell(lane)}
    return {
        "decode": _tok_s(lane.get("decode_tok_per_s")),
        "ttft": _with_note(_ms_value(lane.get("ttft_ms")), lane.get("ttft_note")),
        "load": _with_note(_s(lane.get("load_s")), lane.get("load_label")),
        "steady": _with_note(
            _ms(lane.get("steady_step_ms")),
            f"steps {lane['steady_steps']}" if lane.get("steady_steps") else None,
        ),
        "steady_tok_per_s": _tok_s(lane.get("steady_tok_per_s")),
        "memory": _with_note(_memory_text(lane), lane.get("vram_note")),
        "tokens": _tokens_text(lane, reference),
        "identity": _identity_text(lane),
        "runs": _runs_text(lane),
        "precision": lane.get("precision"),
        "stack": lane.get("stack"),
    }


def _lanes_table(
    lanes: list[Mapping[str, Any]],
    cells: list[Mapping[str, Any]],
    rows: list[tuple[str, str, str]],
    extra_rows: Sequence[str] = (),
) -> str:
    head = "".join(
        f'<th scope="col">{html.escape(lane["title"])} · {html.escape(lane["precision"])}</th>'
        for lane in lanes
    )
    body_rows = []
    for label, key, css in rows:
        tds = "".join(f"<td>{html.escape(_fmt(c.get(key)))}</td>" for c in cells)
        klass = f' class="{css}"' if css else ""
        body_rows.append(f'<tr{klass}><th scope="row">{html.escape(label)}</th>{tds}</tr>')
    body_rows.extend(extra_rows)
    return (
        '<div class="lanes-wrap"><table class="lanes">\n'
        f"<thead><tr><th></th>{head}</tr></thead>\n<tbody>\n"
        + "\n".join(body_rows)
        + "\n</tbody></table></div>\n"
    )


def _published_row(label: str, url: str, page: str, algenta: str, opponent: str) -> str:
    return (
        '<tr class="published">'
        f'<th scope="row">{html.escape(label)} (L4), '
        f'<a href="{html.escape(url)}">{html.escape(page)}</a></th>'
        f"<td>{html.escape(algenta)}</td><td>{html.escape(opponent)}</td></tr>"
    )


def _published_rows(published: Mapping[str, Any]) -> list[str]:
    serving = published.get("serving") or {}
    throughput = published.get("throughput") or {}
    label = PUBLISHED_LABEL.format(date=published.get("date") or cfg.PUBLISHED_DATE)
    rows = []
    if serving:
        algenta = (
            f"{serving['algenta_gen64']:.1f} tok/s at gen=64, "
            f"{serving['algenta_gen256']:.1f} at gen=256 ({serving.get('session') or ''})"
        )
        opponent = (
            f"{serving['ratio_gen64']:.2f}× slower at gen=64 "
            f"({serving['llama_gen64_implied']:.1f} tok/s implied), "
            f"{serving['ratio_gen256']:.2f}× at gen=256 "
            f"({serving['llama_gen256_implied']:.1f} implied); {serving.get('opponent') or ''}"
        )
        rows.append(
            _published_row(
                label,
                serving.get("url") or cfg.PUBLISHED_SERVING_URL,
                "NVIDIA LLM serving",
                algenta,
                opponent,
            )
        )
    if throughput:
        algenta = (
            f"{throughput['algenta_gen64']:.1f} tok/s at gen=64, "
            f"{throughput['algenta_gen256']:.1f} at gen=256 ({throughput.get('session') or ''})"
        )
        opponent = (
            f"{throughput['llama_gen64']:.1f} tok/s at gen=64, "
            f"{throughput['llama_gen256']:.1f} at gen=256"
        )
        # `_ratio` answers None for a non-positive operand and an older replayed record can
        # carry None here: the parenthetical appears only when both ratios are numbers
        ratios = (throughput.get("ratio_gen64"), throughput.get("ratio_gen256"))
        if all(isinstance(r, int | float) and not isinstance(r, bool) for r in ratios):
            opponent += f" (ratio {float(ratios[0]):.2f} / {float(ratios[1]):.2f})"
        rows.append(
            _published_row(
                label,
                throughput.get("url") or cfg.PUBLISHED_THROUGHPUT_URL,
                "NVIDIA LLM throughput",
                algenta,
                opponent,
            )
        )
    return rows


def race_section(body: Mapping[str, Any]) -> str:
    """The first section: lanes A and B as columns, the hero row first, the published rows of
    the same cell beneath the measured ones, then the ratio and the definitions."""
    view = body.get("race") if isinstance(body.get("race"), Mapping) else core.race_view(body)
    lanes = list(view["race"])
    reference = view.get("reference_tokens")
    gpu = view.get("gpu") or "GPU"
    cells = [_race_cells(lane, reference) for lane in lanes]
    rows: list[tuple[str, str, str]] = [
        (f"Decode tokens per second (gen={view['gen_tokens']})", "decode", "hero"),
        (f"Decode tokens per second (gen={view['gen_tokens_long']})", "decode_long", ""),
        (f"Prefill tokens per second ({view['n_prompt']} tokens)", "prefill", ""),
        ("Time to first token", "ttft", ""),
        ("Device memory (peak)", "memory", ""),
        (f"Tokens ({view['gen_tokens']} greedy)", "tokens", ""),
        ("Identity vs the CPU reference", "identity", ""),
        ("Runs", "runs", ""),
        ("Precision", "precision", ""),
        ("Build", "stack", ""),
    ]
    table = _lanes_table(lanes, cells, rows, _published_rows(view.get("published") or {}))
    notes: list[str] = []
    if view.get("predates"):
        notes.append(RACE_PREDATES)
    for lane in lanes:
        if lane.get("status") == core.UNAVAILABLE:
            notes.append(
                f"{lane['title']}: unavailable, {lane.get('code') or 'no code'}"
                + (f" — {lane['message']}" if lane.get("message") else "")
                + "."
            )
    ratio = view.get("ratio") or {}
    # a stored `race` block is data: it may carry fewer or more than the two lanes of today
    engine = lanes[0] if lanes else {}
    llama = lanes[1] if len(lanes) > 1 else {}
    if ratio.get("decode_gen64") is not None:
        text = (
            f"Measured ratio, {engine.get('title') or 'Algenta engine'} over "
            f"{llama.get('title') or 'llama.cpp'}, decode at gen="
            f"{view['gen_tokens']}: {ratio['decode_gen64']:.2f}"
        )
        if ratio.get("decode_gen256") is not None:
            text += f"; at gen={view['gen_tokens_long']}: {ratio['decode_gen256']:.2f}"
        if ratio.get("prefill") is not None:
            text += f"; prefill: {ratio['prefill']:.2f}"
        compared = ratio.get("tokens_compared")
        verified = engine.get("tokens_verified")
        if isinstance(verified, int) and isinstance(compared, int):
            text += (
                f" (both lanes decoded the same first {compared} tokens, the ones the "
                "Algenta driver prints)."
            )
        else:
            text += " (both lanes decoded the same tokens)."
        notes.append(text)
    elif ratio.get("same_tokens") is False:
        notes.append("No ratio: the two lanes decoded different tokens.")
    if engine.get("protocol") == cfg.P3_ENGINE_NAME:
        notes.append(P3_LANE_NOTE.format(runs=engine.get("n_runs") or cfg.RUNS))
    llama_build = llama.get("build") or {}
    # a record whose lane B ran from the prebuilt image says so; one without an image block
    # (none exists yet: the source build never ran) is not described as one
    if llama.get("status") == core.OK_LANE and llama_build.get("image_tag"):
        build = llama_build.get("build_number") or cfg.LLAMA_CPP_BUILD
        notes.append(
            OPPONENT_BUILD_NOTE.format(
                published_build=cfg.PUBLISHED_LLAMA_CPP_BUILD,
                published_arch=cfg.PUBLISHED_LLAMA_CUDA_ARCHITECTURES,
                build=build,
                tag=llama_build["image_tag"],
                later=int(build) - cfg.PUBLISHED_LLAMA_CPP_BUILD,
            )
        )
    caption = RACE_CAPTION.format(
        n_prompt=view["n_prompt"],
        gen=view["gen_tokens"],
        warmup=view["warmup_runs"],
        runs=view["runs"],
        oracle=cfg.ORACLE_PREFIX,
    )
    return (
        f"<h2>{html.escape(RACE_TITLE.format(gpu=gpu))}</h2>\n"
        + table
        + "".join(f'<p class="caption">{html.escape(note)}</p>\n' for note in notes)
        + f'<p class="caption">{html.escape(caption)}</p>'
    )


def secondary_section(body: Mapping[str, Any]) -> str:
    view = body.get("race") if isinstance(body.get("race"), Mapping) else core.race_view(body)
    lanes = list(view["secondary"])
    reference = view.get("reference_tokens")
    gpu = view.get("gpu") or "GPU"
    cells = [_secondary_cells(lane, reference) for lane in lanes]
    rows: list[tuple[str, str, str]] = [
        (f"Decode tokens per second (gen={view['gen_tokens']})", "decode", "hero"),
        ("Time to first token", "ttft", ""),
        ("Load / session open", "load", ""),
        ("Steady per-token", "steady", ""),
        ("Tokens per second (steady)", "steady_tok_per_s", ""),
        ("Device memory", "memory", ""),
        (f"Tokens ({view['gen_tokens']} greedy)", "tokens", ""),
        ("Identity vs the CPU reference", "identity", ""),
        ("Runs", "runs", ""),
        ("Precision", "precision", ""),
        ("Stack", "stack", ""),
    ]
    table = _lanes_table(lanes, cells, rows)
    notes: list[str] = []
    for lane in lanes:
        if lane.get("status") == core.UNAVAILABLE:
            notes.append(
                f"{lane['title']} {lane['precision']}: unavailable, {lane.get('code') or 'no code'}"
                + (f" — {lane['message']}" if lane.get("message") else "")
                + "."
            )
    caption = SECONDARY_CAPTION.format(
        gen=view["gen_tokens"], steady_from=cfg.STEADY_FROM_STEP, runs=view["runs"]
    )
    return (
        f"<h2>{html.escape(SECONDARY_TITLE.format(gpu=gpu))}</h2>\n"
        + table
        + "".join(f'<p class="caption">{html.escape(note)}</p>\n' for note in notes)
        + f'<p class="caption">{html.escape(caption)}</p>'
    )


def render_page(body: Mapping[str, Any]) -> str:
    phases = body.get("phases") or {}
    phase_rows = []
    for name in core.PHASES:
        rec = phases.get(name) or {}
        detail = rec.get("status") or ABSENT
        if rec.get("wall_s") is not None:
            detail += f" in {rec['wall_s']:.1f} s"
        if rec.get("code") and rec.get("status") in (core.ERROR, core.SKIPPED):
            detail += f" ({rec['code']})"
        phase_rows.append(_row(name, detail))
    driver = body.get("driver") or {}
    smi = driver.get("nvidia_smi") or {}
    torch_facts = driver.get("torch") or {}
    kernel = body.get("kernel") or {}
    model = body.get("model") or {}
    engine_block = body.get("engine") or {}
    engine = engine_block.get("engine") or {}
    gate = engine_block.get("target_gate") or {}
    llama = body.get("llama") or {}
    llama_version = llama.get("version") or {}
    gguf = llama.get("gguf") or {}
    reference = body.get("reference") or {}
    pins = body.get("pins") or {}
    versions = body.get("versions") or {}
    packages = versions.get("packages") or {}
    view = body.get("race") if isinstance(body.get("race"), Mapping) else core.race_view(body)
    identity_rows = []
    for lane in [*view["race"], *view["secondary"]]:
        text = (
            _identity_text(lane)
            if lane.get("status") == core.OK_LANE
            else _unavailable_first_cell(lane)
        )
        identity_rows.append(_row(f"{lane['title']} · {lane['precision']}", text))
    sections = [
        race_section(body),
        secondary_section(body),
        _table("Phases", phase_rows),
        _table(
            "Device",
            [
                _row("GPU", driver.get("device_name") or smi.get("name")),
                _row(
                    "Compute capability", ".".join(map(str, driver.get("compute_capability") or []))
                ),
                _row("Memory", _memory(smi.get("memory.total"), driver.get("total_memory_bytes"))),
                _row("NVIDIA driver", driver.get("driver_version")),
                _row("CUDA driver API", driver.get("cuda_driver_api")),
                _row("Driver floor", pins.get("driver_floor")),
                _row("torch", torch_facts.get("version")),
                _row("torch CUDA", torch_facts.get("cuda")),
                _row("Hardware requested", pins.get("hardware")),
                _row("Prompt fixture", pins.get("prompt_fixture")),
            ],
        ),
        _table(
            "Algenta engine",
            [
                _row("Wheel", pins.get("engine"), code=True),
                _row("Selected by ALGENTA_CUDA_ENGINE", pins.get("engine_selected"), code=True),
                _row("Protocol", engine_block.get("protocol") or pins.get("engine_protocol")),
                _row("Binary", engine.get("path"), code=True),
                _row("Resolved from", engine.get("resolved_from")),
                _row("Session", engine.get("session")),
                _row("Built", engine.get("built_utc")),
                _row("Source commit", engine.get("source_commit"), code=True),
                _row("Mojo", engine.get("mojo_version")),
                _row("Compile target", engine.get("cuda_target"), code=True),
                _row(
                    "Target gate",
                    None
                    if not gate
                    else (
                        "compute capability "
                        f"{'.'.join(map(str, gate.get('device_compute_capability') or []))}: "
                        + (
                            "passed"
                            if gate.get("ok")
                            else "not checked"
                            if not gate.get("checked")
                            else "refused"
                        )
                    ),
                ),
                _row("Comptime defines", engine.get("comptime_defines"), code=True),
                _row("Host libraries", engine.get("host_shared_libraries"), code=True),
                _row("sha256", engine.get("sha256"), code=True),
                _row("Bundled libraries", engine.get("bundled_shared_libraries"), code=True),
                _row("Argv", engine_block.get("argv"), code=True),
                _row("Gates", _gates_text(engine_block.get("gates"))),
                _row("Kernel set", engine_block.get("kernel_variant")),
                _row("Captured nodes per token", _graph_nodes_text(engine_block)),
                _row("One-time load", _ms_value(engine_block.get("load_ms"))),
            ],
        ),
        _table(
            "llama.cpp",
            [
                _row("Image", pins.get("llama_image"), code=True),
                _row("Image tag", pins.get("llama_image_tag"), code=True),
                _row(
                    "Pinned build",
                    f"b{pins['llama_cpp_build']}" if pins.get("llama_cpp_build") else None,
                    code=True,
                ),
                _row("Pinned commit", pins.get("llama_cpp_commit"), code=True),
                _row("Reported version", llama_version.get("line")),
                _row("CUDA architectures", llama.get("cuda_architectures"), code=True),
                _row(
                    "Published cell's build",
                    (
                        f"b{pins['published_llama_cpp_build']} "
                        f"({str(pins.get('published_llama_cpp_commit') or '')[:10]}), built from "
                        f"source for sm_{pins.get('published_llama_cuda_architectures')} only; "
                        "not this build"
                    )
                    if pins.get("published_llama_cpp_build")
                    else None,
                ),
                _row("Launch environment", _env_text(llama.get("env")), code=True),
                _row("GGUF", gguf.get("path"), code=True),
                _row("GGUF size", _bytes(gguf.get("bytes"))),
                _row("Server ready", _s(llama.get("ready_s"))),
                _row("Argv", llama.get("argv"), code=True),
            ],
        ),
        _table(
            "Kernel",
            [
                _row("Repository", pins.get("kernel_repo"), code=True),
                _row("Pinned revision", pins.get("kernel_revision"), code=True),
                _row("Loaded revision", kernel.get("revision"), code=True),
                _row("Build variant", kernel.get("variant"), code=True),
                _row("Staging tier", kernel.get("resident_stage_tier"), plain=True),
                _row("CUDA targets", kernel.get("cuda_targets")),
                _row("Library loaded", kernel.get("selected_library"), code=True),
                _row("Mojo toolchain", kernel.get("mojo_version")),
                _row("get_kernel", _s(kernel.get("get_kernel_s"))),
                _row("Native init", _s(kernel.get("native_init_s"))),
            ],
        ),
        _table(
            "Model",
            [
                _row("Repository", pins.get("model_repo"), code=True),
                _row("Snapshot", pins.get("model_revision"), code=True),
                _row("Converted as", model.get("weights_dtype")),
                _row("Blob", _bytes(model.get("blob_bytes"))),
                _row(
                    "Conversion",
                    "reused from disk" if model.get("reused") else _s(model.get("wall_s")),
                ),
                _row("Prompt", _prompt_text(model, reference)),
                _row(
                    "Prompt tokens",
                    model.get("n_prompt") or len(model.get("prompt_ids") or []) or None,
                    plain=True,
                ),
            ],
        ),
        _table(
            "Reference on the CPU",
            [
                _row("Method", reference.get("reference")),
                _row("transformers", reference.get("transformers")),
                _row("Threads", reference.get("threads")),
                _row("Tokens", reference.get("tokens"), plain=True),
                _row("Text", reference.get("decoded")),
                _row("Model load", _s(reference.get("load_s"))),
                _row("Generate", _s(reference.get("generate_s"))),
            ],
        ),
        _table("Identity", identity_rows),
        _table(
            "Versions",
            [
                _row("Python", versions.get("python")),
                _row("glibc", versions.get("glibc")),
                _row("Image CUDA", versions.get("cuda_version_env")),
                *[_row(name, version) for name, version in sorted(packages.items())],
                _row("Started", body.get("started_utc")),
                _row("Updated", body.get("updated_utc")),
            ],
        ),
    ]
    status = str(body.get("status"))
    return PAGE_TEMPLATE.format(
        title=html.escape(TITLE),
        css=PAGE_CSS,
        headline=html.escape(HEADLINE),
        subline=html.escape(SUBLINE),
        status_class="ok" if status == core.OK else "error" if status == core.ERROR else "",
        status_line=html.escape(status_line(body)),
        sections="\n".join(sections),
        run_json_path=RUN_JSON_PATH,
        health_path=HEALTH_PATH,
        model_url=cfg.MODEL_HUB_URL,
        model_repo=html.escape(cfg.MODEL_REPO),
        kernel_url=cfg.KERNEL_HUB_URL,
        kernel_repo=html.escape(cfg.KERNEL_REPO),
        llama_url=cfg.LLAMA_CPP_URL,
        llama_build=html.escape(cfg.LLAMA_CPP_TAG),
        docs_url=cfg.DOCS_URL,
        pricing_url=cfg.PRICING_URL,
        discord_url=cfg.DISCORD_URL,
    )


def _prompt_text(model: Mapping[str, Any], reference: Mapping[str, Any]) -> str | None:
    """The race prompt as the record describes it: the decoded cycle and its repeat count when
    the record carries the cycle, else the record's own prompt ids."""
    cycle_ids = model.get("prompt_cycle_ids")
    prompt_ids = model.get("prompt_ids") or []
    if not cycle_ids:
        return _fmt(prompt_ids, plain=True) if prompt_ids else None
    cycle = model.get("decoded_prompt_cycle") or reference.get("prompt_cycle_text")
    n_prompt = model.get("n_prompt") or len(prompt_ids) or cfg.PROMPT_TOKENS
    repeats = int(n_prompt) // max(1, len(cycle_ids))
    ids = _fmt(cycle_ids, plain=True)
    if cycle:
        return f"{str(cycle).strip()!r} (ids {ids}) repeated {repeats} times"
    return f"ids {ids} repeated {repeats} times"


def _s(value: Any, *, fine: bool = False) -> str | None:
    """Seconds to two decimals; `fine` gives three below one second (a prefill of tens of ms)."""
    if value is None:
        return None
    digits = 3 if fine and float(value) < 1.0 else 2
    return f"{float(value):.{digits}f} s"


def _ms(value: Any) -> str | None:
    return None if value is None else f"{float(value):.2f} ms"


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------


def build_app(state: ProbeState) -> Any:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse, Response

    api = FastAPI(title=TITLE, docs_url=None, redoc_url=None, openapi_url=None)

    @api.get("/", response_class=HTMLResponse)
    def page() -> HTMLResponse:
        return HTMLResponse(render_page(state.health()))

    @api.get(HEALTH_PATH)
    def health() -> JSONResponse:
        body = state.health()
        return JSONResponse(body, status_code=503 if body["status"] == core.ERROR else 200)

    @api.get(RUN_JSON_PATH)
    def run_json() -> Response:
        text = state.run_record_text()
        if text is None:
            return JSONResponse(
                {"error": "run_not_recorded", "phase": state.health()["phase"]}, status_code=404
            )
        return Response(text, media_type="application/json")

    return api


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="serve the GPU probe")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", cfg.APP_PORT)))
    ap.add_argument("--host", default="0.0.0.0")  # noqa: S104 - the container's public bind
    ap.add_argument(
        "--no-run",
        action="store_true",
        help="serve without starting the probe (also PROBE_AUTOSTART=0)",
    )
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    work = probe.work_dir()
    run_json_env = os.environ.get("PROBE_RUN_JSON", "").strip()
    state = ProbeState(work=work, run_json=Path(run_json_env) if run_json_env else None)
    autostart = os.environ.get("PROBE_AUTOSTART", "1").strip().lower() not in ("0", "false", "no")
    if autostart and not a.no_run:
        start_probe_thread(state)
    else:
        log.info("probe not started (PROBE_AUTOSTART off or --no-run)")
    import uvicorn

    uvicorn.run(build_app(state), host=a.host, port=a.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
