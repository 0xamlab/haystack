"""The GPU probe Space: one page, `/health`, `/run.json`, and the run itself at boot.

The probe starts in a background thread when the server starts (`PROBE_AUTOSTART`, default on)
and runs the six measuring stages of `probe.py` one after another, each in its own process
with a wall-clock budget, then writes `run.json`. `/health` is the live record: the phase that
is running, every phase's status, code and time, and each fact once it is measured. The page at
`/` renders that same record in plain HTML; every number on it was measured in this container
during this boot, and what has not been measured yet is shown as absent, never as a stored
result. A failed phase is its code and one sentence, never a traceback. Right under the verdict
the page puts the same decode without Algenta beside it: transformers on the same GPU, float32
and float16, one column each, measured in the same run.

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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import probe
import probe_config as cfg
import probe_core as core

log = logging.getLogger("gpu_probe.app")

APP_DIR = Path(__file__).resolve().parent
TITLE = "Algenta GPU probe"
HEADLINE = "Qwen3-1.7B on Algenta CUDA kernels"
SUBLINE = (
    "One prompt, eight greedy tokens, one GPU: the Hub kernel against a transformers reference."
)
STAGE_PHASES: tuple[str, ...] = tuple(p for p in core.PHASES if p != "record")
HEALTH_PATH = "/health"
RUN_JSON_PATH = "/run.json"
ABSENT = "—"
SIDE_BY_SIDE_TITLE = "Side by side on the same {gpu}"
SIDE_BY_SIDE_PREDATES = (
    "This record predates the baseline stage: the transformers lanes were not part of this "
    "run, so only the Algenta lane is shown."
)
SIDE_BY_SIDE_CAPTION = (
    "Same prompt, same eight greedy tokens requested, same GPU; the precision of each lane is "
    "printed. Steady per-token is the mean of steps {steady_from} to {n}, and tokens per second "
    "(steady) is 1000 over it; tokens per second over all {n} steps divides {n} by the sum of "
    "every step. Time to first token counts from the timed call's start: for the Algenta lane the "
    "prefill runs at session open, so its time to first token is the session open, which "
    "includes the f64 to f32 weight upload, and its warm-up is step 2, inside the timed steps. "
    "The transformers lanes ran one warm-up generate first, excluded from every timed figure; "
    "their step 1 is the prefill, and every step is the gap between two consecutive tokens "
    "reaching the host through the generate streamer. Load is the session open for Algenta and "
    "from_pretrained plus the move to the device for transformers."
)
OPEN_NOTE = "f64 blob uploaded as f32, prompt prefilled"
FIRST_STEP_NOTE = "prefill done at session open"
TTFT_NOTE = "= session open"
_MIB_RE = re.compile(r"^\s*(\d+)\s*MiB\s*$")

PAGE_CSS = """
:root { color-scheme: light dark; }
body { margin: 0; padding: 24px 16px 48px; font: 16px/1.5 -apple-system, BlinkMacSystemFont,
  "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1d1d1f; background: #ffffff; }
main { max-width: 860px; margin: 0 auto; }
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
.lanes-wrap { overflow-x: auto; }
.caption { color: #515154; font-size: 14px; margin-top: 8px; }
footer { margin-top: 48px; color: #515154; font-size: 14px; }
footer a { color: inherit; }
@media (prefers-color-scheme: dark) {
  body { color: #f5f5f7; background: #000000; }
  .alg-subline, th, footer, .caption { color: #a1a1a6; }
  table.lanes th[scope="col"] { color: inherit; }
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
<a href="{kernel_url}">{kernel_repo}</a>, Algenta Community License 1.1.</p>
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
) -> None:
    """The whole run: six stages in order, then `run.json`. Never raises."""
    if runner is None:
        state.stage_dir.mkdir(parents=True, exist_ok=True)

        def runner(name: str, timeout_s: float) -> StageOutcome:
            return subprocess_runner(name, timeout_s, stage_dir=state.stage_dir)

    for name in STAGE_PHASES:
        with state.lock:
            state.machine.start(name)
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


def status_line(body: Mapping[str, Any]) -> str:
    status = str(body.get("status"))
    phase = str(body.get("phase"))
    failure = body.get("failure")
    if status == core.OK:
        parity = body.get("parity") or {}
        verdict = parity.get("verdict") or ABSENT
        return f"Run complete. Parity {verdict}: {parity.get('reference_decoded') or ABSENT}"
    if status == core.ERROR and isinstance(failure, Mapping):
        return (
            f"Stopped at {failure.get('phase')}: {failure.get('code')} "
            f"({failure.get('message') or 'no message'})"
        )
    if status == core.PENDING:
        return "Waiting to start."
    return f"Running: {phase}."


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
    decode = body.get("decode") or {}
    timings = (
        core.decode_timings(decode.get("open_s"), decode.get("step_ms") or []) if decode else {}
    )
    n_steps = timings.get("n_tokens") or cfg.MAX_NEW_TOKENS
    steady_from = cfg.STEADY_FROM_STEP
    reference = body.get("reference") or {}
    parity = body.get("parity") or {}
    run12 = body.get("run12_recorded") or {}
    pins = body.get("pins") or {}
    versions = body.get("versions") or {}
    packages = versions.get("packages") or {}
    divergence = parity.get("first_divergence")
    sections = [
        side_by_side_section(body),
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
                _row("Prompt tokens", model.get("prompt_ids"), plain=True),
            ],
        ),
        _table(
            "Decode on the GPU",
            [
                _row("Prompt", pins.get("prompt")),
                _row("Tokens", decode.get("tokens"), plain=True),
                _row("Text", decode.get("decoded")),
                _row("Session open", _with_note(_s(timings.get("open_s")), OPEN_NOTE)),
                _row("First step", _with_note(_ms(timings.get("first_step_ms")), FIRST_STEP_NOTE)),
                _row("Time to first token", _with_note(_s(timings.get("ttft_s")), TTFT_NOTE)),
                _row(
                    f"Steady per-token (steps {steady_from} to {n_steps})",
                    _ms(timings.get("steady_step_ms")),
                ),
                _row("Tokens per second (steady)", timings.get("steady_tok_per_s")),
                _row(
                    f"Tokens per second (over all {n_steps} steps)",
                    timings.get("all_steps_tok_per_s"),
                ),
                _row("Step times", _ms_list(timings.get("step_ms"))),
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
                _row("Tokenizers agree", reference.get("prompt_ids_agree_with_algenta_tokenizer")),
            ],
        ),
        _table(
            "Parity",
            [
                _row("Verdict", parity.get("verdict")),
                _row(
                    "First divergence",
                    None if not divergence else f"index {divergence.get('index')}",
                ),
                _row(
                    "Reference top-2 margin there",
                    parity.get("reference_top2_margin_at_divergence"),
                ),
                _row("Run 12 recorded (2026-09-22, T4)", run12.get("tokens"), plain=True),
                _row("Matches run 12", run12.get("matches_this_run")),
            ],
        ),
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
        docs_url=cfg.DOCS_URL,
        pricing_url=cfg.PRICING_URL,
        discord_url=cfg.DISCORD_URL,
    )


def _lane_parity(lane: Mapping[str, Any]) -> str | None:
    parity = lane.get("parity")
    if not isinstance(parity, Mapping):
        return None
    verdict = str(parity.get("verdict") or ABSENT)
    div = parity.get("first_divergence")
    if isinstance(div, Mapping):
        verdict += f", first divergence at index {div.get('index')}"
        margin = parity.get("reference_top2_margin_at_divergence")
        if margin is not None:
            verdict += f" (reference top-2 margin {float(margin):.3f})"
    return verdict


def _lane_tokens(lane: Mapping[str, Any], algenta: Mapping[str, Any]) -> str | None:
    text = lane.get("decoded")
    tokens = lane.get("tokens") or []
    if text is None and not tokens:
        return None
    shown = str(text) if text is not None else _fmt(tokens, plain=True)
    if lane is algenta or not tokens:
        return shown
    if tokens == (algenta.get("tokens") or []):
        return f"{shown} (the same {len(tokens)} tokens)"
    cmp = core.compare_tokens(tokens, algenta.get("tokens") or [])
    div = cmp.get("first_divergence") or {}
    return f"{shown} (differs from the Algenta lane at index {div.get('index')})"


def _lane_memory(lane: Mapping[str, Any]) -> str | None:
    taken = _gb(lane.get("device_taken_bytes"))
    peak = _gb(lane.get("peak_allocated_bytes"))
    parts = []
    if taken:
        parts.append(f"{taken} taken on the device")
    if peak:
        parts.append(f"peak allocated {peak}")
    return "; ".join(parts) or None


def _lane_cells(lane: Mapping[str, Any], algenta: Mapping[str, Any]) -> dict[str, Any]:
    """Every row's cell for one lane; an unavailable lane says so once and is absent after."""
    status = lane.get("status")
    if status != core.OK_LANE:
        if status == core.UNAVAILABLE:
            first = f"unavailable ({lane.get('code') or 'no code'})"
        elif status == core.PENDING_LANE:
            first = "not measured yet"
        else:
            first = "not measured in this run"
        return {"tokens": first}
    return {
        "tokens": _lane_tokens(lane, algenta),
        "parity": _lane_parity(lane),
        "load": _with_note(_s(lane.get("load_s")), lane.get("load_label")),
        "ttft": _with_note(_s(lane.get("ttft_s"), fine=True), lane.get("ttft_note")),
        "steady": _ms(lane.get("steady_step_ms")),
        "tok_per_s": lane.get("steady_tok_per_s"),
        "tok_per_s_all": lane.get("all_steps_tok_per_s"),
        "first_step": _with_note(_ms(lane.get("first_step_ms")), lane.get("first_step_note")),
        "memory": _lane_memory(lane),
        "precision": lane.get("precision"),
        "stack": lane.get("stack"),
    }


def side_by_side_section(body: Mapping[str, Any]) -> str:
    """The comparison table right under the verdict: one column per lane, the Algenta lane
    first, every figure this run's own; a caption defines every timing once."""
    view = core.side_by_side(body)
    lanes = view["lanes"]
    algenta = lanes[0]
    gpu = view.get("gpu") or "GPU"
    n_steps = len(algenta.get("step_ms") or []) or cfg.MAX_NEW_TOKENS
    cells = [_lane_cells(lane, algenta) for lane in lanes]
    rows: list[tuple[str, str]] = [
        ("Tokens decoded", "tokens"),
        ("Parity vs the CPU reference", "parity"),
        ("Load / session open", "load"),
        ("Time to first token", "ttft"),
        (f"Steady per-token (steps {view['steady_from_step']} to {n_steps})", "steady"),
        ("Tokens per second (steady)", "tok_per_s"),
        (f"Tokens per second (over all {n_steps} steps)", "tok_per_s_all"),
        ("First step and warm-up", "first_step"),
        ("Device memory", "memory"),
        ("Precision", "precision"),
        ("Stack", "stack"),
    ]
    head = "".join(
        f'<th scope="col">{html.escape(lane["title"])} · {html.escape(lane["precision"])}</th>'
        for lane in lanes
    )
    body_rows = []
    for label, key in rows:
        tds = "".join(f"<td>{html.escape(_fmt(c.get(key)))}</td>" for c in cells)
        body_rows.append(f'<tr><th scope="row">{html.escape(label)}</th>{tds}</tr>')
    notes: list[str] = []
    if view["predates"]:
        notes.append(SIDE_BY_SIDE_PREDATES)
    for ratio in view["ratios"]:
        lane = next(x for x in lanes if x["id"] == ratio["lane"])
        title = f"{lane['title']} {lane['precision']}"
        if ratio["steady_step_ratio"] is not None:
            notes.append(
                f"Ratio of steady per-token times, {title} over Algenta: "
                f"{ratio['steady_step_ratio']:.2f} (both lanes decoded the same tokens)."
            )
        elif ratio["same_tokens"] is False:
            notes.append(f"No ratio for {title}: its tokens differ from the Algenta lane's.")
    caption = SIDE_BY_SIDE_CAPTION.format(steady_from=view["steady_from_step"], n=n_steps)
    return (
        f"<h2>{html.escape(SIDE_BY_SIDE_TITLE.format(gpu=gpu))}</h2>\n"
        '<div class="lanes-wrap"><table class="lanes">\n'
        f"<thead><tr><th></th>{head}</tr></thead>\n<tbody>\n"
        + "\n".join(body_rows)
        + "\n</tbody></table></div>\n"
        + "".join(f'<p class="caption">{html.escape(note)}</p>\n' for note in notes)
        + f'<p class="caption">{html.escape(caption)}</p>'
    )


def _s(value: Any, *, fine: bool = False) -> str | None:
    """Seconds to two decimals; `fine` gives three below one second (a prefill of tens of ms)."""
    if value is None:
        return None
    digits = 3 if fine and float(value) < 1.0 else 2
    return f"{float(value):.{digits}f} s"


def _ms(value: Any) -> str | None:
    return None if value is None else f"{float(value):.2f} ms"


def _ms_list(values: Any) -> str | None:
    if not values:
        return None
    return ", ".join(f"{float(v):.1f}" for v in values) + " ms"


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
