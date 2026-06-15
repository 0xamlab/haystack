#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.png_loader import load_png_rgb

MOJO_DIR = ROOT / "mojo" / "engine"
MOJO_BENCH_SRC = ROOT / "benchmarks" / "mojo_benchmarks" / "bench_image_real_direct.mojo"
ARTIFACT_PATH = ROOT / "build" / "image_real_direct_benchmark_repo_env.json"
PY_LIBS = ROOT / "benchmarks" / "python_libs"

# The python_libs equivalents are imported by bare name and a few of them shadow
# stdlib modules (e.g. datetime). Inserting PY_LIBS onto sys.path at import time
# leaks that shadowing into any process that merely imports this benchmark module
# (and into spawned ProcessPool workers, which re-import on a polluted path).
# Defer the path mutation + bare-name imports until the benchmark actually runs.
py_image_features = None
py_image_quality = None
py_image_resize = None
py_perceptual_hash = None
py_vision_gate = None


def _load_python_libs() -> None:
    """Bind the python_libs equivalents lazily (no import-time sys.path pollution)."""
    global py_image_features, py_image_quality, py_image_resize
    global py_perceptual_hash, py_vision_gate
    if py_image_features is not None:
        return
    if str(PY_LIBS) not in sys.path:
        sys.path.insert(0, str(PY_LIBS))
    import image_features
    import image_quality
    import image_resize
    import perceptual_hash
    import vision_gate

    # image_quality.py currently references math.math.log
    math.math = math

    py_image_features = image_features
    py_image_quality = image_quality
    py_image_resize = image_resize
    py_perceptual_hash = perceptual_hash
    py_vision_gate = vision_gate


DEFAULT_IMAGES: dict[str, Path] = {
    "mojo_logo_64": ROOT / "mojo_env/.pixi/envs/default/share/jupyter/kernels/mojo/logo-64x64.png",
    "earthmenu_80": ROOT / "mojo_env/.pixi/envs/default/lib/tk8.6/demos/images/earthmenu.png",
    "celery_icon_128": ROOT
    / "mojo_env/.pixi/envs/default/lib/python3.12/site-packages/celery/utils/static/celery_128.png",
    "ouster_icon_142x181": ROOT / "mojo_env/.pixi/envs/default/lib/tk8.6/demos/images/ouster.png",
    "interop_screenshot_838x426": ROOT
    / ".claude/worktrees/wf_3967a6fe-cb7-1/docs/mojo/Python interoperability.rtfd/python-interop-e7ab6838e7bdecafb63a7d9a27753d3b.png",
}

_MOJO_IMAGE_RE = re.compile(r"^MOJO_IMAGE\s+(.+)\s+(\d+)\s+(\d+)\s+(\d+)$")
_MOJO_ITERS_RE = re.compile(r"^MOJO_ITERS\s+(\S+)\s+(\d+)$")
_MOJO_TIMING_RE = re.compile(r"^MOJO_TIMING\s+(\S+)\s+([\d.eE+\-]+)$")
_MOJO_RESULT_RE = re.compile(r"^MOJO_RESULT\s+(\S+)\s+(.+)$")


@dataclass(frozen=True)
class LoadedImage:
    name: str
    path: Path
    width: int
    height: int
    flat_rgb: list[float]
    flat_gray: list[float]


@dataclass(frozen=True)
class PythonCase:
    name: str
    kind: str
    fn: Callable[[], Any]


def _image_selection() -> dict[str, Path]:
    raw = os.environ.get("DE_REAL_IMAGE_BENCH_IMAGES", "").strip()
    if not raw:
        return DEFAULT_IMAGES
    selected: dict[str, Path] = {}
    for name in [part.strip() for part in raw.split(",") if part.strip()]:
        if name not in DEFAULT_IMAGES:
            raise KeyError(f"Unknown DE_REAL_IMAGE_BENCH_IMAGES entry: {name}")
        selected[name] = DEFAULT_IMAGES[name]
    return selected


def load_png_image(name: str, path: Path) -> LoadedImage:
    payload = load_png_rgb(path)
    return LoadedImage(
        name=name,
        path=path,
        width=int(payload["width"]),
        height=int(payload["height"]),
        flat_rgb=[float(value) for value in payload["flat_rgb"]],
        flat_gray=[float(value) for value in payload["flat_gray"]],
    )


def build_python_cases(image: LoadedImage) -> list[PythonCase]:
    _load_python_libs()
    blur = py_image_quality.blur_score_flat(image.flat_gray, image.width, image.height)
    brightness = py_image_quality.brightness_flat(image.flat_gray, image.width, image.height)
    entropy = py_image_quality.entropy_flat(image.flat_gray, image.width, image.height)
    edge = py_image_features.edge_density_flat(image.flat_gray, image.width, image.height, 32.0)

    return [
        PythonCase(
            name="blur_score_flat",
            kind="float",
            fn=lambda: py_image_quality.blur_score_flat(image.flat_gray, image.width, image.height),
        ),
        PythonCase(
            name="quality_score_flat",
            kind="float",
            fn=lambda: py_image_quality.quality_score_flat(
                image.flat_gray, image.width, image.height
            ),
        ),
        PythonCase(
            name="edge_density_flat",
            kind="float",
            fn=lambda: py_image_features.edge_density_flat(
                image.flat_gray, image.width, image.height, 32.0
            ),
        ),
        PythonCase(
            name="most_salient_cell_flat",
            kind="int",
            fn=lambda: py_image_features.most_salient_cell_flat(
                image.flat_gray, image.width, image.height, 4, 4
            ),
        ),
        PythonCase(
            name="downscale_flat",
            kind="list",
            fn=lambda: py_image_resize.downscale_flat(
                image.flat_gray,
                image.width,
                image.height,
                min(image.width, 64),
                min(image.height, 64),
            ),
        ),
        PythonCase(
            name="phash_flat",
            kind="int",
            fn=lambda: py_perceptual_hash.phash_flat(image.flat_gray, image.width, image.height),
        ),
        PythonCase(
            name="color_histogram",
            kind="list",
            fn=lambda: py_image_features.color_histogram(
                image.flat_rgb, image.width, image.height, 8
            ),
        ),
        PythonCase(
            name="dominant_colors",
            kind="list",
            fn=lambda: py_image_features.dominant_colors(
                image.flat_rgb, image.width, image.height, 8
            ),
        ),
        PythonCase(
            name="route_image_request",
            kind="int",
            fn=lambda: py_vision_gate.route_image_request(
                blur,
                brightness,
                entropy,
                edge,
                False,
                0,
            ),
        ),
    ]


def _round_half_away_from_zero(value: float, digits: int = 6) -> float:
    scale = 10**digits
    scaled = value * scale
    if scaled >= 0:
        rounded = math.floor(scaled + 0.5)
    else:
        rounded = math.ceil(scaled - 0.5)
    return rounded / scale


def _summary_hash_string(value: str) -> int:
    h = 7
    for byte in value.encode("utf-8"):
        h = (h * 131 + byte) % 2147483647
    return h


def summarize_value(value: Any) -> str:
    if isinstance(value, bool):
        return f"int:{int(value)}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, float):
        if math.isnan(value):
            return "float:nan"
        if math.isinf(value):
            return "float:inf" if value > 0 else "float:-inf"
        return f"float:{_round_half_away_from_zero(value, 6)}"
    if isinstance(value, list):
        joined = "|".join(summarize_value(float(item)) for item in value)
        return f"list:{len(value)}:{_summary_hash_string(joined)}"
    raise TypeError(f"Unsupported summary value: {type(value).__name__}")


def collect_python_timing(case: PythonCase, *, target_total_s: float = 0.25) -> dict[str, Any]:
    started = time.perf_counter()
    first_result = case.fn()
    first_elapsed = time.perf_counter() - started

    times = [first_elapsed]
    total = first_elapsed
    while total < target_total_s and len(times) < 1000:
        started = time.perf_counter()
        case.fn()
        elapsed = time.perf_counter() - started
        times.append(elapsed)
        total += elapsed

    return {
        "summary": summarize_value(first_result),
        "python_samples": len(times),
        "python_median_ns": statistics.median(times) * 1e9,
        "python_mean_ns": statistics.fmean(times) * 1e9,
    }


def parse_mojo_benchmark_output(stdout: str) -> dict[str, Any]:
    image_meta: dict[str, Any] | None = None
    iters: dict[str, int] = {}
    timings: dict[str, float] = {}
    results: dict[str, str] = {}

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _MOJO_IMAGE_RE.match(line)
        if match is not None:
            image_meta = {
                "path": match.group(1),
                "width": int(match.group(2)),
                "height": int(match.group(3)),
                "pixels": int(match.group(4)),
            }
            continue
        match = _MOJO_ITERS_RE.match(line)
        if match is not None:
            iters[match.group(1)] = int(match.group(2))
            continue
        match = _MOJO_TIMING_RE.match(line)
        if match is not None:
            timings[match.group(1)] = float(match.group(2))
            continue
        match = _MOJO_RESULT_RE.match(line)
        if match is not None:
            results[match.group(1)] = match.group(2)
            continue

    if image_meta is None:
        raise RuntimeError(f"Mojo benchmark output missing MOJO_IMAGE header:\n{stdout}")
    return {"image_meta": image_meta, "iters": iters, "timings": timings, "results": results}


def build_mojo_benchmark_binary(mojo_bin: Path) -> Path:
    binary_path = ROOT / "build" / "bench_image_real_direct"
    subprocess.run(
        [str(mojo_bin), "build", f"-I{MOJO_DIR}", str(MOJO_BENCH_SRC), "-o", str(binary_path)],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    return binary_path


def run_mojo_direct(binary_path: Path, image: LoadedImage) -> dict[str, Any]:
    result = subprocess.run(
        [str(binary_path), str(image.path)],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    parsed = parse_mojo_benchmark_output(result.stdout)
    parsed["stdout"] = result.stdout
    return parsed


def main() -> int:
    if sys.executable.startswith("/usr/local/"):
        raise RuntimeError(
            "Run benchmarks/image_real_direct_benchmark.py via ./scripts/run_repo_python.sh "
            "so it uses the repo Pixi environment."
        )

    mojo_bin = Path(sys.executable).with_name("mojo")
    binary_path = build_mojo_benchmark_binary(mojo_bin)
    images = [load_png_image(name, path) for name, path in _image_selection().items()]

    artifact: dict[str, Any] = {
        "kind": "image_real_direct_benchmark",
        "controller_python": sys.executable,
        "mojo_binary": str(mojo_bin),
        "bench_binary": str(binary_path),
        "images": [],
        "summary": {},
    }

    speedups: list[float] = []
    all_matches = True

    for image in images:
        python_cases = build_python_cases(image)
        mojo = run_mojo_direct(binary_path, image)
        image_cases: list[dict[str, Any]] = []

        print(f"[{image.name}] {image.width}x{image.height}")
        for case in python_cases:
            py_stats = collect_python_timing(case)
            mojo_summary = mojo["results"][case.name]
            mojo_ns = mojo["timings"][case.name]
            matched = py_stats["summary"] == mojo_summary
            all_matches = all_matches and matched
            speedup = py_stats["python_median_ns"] / mojo_ns if mojo_ns > 0 else None
            if speedup is not None:
                speedups.append(speedup)
            record = {
                "function": case.name,
                "matched": matched,
                "python_summary": py_stats["summary"],
                "mojo_summary": mojo_summary,
                "python_samples": py_stats["python_samples"],
                "python_median_ns": round(py_stats["python_median_ns"], 3),
                "python_mean_ns": round(py_stats["python_mean_ns"], 3),
                "mojo_iterations": mojo["iters"][case.name],
                "mojo_ns": round(mojo_ns, 3),
                "speedup_x": round(speedup, 6) if speedup is not None else None,
            }
            image_cases.append(record)
            verdict = "match" if matched else "MISMATCH"
            speedup_display = (
                f"x{record['speedup_x']:.3f}" if record["speedup_x"] is not None else "xN/A"
            )
            print(
                f"  {case.name}: {verdict} | py {record['python_median_ns']:.1f} ns | "
                f"mojo {record['mojo_ns']:.1f} ns | {speedup_display}"
            )

        artifact["images"].append(
            {
                "image": image.name,
                "path": str(image.path),
                "width": image.width,
                "height": image.height,
                "pixels": image.width * image.height,
                "cases": image_cases,
            }
        )

    artifact["summary"] = {
        "all_matches": all_matches,
        "image_count": len(artifact["images"]),
        "case_count": sum(len(image["cases"]) for image in artifact["images"]),
        "median_speedup_x": round(statistics.median(speedups), 6),
        "mean_speedup_x": round(statistics.fmean(speedups), 6),
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    print("\nSummary")
    print(json.dumps(artifact["summary"], indent=2))
    print(f"\nartifact: {ARTIFACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
