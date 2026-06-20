"""
benchmark_mojo_vs_python.py
===========================
For every Mojo library (A → Z):
  1. Auto-transpile each public function to a Python equivalent.
  2. Generate a Mojo timing-loop benchmark file that calls each function
     N times and reports ns-per-call.
  3. Run both, compare outputs (correctness) and wall-clock timing.
  4. Write per-library JSON to benchmarks/results/{lib}.json.
  5. Write benchmarks/summary.json + benchmarks/summary.txt.

Usage:
  python3 tests/benchmark_mojo_vs_python.py
  DE_BENCH_N=50000 python3 ...        # iterations per function (default 10000)
  DE_BENCH_WORKERS=12 python3 ...     # parallel Mojo processes (default 8)
  DE_BENCH_TIMEOUT=60 python3 ...     # seconds per library Mojo run (default 30)
  DE_BENCH_LIBS=accounting,finance python3 ...   # run only named libs

Run from repo root.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.llm_rollout_matrix import LLM_ROLLOUT_FUNCTIONS_BY_MODULE  # noqa: E402

MOJO_DIR = ROOT / "mojo" / "engine"
MOJO_ENV = ROOT / "mojo_env"
BENCH_DIR = ROOT / "benchmarks"
RESULTS = BENCH_DIR / "results"
MOJO_BENCH = BENCH_DIR / "mojo_benchmarks"
PY_LIBS = BENCH_DIR / "python_libs"
PY_MANUAL_LIBS = BENCH_DIR / "python_manual_libs"
SUMMARY_JSON_PATH = Path(
    os.environ.get("DE_BENCH_SUMMARY_JSON", str(BENCH_DIR / "summary.json"))
).expanduser()
SUMMARY_TXT_PATH = Path(
    os.environ.get("DE_BENCH_SUMMARY_TXT", str(BENCH_DIR / "summary.txt"))
).expanduser()

N_ITER = int(os.environ.get("DE_BENCH_N", "10000"))
WORKERS = int(os.environ.get("DE_BENCH_WORKERS", "8"))
TIMEOUT = int(os.environ.get("DE_BENCH_TIMEOUT", "30"))
ONLY_LIBS = set(os.environ.get("DE_BENCH_LIBS", "").split(",")) - {""}

_BLOCK_5X5_EXPR = repr(
    [255.0 if 1 <= (index // 5) <= 3 and 1 <= (index % 5) <= 3 else 0.0 for index in range(25)]
)
_RING_5X5_EXPR = repr(
    [
        255.0
        if 1 <= (index // 5) <= 3 and 1 <= (index % 5) <= 3 and not ((index // 5) == 2 and (index % 5) == 2)
        else 0.0
        for index in range(25)
    ]
)
_COMPONENTS_6X6_EXPR = repr(
    [
        255.0
        if (
            (index % 6 == 0 and index // 6 in {1, 2})
            or (index % 6 == 3 and index // 6 in {1, 2, 3})
            or (index % 6 == 4 and index // 6 == 1)
        )
        else 0.0
        for index in range(36)
    ]
)
_DOC_8X8_EXPR = repr(
    [
        20.0
        if (
            (index // 8 == 2 and 1 <= (index % 8) <= 6)
            or (index // 8 == 5 and 2 <= (index % 8) <= 5)
        )
        else 240.0
        for index in range(64)
    ]
)
_DOC_8X8_ALT_EXPR = repr(
    [
        60.0
        if (
            (index // 8 == 2 and 1 <= (index % 8) <= 6)
            or (index // 8 == 5 and 2 <= (index % 8) <= 5)
        )
        else 235.0
        for index in range(64)
    ]
)
_DOC_MASK_8X8_EXPR = repr(
    [
        255.0
        if (
            (index // 8 == 2 and 1 <= (index % 8) <= 6)
            or (index // 8 == 5 and 2 <= (index % 8) <= 5)
        )
        else 0.0
        for index in range(64)
    ]
)
_ADAPTIVE_DOC_6X6_EXPR = repr(
    [
        40.0
        if (index // 6 == 2 and 2 <= (index % 6) <= 3)
        else (220.0 if (index % 6) < 3 else 245.0)
        for index in range(36)
    ]
)
_SKEW_MASK_6X6_EXPR = repr(
    [255.0 if 1 <= (index // 6) <= 4 and (index % 6) == (index // 6) else 0.0 for index in range(36)]
)
_BLOB_DOC_8X8_EXPR = repr(
    [
        20.0
        if (
            (2 <= (index // 8) <= 4 and 1 <= (index % 8) <= 3)
            or ((index % 8) == 6 and (index // 8 in {1, 2}))
        )
        else 235.0
        for index in range(64)
    ]
)
_DOC_COLUMNS_8X8_EXPR = repr(
    [
        255.0
        if 1 <= (index // 8) <= 6 and ((1 <= (index % 8) <= 2) or (5 <= (index % 8) <= 6))
        else 0.0
        for index in range(64)
    ]
)
_DOC_TABLE_9X9_EXPR = repr(
    [
        255.0
        if (
            (((1 <= (index // 9) <= 2) or (4 <= (index // 9) <= 5) or (7 <= (index // 9) <= 8)))
            and (((1 <= (index % 9) <= 2) or (4 <= (index % 9) <= 5) or (7 <= (index % 9) <= 8)))
        )
        else 0.0
        for index in range(81)
    ]
)
_TEXTURE_16X16_EXPR = repr(
    [
        (255.0 if ((index // 16) + (index % 16)) % 2 == 0 else 0.0)
        if (index // 16) >= 8 and (index % 16) >= 8
        else 64.0
        for index in range(256)
    ]
)
_GRID_4X4_EXPR = repr([float(index) for index in range(16)])
_BOX_A_EXPR = "[0, 0, 2, 2]"
_BOX_B_EXPR = "[1, 1, 3, 3]"
_VIDEO_3X4X4_EXPR = repr(
    [10.0 for _ in range(16)]
    + [200.0 if pixel < 4 else 10.0 for pixel in range(16)]
    + [200.0 for _ in range(16)]
)
_VIDEO_3X4X4_ALT_EXPR = repr(
    [12.0 for _ in range(16)]
    + [188.0 if pixel < 4 else 12.0 for pixel in range(16)]
    + [192.0 for _ in range(16)]
)
_VIDEO_RGB_3X2X2_EXPR = repr(
    [200.0, 20.0, 20.0] * 4
    + [200.0, 20.0, 20.0] * 3
    + [20.0, 20.0, 200.0]
    + [20.0, 20.0, 200.0] * 4
)
_VIDEO_MOTION_3X5X5_EXPR = repr(
    [10.0 for _ in range(25)]
    + [
        200.0 if 1 <= (index // 5) <= 2 and 1 <= (index % 5) <= 2 else 10.0
        for index in range(25)
    ]
    + [
        200.0
        if (
            (1 <= (index // 5) <= 2 and 1 <= (index % 5) <= 2)
            or ((index // 5) == 4 and (index % 5) == 4)
        )
        else 10.0
        for index in range(25)
    ]
)
_COLOR_CHECK_IMAGE_2X2_EXPR = repr(
    [
        200.0, 20.0, 20.0,
        200.0, 20.0, 20.0,
        200.0, 20.0, 20.0,
        20.0, 20.0, 200.0,
    ]
)

SKIP_FILES = {
    "main",
    "types",
    "expr",
    "output",
    "request_parser",
    "python_bridge",
    # engine entry points only — only have run_*(req: SimRequest) with no simple params
    "compare",
    "decision_tree",
    "time_series",
    "importance_sampling",
    "decision_tree_parser",
    "field_mapper",
    "validate",
    # __init__ files are package markers, not libraries
    "__init__",
    # trie: Mojo bench crashes (Trie() default-constructor in loop causes memory corruption)
    "trie",
    # pure struct-only APIs — no top-level fn, only struct methods (MarkovChain, SobolGen, Scheduler)
    "markov",
    "sobol",
    "scheduler",
}

# Subdirectory files that are engine infrastructure, not domain math libraries
SKIP_SUBDIR_FILES = {
    # engines — complex simulation state machines (no simple-param public fns)
    "engines/bootstrap",
    "engines/lhs",
    "engines/mcmc",
    "engines/qmc_sobol",
    "engines/scenario",
    "engines/sensitivity",
    # logging — side-effect only
    "logging/logger",
    # net — low-level socket I/O (rate_limiter only — unix_socket has benchmarkable encode/decode fns)
    "net/rate_limiter",
    # json tokenizer — struct/state-based, no simple-param public fns
    "json/tokenizer",
    # structs — only private helpers or struct-only API
    "structs/bloom_filter",
    "structs/hashmap",
    "structs/lru_cache",
    # graph/algorithms — needs Graph param (in SKIP_PARAM_TYPES)
    "graph/algorithms",
    # automata — struct-only API
    "automata/state_machine",
    # data/dataframe — struct-heavy
    "data/dataframe",
}


class LibEntry:
    """One Mojo library to benchmark."""

    def __init__(self, path: Path, import_path: str, lib_id: str):
        self.path = path  # absolute .mojo file path
        self.import_path = import_path  # e.g. "accounting" or "crypto.hmac"
        self.lib_id = lib_id  # safe identifier for filenames, e.g. "crypto_hmac"


def get_benchmark_inventory_breakdown(libs: list[LibEntry]) -> dict[str, Any]:
    """Return dynamic benchmark-inventory counts for the current Mojo tree."""
    top_level_library_count = 0
    nested_library_count = 0
    group_counts: dict[str, int] = {}

    for entry in libs:
        if "." in entry.import_path:
            nested_library_count += 1
            group = entry.import_path.split(".", 1)[0]
        else:
            top_level_library_count += 1
            group = "top_level"
        group_counts[group] = group_counts.get(group, 0) + 1

    return {
        "kind": "benchmark_discovery_inventory",
        "total_libraries": len(libs),
        "top_level_library_count": top_level_library_count,
        "nested_library_count": nested_library_count,
        "group_counts": dict(sorted(group_counts.items())),
    }


def get_all_libs() -> list[LibEntry]:
    """Collect all domain libraries (top-level + subdirectories)."""
    entries: list[LibEntry] = []

    # 1. Top-level libraries
    for p in sorted(MOJO_DIR.glob("*.mojo")):
        if p.stem in SKIP_FILES:
            continue
        if ONLY_LIBS and p.stem not in ONLY_LIBS:
            continue
        entries.append(LibEntry(p, p.stem, p.stem))

    # 2. Subdirectory libraries (one level deep)
    for p in sorted(MOJO_DIR.glob("*/*.mojo")):
        subdir = p.parent.name
        rel = f"{subdir}/{p.stem}"
        if p.stem in SKIP_FILES or rel in SKIP_SUBDIR_FILES:
            continue
        import_path = f"{subdir}.{p.stem}"
        lib_id = f"{subdir}_{p.stem}"
        if ONLY_LIBS and lib_id not in ONLY_LIBS and p.stem not in ONLY_LIBS:
            continue
        entries.append(LibEntry(p, import_path, lib_id))

    return entries


def get_shipping_runtime_contract_counts() -> dict[str, int | str]:
    """Return the current signed LLM rollout inventory derived from the rollout matrix."""
    return {
        "kind": "shipping_runtime_contract",
        "module_count": len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE),
        "function_count": sum(
            len(functions) for functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.values()
        ),
    }


_ROLLOUT_PUBLIC_FUNCTION_MODULE_ALIASES = {
    "text_tokenizer": "text.tokenizer",
    "vector_kernels_ranker": "vector_kernels.ranker",
    "vector_kernels_table": "vector_kernels.table",
}


def _rollout_public_benchmark_functions(lib: str) -> frozenset[str] | None:
    runtime_module = _ROLLOUT_PUBLIC_FUNCTION_MODULE_ALIASES.get(lib, lib)
    functions = LLM_ROLLOUT_FUNCTIONS_BY_MODULE.get(runtime_module)
    if functions is None:
        return None
    return frozenset(functions)


def _filter_testable_functions_for_library(lib: str, fns: list[FnInfo]) -> list[FnInfo]:
    allowed = _rollout_public_benchmark_functions(lib)
    if allowed is None:
        return fns
    return [fn for fn in fns if fn.name in allowed]


# Per-function safe test arguments (avoid NaN/Inf singularities)
_PARAM_OVERRIDES: dict[tuple[str, str], list[str]] = {
    ("cryogenics", "carnot_cop_cooling"): ["200.0", "300.0"],
    ("pharmacokinetics", "time_to_peak"): ["0.8", "0.2"],
    ("pharmacokinetics", "one_compartment_oral"): ["100.0", "0.8", "0.2", "10.0", "2.0"],
    ("seismology", "epicenter_distance_from_ts_tp"): ["2.0", "3.5", "6.0"],
    ("semiconductors", "junction_capacitance"): ["1e-12", "0.3", "0.7", "0.5"],
    ("insurance", "gross_premium"): ["100.0", "0.2", "0.1"],
    ("geomorphology", "shields_parameter"): ["5.0", "2650.0", "1000.0", "9.81", "0.01"],
    ("geomorphology", "hypsometric_integral"): ["500.0", "100.0", "1000.0"],
    ("root_finding", "regula_falsi"): ["-1.0", "1.0", "0"],
    # correlation: cholesky needs positive-definite matrix + correct n
    ("correlation", "cholesky_lower"): ["[[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]]", "3"],
    ("correlation", "sample_correlated_normal"): [
        "[[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]]",
        "3",
    ],
    ("color", "hex_to_rgb"): ['"#336699"'],
    ("color_check", "wcag_relative_luminance_hex"): ['"#808080"'],
    ("color_check", "wcag_contrast_ratio_hex"): ['"#000000"', '"#FFFFFF"'],
    ("color_check", "wcag_text_pass_hex"): ['"#000000"', '"#FFFFFF"', "12.0", "False"],
    ("color_check", "preferred_text_color_hex"): ['"#336699"'],
    ("color_check", "dominant_background_rgb255"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4"],
    ("color_check", "dominant_background_hex"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4"],
    ("color_check", "dominant_background_contrast_ratio_hex"): [
        _COLOR_CHECK_IMAGE_2X2_EXPR,
        "2",
        "2",
        "4",
        '"#FFFFFF"',
    ],
    ("color_check", "dominant_background_wcag_pass_hex"): [
        _COLOR_CHECK_IMAGE_2X2_EXPR,
        "2",
        "2",
        "4",
        '"#FFFFFF"',
        "12.0",
        "False",
    ],
    ("color_check", "preferred_text_color_for_image"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4"],
    ("color_check", "preferred_text_contrast_for_image"): [
        _COLOR_CHECK_IMAGE_2X2_EXPR,
        "2",
        "2",
        "4",
    ],
    ("color_check", "preferred_text_pass_for_image"): [
        _COLOR_CHECK_IMAGE_2X2_EXPR,
        "2",
        "2",
        "4",
        "12.0",
        "False",
    ],
    ("image_palette", "dominant_palette_rgb255"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4", "2"],
    ("image_palette", "palette_size_estimate"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4", "0.2"],
    ("image_palette", "palette_entropy"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4"],
    ("image_palette", "mean_saturation_rgb255"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2"],
    ("image_palette", "warm_color_ratio_rgb255"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "0.25"],
    ("image_palette", "palette_contrast_score"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4", "2"],
    ("image_palette", "accent_color_hex"): [_COLOR_CHECK_IMAGE_2X2_EXPR, "2", "2", "4"],
    ("image_palette", "is_monochrome_palette"): [
        _COLOR_CHECK_IMAGE_2X2_EXPR,
        "2",
        "2",
        "4",
        "0.2",
        "0.15",
    ],
    ("image_ops", "convolve_2d"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]", "[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]"],
    ("image_ops", "histogram"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]", "5"],
    ("image_ops", "threshold"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]", "0.5"],
    ("image_ops", "invert"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]"],
    ("image_ops", "brightness"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]", "0.5"],
    ("image_ops", "contrast"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]", "0.5"],
    ("image_ops", "mean_pixel"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]"],
    ("video_ops", "frame_count_from_flat"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_ops", "frame_mean_intensity"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "1"],
    ("video_ops", "frame_mean_intensities"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_ops", "frame_mean_abs_diff"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0", "1"],
    ("video_ops", "temporal_mean_abs_diff"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_ops", "temporal_max_abs_diff"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_ops", "freeze_frame_ratio"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "50.0"],
    ("video_ops", "sample_frame_indices"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "2"],
    ("video_features", "scene_change_scores"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_features", "scene_cut_count"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4"],
    ("video_features", "scene_cut_rate"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4"],
    ("video_features", "peak_motion_frame"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_features", "keyframe_indices"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4", "4"],
    ("video_storyboard", "scene_start_indices"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4"],
    ("video_storyboard", "scene_end_indices"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4"],
    ("video_storyboard", "scene_lengths_frames"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4"],
    ("video_storyboard", "scene_representative_frames"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4"],
    ("video_storyboard", "longest_scene_index"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "0.4"],
    ("video_storyboard", "storyboard_frame_indices"): [
        _VIDEO_3X4X4_EXPR,
        "4",
        "4",
        "1",
        "0.4",
        "2",
    ],
    ("video_color", "frame_mean_rgb255"): [_VIDEO_RGB_3X2X2_EXPR, "2", "2", "3", "1"],
    ("video_color", "frame_mean_rgb_series"): [_VIDEO_RGB_3X2X2_EXPR, "2", "2", "3"],
    ("video_color", "clip_mean_rgb255"): [_VIDEO_RGB_3X2X2_EXPR, "2", "2", "3"],
    ("video_color", "dominant_clip_color_rgb255"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "4",
        "3",
    ],
    ("video_color", "clip_mean_saturation_rgb255"): [_VIDEO_RGB_3X2X2_EXPR, "2", "2", "3"],
    ("video_color", "warm_frame_ratio_rgb255"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "0.25",
    ],
    ("video_color", "color_drift_score_rgb255"): [_VIDEO_RGB_3X2X2_EXPR, "2", "2", "3"],
    ("video_color", "preferred_text_contrast_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "4",
        "3",
    ],
    ("video_color", "preferred_text_color_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "4",
        "3",
    ],
    ("video_accessibility", "frame_min_preferred_text_contrast_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "1",
    ],
    ("video_accessibility", "frame_preferred_text_color_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "1",
    ],
    ("video_accessibility", "sampled_video_min_text_contrast"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "3",
    ],
    ("video_accessibility", "sampled_video_wcag_safe_ratio"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "3",
        "16.0",
        "False",
    ],
    ("video_accessibility", "needs_text_backplate_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "3",
        "16.0",
        "False",
    ],
    ("video_accessibility", "subtitle_band_min_preferred_text_contrast_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "3",
        "1",
    ],
    ("video_accessibility", "subtitle_band_preferred_text_color_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "3",
        "1",
    ],
    ("video_accessibility", "sampled_subtitle_band_wcag_safe_ratio"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "3",
        "1",
        "16.0",
        "False",
    ],
    ("video_accessibility", "subtitle_band_needs_backplate_for_video"): [
        _VIDEO_RGB_3X2X2_EXPR,
        "2",
        "2",
        "3",
        "3",
        "1",
        "16.0",
        "False",
    ],
    ("video_quality", "frame_quality_series"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "3"],
    ("video_quality", "average_frame_quality"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "3"],
    ("video_quality", "brightness_flicker_score"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_quality", "temporal_stability_score"): [_VIDEO_3X4X4_EXPR, "4", "4", "1"],
    ("video_quality", "video_quality_score"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "3"],
    ("video_quality", "is_usable_video"): [_VIDEO_3X4X4_EXPR, "4", "4", "1", "3", "0.35"],
    ("image_morphology", "binary_erode_flat"): [_BLOCK_5X5_EXPR, "5", "5", "3", "128.0"],
    ("image_morphology", "binary_dilate_flat"): [_BLOCK_5X5_EXPR, "5", "5", "3", "128.0"],
    ("image_morphology", "binary_open_flat"): [_BLOCK_5X5_EXPR, "5", "5", "3", "128.0"],
    ("image_morphology", "binary_close_flat"): [_RING_5X5_EXPR, "5", "5", "3", "128.0"],
    ("image_morphology", "binary_fill_holes_flat"): [_RING_5X5_EXPR, "5", "5", "128.0"],
    ("image_morphology", "connected_components_4_flat"): [_COMPONENTS_6X6_EXPR, "6", "6", "128.0"],
    ("image_morphology", "largest_component_bbox_flat"): [_COMPONENTS_6X6_EXPR, "6", "6", "128.0"],
    ("image_morphology", "distance_transform_cityblock_flat"): [_BLOCK_5X5_EXPR, "5", "5", "128.0"],
    ("image_morphology", "foreground_area_ratio_flat"): [_BLOCK_5X5_EXPR, "5", "5", "128.0"],
    ("document_vision", "otsu_threshold_flat"): [_DOC_8X8_EXPR, "8", "8"],
    ("document_vision", "binarize_otsu_flat"): [_DOC_8X8_EXPR, "8", "8"],
    ("document_vision", "adaptive_mean_binarize_flat"): [_ADAPTIVE_DOC_6X6_EXPR, "6", "6", "1", "20.0"],
    ("document_vision", "horizontal_projection"): [_DOC_MASK_8X8_EXPR, "8", "8", "128.0"],
    ("document_vision", "vertical_projection"): [_DOC_MASK_8X8_EXPR, "8", "8", "128.0"],
    ("document_vision", "mask_content_bbox_flat"): [_DOC_MASK_8X8_EXPR, "8", "8", "128.0"],
    ("document_vision", "skew_angle_estimate_flat"): [_SKEW_MASK_6X6_EXPR, "6", "6", "128.0"],
    ("document_vision", "horizontal_text_score_flat"): [_DOC_MASK_8X8_EXPR, "8", "8", "128.0"],
    ("document_vision", "document_scan_quality_flat"): [_DOC_8X8_EXPR, "8", "8"],
    ("document_layout", "text_line_boxes_flat"): [_DOC_MASK_8X8_EXPR, "8", "8", "128.0", "1"],
    ("document_layout", "line_count_flat"): [_DOC_MASK_8X8_EXPR, "8", "8", "128.0", "1"],
    ("document_layout", "column_boxes_flat"): [_DOC_COLUMNS_8X8_EXPR, "8", "8", "128.0", "2"],
    ("document_layout", "column_count_flat"): [_DOC_COLUMNS_8X8_EXPR, "8", "8", "128.0", "2"],
    ("document_layout", "text_density_grid_flat"): [_DOC_MASK_8X8_EXPR, "8", "8", "128.0", "2", "2"],
    ("document_layout", "multi_column_score_flat"): [_DOC_COLUMNS_8X8_EXPR, "8", "8", "128.0"],
    ("document_layout", "table_like_score_flat"): [_DOC_TABLE_9X9_EXPR, "9", "9", "128.0"],
    ("image_similarity", "mean_squared_error_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8"],
    ("image_similarity", "mean_abs_error_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8"],
    ("image_similarity", "psnr_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8", "255.0"],
    ("image_similarity", "normalized_cross_correlation_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8"],
    ("image_similarity", "ssim_global_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8"],
    ("image_similarity", "diff_fraction_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8", "5.0"],
    ("image_similarity", "crop_region_similarity_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8", "2", "2", "5", "5"],
    ("image_similarity", "duplicate_score_flat"): [_DOC_8X8_EXPR, _DOC_8X8_ALT_EXPR, "8", "8"],
    ("image_regions", "foreground_mask_otsu_flat"): [_BLOB_DOC_8X8_EXPR, "8", "8"],
    ("image_regions", "connected_component_boxes_flat"): [_COMPONENTS_6X6_EXPR, "6", "6", "128.0", "4"],
    ("image_regions", "largest_foreground_box_flat"): [_BLOB_DOC_8X8_EXPR, "8", "8"],
    ("image_regions", "saliency_box_flat"): [_TEXTURE_16X16_EXPR, "16", "16", "2", "2"],
    ("image_regions", "extract_box_flat"): [_GRID_4X4_EXPR, "4", "4", "1", "1", "2", "2"],
    ("image_regions", "box_iou"): [_BOX_A_EXPR, _BOX_B_EXPR],
    ("video_regions", "frame_diff_mask_flat"): [_VIDEO_MOTION_3X5X5_EXPR, "5", "5", "1", "0", "1", "50.0"],
    ("video_regions", "motion_boxes_between_frames"): [
        _VIDEO_MOTION_3X5X5_EXPR,
        "5",
        "5",
        "1",
        "0",
        "1",
        "50.0",
        "4",
    ],
    ("video_regions", "largest_motion_box_between_frames"): [
        _VIDEO_MOTION_3X5X5_EXPR,
        "5",
        "5",
        "1",
        "1",
        "2",
        "50.0",
    ],
    ("video_regions", "temporal_motion_area_series"): [_VIDEO_MOTION_3X5X5_EXPR, "5", "5", "1", "50.0"],
    ("video_regions", "peak_motion_box_flat"): [_VIDEO_MOTION_3X5X5_EXPR, "5", "5", "1", "50.0"],
    ("video_regions", "temporal_union_motion_box_flat"): [_VIDEO_MOTION_3X5X5_EXPR, "5", "5", "1", "50.0"],
    ("video_regions", "motion_coverage_ratio_flat"): [_VIDEO_MOTION_3X5X5_EXPR, "5", "5", "1", "50.0"],
    ("video_similarity", "frame_duplicate_scores"): [
        _VIDEO_3X4X4_EXPR,
        _VIDEO_3X4X4_ALT_EXPR,
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "average_frame_duplicate_score"): [
        _VIDEO_3X4X4_EXPR,
        _VIDEO_3X4X4_ALT_EXPR,
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "frame_hash_hamming_series"): [
        _VIDEO_3X4X4_EXPR,
        _VIDEO_3X4X4_ALT_EXPR,
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "average_frame_hash_hamming"): [
        _VIDEO_3X4X4_EXPR,
        _VIDEO_3X4X4_ALT_EXPR,
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "temporal_signature_distance"): [
        _VIDEO_3X4X4_EXPR,
        _VIDEO_3X4X4_ALT_EXPR,
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "clip_duplicate_score_flat"): [
        _VIDEO_3X4X4_EXPR,
        _VIDEO_3X4X4_ALT_EXPR,
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "is_duplicate_clip_flat"): [
        _VIDEO_3X4X4_EXPR,
        _VIDEO_3X4X4_ALT_EXPR,
        "4",
        "4",
        "1",
        "0.85",
    ],
    # scheduling_algo: processes = [arrival, burst, priority]; results = [pid, start, finish, wait]
    ("scheduling_algo", "fcfs"): ["[[0,3,1],[1,5,2],[2,2,3]]"],
    ("scheduling_algo", "sjf"): ["[[0,3,1],[1,5,2],[2,2,3]]"],
    ("scheduling_algo", "priority_scheduling"): ["[[0,3,1],[1,5,2],[2,2,3]]"],
    ("scheduling_algo", "round_robin"): ["[[0,3,1],[1,5,2],[2,2,3]]", "2"],
    ("scheduling_algo", "avg_wait_time"): ["[[0,0,3,1],[1,3,8,2],[2,8,10,1]]"],
    ("scheduling_algo", "avg_turnaround"): ["[[0,0,3,1],[1,3,8,2],[2,8,10,1]]"],
    ("scheduling_algo", "throughput"): ["[[0,0,3,1],[1,3,8,2],[2,8,10,1]]", "10"],
    ("scheduling_algo", "cpu_utilization"): ["[[0,0,3,1],[1,3,8,2],[2,8,10,1]]", "10"],
    ("scheduling_algo", "gantt_chart"): ["[[0,0,3,1],[1,3,8,2],[2,8,10,1]]"],
    # dimensionality: n_components must be ≤ n_features
    ("dimensionality", "pca"): ["[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]", "2"],
    # linalg: Matrix functions that need a Matrix arg (so they appear in linalg.py)
    ("linalg", "mat_add"): [
        "mat_from_list([1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0],3,3)",
        "mat_from_list([1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0],3,3)",
    ],
    ("linalg", "mat_sub"): [
        "mat_from_list([1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0],3,3)",
        "mat_from_list([1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0],3,3)",
    ],
    ("linalg", "mat_mul"): [
        "mat_from_list([1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0],3,3)",
        "mat_from_list([1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0],3,3)",
    ],
    ("linalg", "mat_scale"): ["mat_from_list([1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0],3,3)", "2.0"],
    ("linalg", "mat_transpose"): ["mat_from_list([1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0],3,3)"],
    ("linalg", "mat_det"): ["mat_from_list([4.0,2.0,0.0,2.0,3.0,0.0,0.0,0.0,1.0],3,3)"],
    ("linalg", "mat_inv"): ["mat_from_list([4.0,2.0,0.0,2.0,3.0,0.0,0.0,0.0,1.0],3,3)"],
    ("linalg", "mat_norm_frobenius"): ["mat_from_list([1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0],3,3)"],
    ("linalg", "mat_trace"): ["mat_from_list([1.0,0.0,0.0,0.0,2.0,0.0,0.0,0.0,3.0],3,3)"],
    ("linalg", "vec_dot"): ["[0.5,0.6,0.7,0.4,0.3]", "[0.5,0.6,0.7,0.4,0.3]"],
    ("linalg", "vec_norm"): ["[0.5,0.6,0.7,0.4,0.3]"],
    # linalg_ext: Matrix comes from linalg module; use mat_from_list to construct
    ("linalg_ext", "mat_norm_frobenius"): [
        "mat_from_list([1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0],3,3)"
    ],
    ("linalg_ext", "mat_norm_inf"): ["mat_from_list([1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0],3,3)"],
    ("linalg_ext", "mat_trace"): ["mat_from_list([1.0,0.0,0.0,0.0,2.0,0.0,0.0,0.0,3.0],3,3)"],
    ("linalg_ext", "mat_is_symmetric"): [
        "mat_from_list([1.0,2.0,3.0,2.0,5.0,6.0,3.0,6.0,9.0],3,3)",
        "1e-10",
    ],
    ("linalg_ext", "mat_is_positive_definite"): [
        "mat_from_list([4.0,2.0,0.0,2.0,3.0,0.0,0.0,0.0,1.0],3,3)"
    ],
    ("linalg_ext", "mat_power_iteration"): [
        "mat_from_list([4.0,1.0,0.0,1.0,3.0,0.0,0.0,0.0,2.0],3,3)",
        "100",
    ],
    ("linalg_ext", "mat_condition_number"): [
        "mat_from_list([4.0,1.0,0.0,1.0,3.0,0.0,0.0,0.0,2.0],3,3)"
    ],
    # recommender: ratings matrix, user/item indices must be within bounds
    ("recommender", "cosine_sim_users"): ["[[4.0,0.0,5.0],[0.0,3.0,4.0],[3.0,4.0,0.0]]", "0", "1"],
    ("recommender", "predict_rating"): [
        "[[4.0,0.0,5.0],[0.0,3.0,4.0],[3.0,4.0,0.0]]",
        "0",
        "2",
        "2",
    ],
    ("recommender", "popularity_ranking"): ["[[4.0,0.0,5.0],[0.0,3.0,4.0],[3.0,4.0,0.0]]"],
    ("recommender", "mean_rating_per_item"): ["[[4.0,0.0,5.0],[0.0,3.0,4.0],[3.0,4.0,0.0]]"],
    ("recommender", "mean_rating_per_user"): ["[[4.0,0.0,5.0],[0.0,3.0,4.0],[3.0,4.0,0.0]]"],
    ("recommender", "item_overlap"): ["[[4.0,0.0,5.0],[0.0,3.0,4.0],[3.0,4.0,0.0]]", "0", "1"],
    ("recommender", "cold_start_recommend"): ["[[4.0,0.0,5.0],[0.0,3.0,4.0],[3.0,4.0,0.0]]", "2"],
    ("recommender", "rmse_ratings"): ["[0.5,0.6,0.7,0.4,0.3]", "[0.5,0.6,0.7,0.4,0.3]"],
    # geometry: Point struct with x, y fields
    ("geometry", "distance_2d"): ["Point(0.0,0.0)", "Point(3.0,4.0)"],
    ("geometry", "cross_product_2d"): ["Point(0.0,0.0)", "Point(1.0,0.0)", "Point(0.0,1.0)"],
    ("geometry", "point_in_polygon"): [
        "Point(0.5,0.5)",
        "[Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]",
    ],
    ("geometry", "polygon_area"): ["[Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]"],
    ("geometry", "polygon_perimeter"): [
        "[Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]"
    ],
    ("geometry", "convex_hull"): ["[Point(0.0,0.0),Point(1.0,0.0),Point(0.5,1.0),Point(0.5,0.5)]"],
    ("geometry", "line_intersection"): [
        "Point(0.0,0.0)",
        "Point(1.0,1.0)",
        "Point(1.0,0.0)",
        "Point(0.0,1.0)",
    ],
    ("geometry", "centroid"): ["[Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]"],
    ("geometry", "bounding_box"): ["[Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]"],
    # trie: Trie struct with no-arg constructor; functions mutate it
    ("trie", "trie_count_words"): ["Trie()"],
    ("trie", "trie_count_nodes"): ["Trie()"],
    ("trie", "trie_word_list"): ["Trie()"],
    # LLM rollout fixtures
    (
        "vector_kernels_ranker",
        "run_column_rank_v2",
    ): [
        '\'{"query":{"name":"unit_price","role_hint":"unit_measure","source":"POS"},"candidates":[{"source":"POS","name":"unit_price"},{"source":"POS","name":"extended_price"},{"source":"INVOICE","name":"invoice_total"}],"top_k":2}\''
    ],
    (
        "vector_kernels_table",
        "build_table_json",
    ): [
        '\'[{"id":1,"source":"POS","role":"unit_measure","name":"unit_price"},{"id":2,"source":"BACKLOG","role":"derived_measure","name":"extended_price"},{"id":3,"source":"INVOICE","role":"derived_measure","name":"invoice_total"}]\''
    ],
    ("vector_kernels_table", "build_query"): ['"unit_price"', "1", "1", "2"],
    ("vector_kernels_table", "source_id_of"): ['"POS"'],
    ("vector_kernels_table", "role_id_of"): ['"unit_measure"'],
    ("sparse_attention", "bigbird_random_block_select"): ["1.0", "8.0", "3.0", "2.0"],
    ("rlhf_dpo", "orpo_ratio"): ["-0.2", "-1.2", "5.0", "5.0", "0.1"],
}

# Mojo-specific arg overrides (replaces _PARAM_OVERRIDES value for Mojo bench only)
# Use pre-built vars (e.g. _llf3) to avoid per-iteration allocation overhead
_MOJO_PARAM_OVERRIDES: dict[tuple[str, str], list[str]] = {
    # linalg: use pre-built _mat3 Matrix to avoid per-iteration mat_from_list allocation
    ("linalg", "mat_add"): ["_mat3", "_mat3"],
    ("linalg", "mat_sub"): ["_mat3", "_mat3"],
    ("linalg", "mat_mul"): ["_mat3", "_mat3"],
    ("linalg", "mat_scale"): ["_mat3", "2.0"],
    ("linalg", "mat_transpose"): ["_mat3"],
    ("linalg", "mat_det"): ["_mat3"],
    ("linalg", "mat_inv"): ["_mat3"],
    ("linalg", "mat_norm_frobenius"): ["_mat3"],
    ("linalg", "mat_trace"): ["_mat3"],
    ("linalg", "vec_dot"): ["_lf5", "_lf5"],
    ("linalg", "vec_norm"): ["_lf5"],
    # linalg_ext: use mat_from_list to build Matrix once (pre-built in bench preamble)
    ("linalg_ext", "mat_norm_frobenius"): ["_mat3"],
    ("linalg_ext", "mat_norm_inf"): ["_mat3"],
    ("linalg_ext", "mat_trace"): ["_mat3"],
    ("linalg_ext", "mat_is_symmetric"): ["_mat3", "1e-10"],
    ("linalg_ext", "mat_is_positive_definite"): ["_mat3"],
    ("linalg_ext", "mat_power_iteration"): ["_mat3", "100"],
    ("linalg_ext", "mat_condition_number"): ["_mat3"],
    # recommender: use pre-built _llf3 matrix to avoid per-iteration list allocation
    ("recommender", "cosine_sim_users"): ["_llf3", "0", "1"],
    ("recommender", "predict_rating"): ["_llf3", "0", "2", "2"],
    ("recommender", "popularity_ranking"): ["_llf3"],
    ("recommender", "mean_rating_per_item"): ["_llf3"],
    ("recommender", "mean_rating_per_user"): ["_llf3"],
    ("recommender", "item_overlap"): ["_llf3", "0", "1"],
    ("recommender", "cold_start_recommend"): ["_llf3", "2"],
    ("recommender", "rmse_ratings"): ["_lf5", "_lf5"],
    ("image_ops", "convolve_2d"): ["_llf3_imageops", "_llf3_imageops"],
    ("image_ops", "histogram"): ["_llf3_imageops", "5"],
    ("image_ops", "threshold"): ["_llf3_imageops", "0.5"],
    ("image_ops", "invert"): ["_llf3_imageops"],
    ("image_ops", "brightness"): ["_llf3_imageops", "0.5"],
    ("image_ops", "contrast"): ["_llf3_imageops", "0.5"],
    ("image_ops", "mean_pixel"): ["_llf3_imageops"],
    ("color_check", "dominant_background_rgb255"): ["_lf12_colorcheck2x2", "2", "2", "4"],
    ("color_check", "dominant_background_hex"): ["_lf12_colorcheck2x2", "2", "2", "4"],
    ("color_check", "dominant_background_contrast_ratio_hex"): [
        "_lf12_colorcheck2x2",
        "2",
        "2",
        "4",
        '"#FFFFFF"',
    ],
    ("color_check", "dominant_background_wcag_pass_hex"): [
        "_lf12_colorcheck2x2",
        "2",
        "2",
        "4",
        '"#FFFFFF"',
        "12.0",
        "False",
    ],
    ("color_check", "preferred_text_color_for_image"): ["_lf12_colorcheck2x2", "2", "2", "4"],
    ("color_check", "preferred_text_contrast_for_image"): ["_lf12_colorcheck2x2", "2", "2", "4"],
    ("color_check", "preferred_text_pass_for_image"): [
        "_lf12_colorcheck2x2",
        "2",
        "2",
        "4",
        "12.0",
        "False",
    ],
    ("image_palette", "dominant_palette_rgb255"): ["_lf12_colorcheck2x2", "2", "2", "4", "2"],
    ("image_palette", "palette_size_estimate"): ["_lf12_colorcheck2x2", "2", "2", "4", "0.2"],
    ("image_palette", "palette_entropy"): ["_lf12_colorcheck2x2", "2", "2", "4"],
    ("image_palette", "mean_saturation_rgb255"): ["_lf12_colorcheck2x2", "2", "2"],
    ("image_palette", "warm_color_ratio_rgb255"): ["_lf12_colorcheck2x2", "2", "2", "0.25"],
    ("image_palette", "palette_contrast_score"): ["_lf12_colorcheck2x2", "2", "2", "4", "2"],
    ("image_palette", "accent_color_hex"): ["_lf12_colorcheck2x2", "2", "2", "4"],
    ("image_palette", "is_monochrome_palette"): [
        "_lf12_colorcheck2x2",
        "2",
        "2",
        "4",
        "0.2",
        "0.15",
    ],
    ("video_ops", "frame_count_from_flat"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_ops", "frame_mean_intensity"): ["_lf48_video3x4x4", "4", "4", "1", "1"],
    ("video_ops", "frame_mean_intensities"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_ops", "frame_mean_abs_diff"): ["_lf48_video3x4x4", "4", "4", "1", "0", "1"],
    ("video_ops", "temporal_mean_abs_diff"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_ops", "temporal_max_abs_diff"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_ops", "freeze_frame_ratio"): ["_lf48_video3x4x4", "4", "4", "1", "50.0"],
    ("video_ops", "sample_frame_indices"): ["_lf48_video3x4x4", "4", "4", "1", "2"],
    ("video_features", "scene_change_scores"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_features", "scene_cut_count"): ["_lf48_video3x4x4", "4", "4", "1", "0.4"],
    ("video_features", "scene_cut_rate"): ["_lf48_video3x4x4", "4", "4", "1", "0.4"],
    ("video_features", "peak_motion_frame"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_features", "keyframe_indices"): ["_lf48_video3x4x4", "4", "4", "1", "0.4", "4"],
    ("video_storyboard", "scene_start_indices"): ["_lf48_video3x4x4", "4", "4", "1", "0.4"],
    ("video_storyboard", "scene_end_indices"): ["_lf48_video3x4x4", "4", "4", "1", "0.4"],
    ("video_storyboard", "scene_lengths_frames"): ["_lf48_video3x4x4", "4", "4", "1", "0.4"],
    ("video_storyboard", "scene_representative_frames"): ["_lf48_video3x4x4", "4", "4", "1", "0.4"],
    ("video_storyboard", "longest_scene_index"): ["_lf48_video3x4x4", "4", "4", "1", "0.4"],
    ("video_storyboard", "storyboard_frame_indices"): [
        "_lf48_video3x4x4",
        "4",
        "4",
        "1",
        "0.4",
        "2",
    ],
    ("video_color", "frame_mean_rgb255"): ["_lf36_video_rgb3x2x2", "2", "2", "3", "1"],
    ("video_color", "frame_mean_rgb_series"): ["_lf36_video_rgb3x2x2", "2", "2", "3"],
    ("video_color", "clip_mean_rgb255"): ["_lf36_video_rgb3x2x2", "2", "2", "3"],
    ("video_color", "dominant_clip_color_rgb255"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "4",
        "3",
    ],
    ("video_color", "clip_mean_saturation_rgb255"): ["_lf36_video_rgb3x2x2", "2", "2", "3"],
    ("video_color", "warm_frame_ratio_rgb255"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "0.25",
    ],
    ("video_color", "color_drift_score_rgb255"): ["_lf36_video_rgb3x2x2", "2", "2", "3"],
    ("video_color", "preferred_text_contrast_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "4",
        "3",
    ],
    ("video_color", "preferred_text_color_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "4",
        "3",
    ],
    ("video_accessibility", "frame_min_preferred_text_contrast_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "1",
    ],
    ("video_accessibility", "frame_preferred_text_color_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "1",
    ],
    ("video_accessibility", "sampled_video_min_text_contrast"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "3",
    ],
    ("video_accessibility", "sampled_video_wcag_safe_ratio"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "3",
        "16.0",
        "False",
    ],
    ("video_accessibility", "needs_text_backplate_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "3",
        "16.0",
        "False",
    ],
    ("video_accessibility", "subtitle_band_min_preferred_text_contrast_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "3",
        "1",
    ],
    ("video_accessibility", "subtitle_band_preferred_text_color_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "3",
        "1",
    ],
    ("video_accessibility", "sampled_subtitle_band_wcag_safe_ratio"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "3",
        "1",
        "16.0",
        "False",
    ],
    ("video_accessibility", "subtitle_band_needs_backplate_for_video"): [
        "_lf36_video_rgb3x2x2",
        "2",
        "2",
        "3",
        "3",
        "1",
        "16.0",
        "False",
    ],
    ("video_quality", "frame_quality_series"): ["_lf48_video3x4x4", "4", "4", "1", "3"],
    ("video_quality", "average_frame_quality"): ["_lf48_video3x4x4", "4", "4", "1", "3"],
    ("video_quality", "brightness_flicker_score"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_quality", "temporal_stability_score"): ["_lf48_video3x4x4", "4", "4", "1"],
    ("video_quality", "video_quality_score"): ["_lf48_video3x4x4", "4", "4", "1", "3"],
    ("video_quality", "is_usable_video"): ["_lf48_video3x4x4", "4", "4", "1", "3", "0.35"],
    ("image_morphology", "binary_erode_flat"): ["_lf25_block5x5", "5", "5", "3", "128.0"],
    ("image_morphology", "binary_dilate_flat"): ["_lf25_block5x5", "5", "5", "3", "128.0"],
    ("image_morphology", "binary_open_flat"): ["_lf25_block5x5", "5", "5", "3", "128.0"],
    ("image_morphology", "binary_close_flat"): ["_lf25_ring5x5", "5", "5", "3", "128.0"],
    ("image_morphology", "binary_fill_holes_flat"): ["_lf25_ring5x5", "5", "5", "128.0"],
    ("image_morphology", "connected_components_4_flat"): ["_lf36_components6x6", "6", "6", "128.0"],
    ("image_morphology", "largest_component_bbox_flat"): ["_lf36_components6x6", "6", "6", "128.0"],
    ("image_morphology", "distance_transform_cityblock_flat"): ["_lf25_block5x5", "5", "5", "128.0"],
    ("image_morphology", "foreground_area_ratio_flat"): ["_lf25_block5x5", "5", "5", "128.0"],
    ("document_vision", "otsu_threshold_flat"): ["_lf64_doc8x8", "8", "8"],
    ("document_vision", "binarize_otsu_flat"): ["_lf64_doc8x8", "8", "8"],
    ("document_vision", "adaptive_mean_binarize_flat"): ["_lf36_adaptive_doc6x6", "6", "6", "1", "20.0"],
    ("document_vision", "horizontal_projection"): ["_lf64_docmask8x8", "8", "8", "128.0"],
    ("document_vision", "vertical_projection"): ["_lf64_docmask8x8", "8", "8", "128.0"],
    ("document_vision", "mask_content_bbox_flat"): ["_lf64_docmask8x8", "8", "8", "128.0"],
    ("document_vision", "skew_angle_estimate_flat"): ["_lf36_skewmask6x6", "6", "6", "128.0"],
    ("document_vision", "horizontal_text_score_flat"): ["_lf64_docmask8x8", "8", "8", "128.0"],
    ("document_vision", "document_scan_quality_flat"): ["_lf64_doc8x8", "8", "8"],
    ("document_layout", "text_line_boxes_flat"): ["_lf64_docmask8x8", "8", "8", "128.0", "1"],
    ("document_layout", "line_count_flat"): ["_lf64_docmask8x8", "8", "8", "128.0", "1"],
    ("document_layout", "column_boxes_flat"): ["_lf64_doccolumns8x8", "8", "8", "128.0", "2"],
    ("document_layout", "column_count_flat"): ["_lf64_doccolumns8x8", "8", "8", "128.0", "2"],
    ("document_layout", "text_density_grid_flat"): ["_lf64_docmask8x8", "8", "8", "128.0", "2", "2"],
    ("document_layout", "multi_column_score_flat"): ["_lf64_doccolumns8x8", "8", "8", "128.0"],
    ("document_layout", "table_like_score_flat"): ["_lf81_doctable9x9", "9", "9", "128.0"],
    ("image_similarity", "mean_squared_error_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8"],
    ("image_similarity", "mean_abs_error_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8"],
    ("image_similarity", "psnr_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8", "255.0"],
    ("image_similarity", "normalized_cross_correlation_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8"],
    ("image_similarity", "ssim_global_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8"],
    ("image_similarity", "diff_fraction_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8", "5.0"],
    ("image_similarity", "crop_region_similarity_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8", "2", "2", "5", "5"],
    ("image_similarity", "duplicate_score_flat"): ["_lf64_doc8x8", "_lf64_doc8x8_alt", "8", "8"],
    ("image_regions", "foreground_mask_otsu_flat"): ["_lf64_blobdoc8x8", "8", "8"],
    ("image_regions", "connected_component_boxes_flat"): ["_lf36_components6x6", "6", "6", "128.0", "4"],
    ("image_regions", "largest_foreground_box_flat"): ["_lf64_blobdoc8x8", "8", "8"],
    ("image_regions", "saliency_box_flat"): ["_lf256_texture16x16", "16", "16", "2", "2"],
    ("image_regions", "extract_box_flat"): ["_lf16_grid4x4", "4", "4", "1", "1", "2", "2"],
    ("image_regions", "box_iou"): ["_li4_box_a", "_li4_box_b"],
    ("video_regions", "frame_diff_mask_flat"): ["_lf75_video_motion3x5x5", "5", "5", "1", "0", "1", "50.0"],
    ("video_regions", "motion_boxes_between_frames"): [
        "_lf75_video_motion3x5x5",
        "5",
        "5",
        "1",
        "0",
        "1",
        "50.0",
        "4",
    ],
    ("video_regions", "largest_motion_box_between_frames"): [
        "_lf75_video_motion3x5x5",
        "5",
        "5",
        "1",
        "1",
        "2",
        "50.0",
    ],
    ("video_regions", "temporal_motion_area_series"): ["_lf75_video_motion3x5x5", "5", "5", "1", "50.0"],
    ("video_regions", "peak_motion_box_flat"): ["_lf75_video_motion3x5x5", "5", "5", "1", "50.0"],
    ("video_regions", "temporal_union_motion_box_flat"): ["_lf75_video_motion3x5x5", "5", "5", "1", "50.0"],
    ("video_regions", "motion_coverage_ratio_flat"): ["_lf75_video_motion3x5x5", "5", "5", "1", "50.0"],
    ("video_similarity", "frame_duplicate_scores"): [
        "_lf48_video3x4x4",
        "_lf48_video3x4x4_alt",
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "average_frame_duplicate_score"): [
        "_lf48_video3x4x4",
        "_lf48_video3x4x4_alt",
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "frame_hash_hamming_series"): [
        "_lf48_video3x4x4",
        "_lf48_video3x4x4_alt",
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "average_frame_hash_hamming"): [
        "_lf48_video3x4x4",
        "_lf48_video3x4x4_alt",
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "temporal_signature_distance"): [
        "_lf48_video3x4x4",
        "_lf48_video3x4x4_alt",
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "clip_duplicate_score_flat"): [
        "_lf48_video3x4x4",
        "_lf48_video3x4x4_alt",
        "4",
        "4",
        "1",
    ],
    ("video_similarity", "is_duplicate_clip_flat"): [
        "_lf48_video3x4x4",
        "_lf48_video3x4x4_alt",
        "4",
        "4",
        "1",
        "0.85",
    ],
}

SCALAR_VAL = "0.5"
INT_VAL = "5"
LIST_VALS = "[0.5, 0.6, 0.7, 0.4, 0.3]"
INT_LIST = "[0, 1, 2, 3, 4]"

SKIP_PARAM_TYPES = {
    "TTLCache",
    "Graph",
    "WeightedGraph",
    "Heap",
    "BloomFilter",
    "PetriNet",
    "KalmanState",
    "LRUCache",
    "CSVRow",
    "CSVResult",  # csv_parser — complex struct returns
}

# Type prefixes that can never be represented as Python values
_SKIP_TYPE_PREFIXES = ("UnsafePointer[", "Pointer[", "DTypePointer[")

# Extra __init__ lines for structs whose List fields need dynamic initialization
# Appended after the auto-generated field defaults (overrides the [] placeholder)
_STRUCT_INIT_EXTRAS: dict[tuple[str, str], list[str]] = {
    # Matrix.__init__(rows, cols) pre-allocates data = [0.0] * (rows * cols)
    ("linalg", "Matrix"): [
        "        self.data = [0.0] * (self.rows * self.cols)",
    ],
}

# Manual method stubs for structs whose methods can't be auto-transpiled
# (e.g. because they use Mojo-specific arithmetic without Python equivalents)
_STRUCT_MANUAL_METHODS: dict[tuple[str, str], list[str]] = {
    # SHA256: uses UInt32 wrapping arithmetic — use hashlib for Python side
    ("sha256", "SHA256"): [
        "    def update(self, data):\n"
        "        if not hasattr(self, '_hlib'):\n"
        "            import hashlib\n"
        "            self._hlib = hashlib.sha256()\n"
        "        self._hlib.update(data.encode() if isinstance(data, str) else bytes(data))\n",
        "    def hexdigest(self):\n"
        "        if not hasattr(self, '_hlib'): return ''\n"
        "        return self._hlib.hexdigest()\n",
    ],
}


# ── Mojo parser ────────────────────────────────────────────────────────────────


class Param:
    def __init__(
        self, name: str, typ: str, has_default: bool, is_mut: bool, default_val: str | None = None
    ):
        self.name = name
        self.typ = typ
        self.has_default = has_default
        self.is_mut = is_mut
        self.default_val = default_val  # Python-compatible default expression, or None


class FnInfo:
    def __init__(self, name: str, params: list[Param], ret: str, body_lines: list[str], lib: str):
        self.name = name
        self.params = params
        self.ret = ret
        self.body_lines = body_lines  # raw Mojo body lines
        self.lib = lib


def _clean_type(t: str) -> str:
    t = t.split("=")[0].strip()
    t = re.sub(r"\s+", " ", t)
    for prefix in ("owned ", "inout ", "ref ", "read ", "mut "):
        if t.startswith(prefix):
            t = t[len(prefix) :]
    return t.strip()


def _parse_params(raw: str) -> list[Param] | None:
    parts: list[str] = []
    depth = 0
    cur = ""
    for ch in raw:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        is_mut = bool(re.match(r"(mut|inout)\s+", p))
        m = re.match(r"(?:mut\s+|owned\s+|inout\s+)?(\w+)\s*:\s*(.+)", p)
        if not m:
            return None
        name = m.group(1)
        rest = m.group(2).strip()
        has_def = "=" in rest
        typ = _clean_type(rest)
        # Extract Python-compatible default value (e.g. 1e-10, True, "hello", "")
        default_val: str | None = None
        if has_def:
            eq_idx = rest.index("=")
            raw_dflt = rest[eq_idx + 1 :].strip()
            # Numeric scalar or bool
            if re.match(r"^[\d.e+\-]+$", raw_dflt) or raw_dflt in ("True", "False"):
                default_val = raw_dflt
            # String literals: "" or "some string"
            elif raw_dflt.startswith('"') and raw_dflt.endswith('"'):
                default_val = raw_dflt  # already valid Python string literal
        result.append(Param(name, typ, has_def, is_mut, default_val))
    return result


def parse_library(path: Path, lib_id: str | None = None) -> list[FnInfo]:
    lib = lib_id if lib_id is not None else path.stem
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fns: list[FnInfo] = []
    i = 0
    in_docstring = False
    while i < len(lines):
        stripped = lines[i].strip()
        # Track docstring state to avoid matching fn declarations inside docstrings
        if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
            quote = stripped[:3]
            rest = stripped[3:]
            if (quote in rest) or (stripped.count(quote) >= 2 and len(stripped) > 3):
                pass  # single-line docstring, no state change
            else:
                in_docstring = True
                i += 1
                continue
        elif in_docstring:
            if '"""' in stripped or "'''" in stripped:
                in_docstring = False
            i += 1
            continue
        # Only match top-level (unindented) function definitions — skip nested closures
        if lines[i] and lines[i][0].isspace():
            i += 1
            continue
        m = re.match(r"(?:fn|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", stripped)
        if not m:
            i += 1
            continue
        fname = m.group(1)

        # Collect signature: single-line ends with ':', multi-line continues
        sig_lines = [stripped]
        body_start = i + 1
        if not stripped.rstrip().endswith(":"):
            # Multi-line signature — collect until ':' terminator
            j = i + 1
            while j < min(i + 15, len(lines)):
                nxt = lines[j].strip()
                if re.match(r"(fn|def|struct|from|var|let)\s", nxt):
                    break
                sig_lines.append(nxt)
                j += 1
                if nxt.rstrip().endswith(":") or (
                    re.search(r"->\s*\w", nxt) and nxt.rstrip().endswith(":")
                ):
                    break
                # Check if this line ends the sig (has ')' and '-> ...')
                if re.search(r"\)\s*->\s*\w[\w\[\], ]*\s*:$", nxt):
                    break
            body_start = j  # j already incremented past last sig line

        full = " ".join(sig_lines)

        ret = "Float64"
        am = re.search(r"->\s*([^\n:{]+)", full)
        if am:
            ret = am.group(1).strip().rstrip("{: ")
            ret = re.sub(r"\s+", " ", ret)
        else:
            ret = "None"

        pm = re.search(r"\(([^)]*)\)", full)
        param_str = pm.group(1) if pm else ""
        params = _parse_params(param_str)
        if params is None:
            i += 1
            continue

        # Collect body (until next fn/def/struct)
        body_lines: list[str] = []
        k = body_start
        while k < len(lines):
            ln = lines[k]
            stripped_k = ln.strip()
            # Only break on top-level (unindented) definitions, not nested closures
            if (
                ln
                and not ln[0].isspace()
                and (
                    stripped_k.startswith("fn ")
                    or stripped_k.startswith("def ")
                    or stripped_k.startswith("struct ")
                )
            ):
                break
            # Skip any remaining signature fragments (contain '-> Type:' pattern)
            if re.match(r"[^#]*\)\s*->\s*\w[\w\[\], ]*\s*:", stripped_k):
                k += 1
                continue
            body_lines.append(ln)
            k += 1

        fns.append(FnInfo(fname, params, ret, body_lines, lib))
        i = k
    return fns


# ── Mojo → Python transpiler ──────────────────────────────────────────────────

_MOJO_MATH_FNS = {
    "log",
    "exp",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    "floor",
    "ceil",
    "fabs",
    "pow",
    "log10",
    "log2",
    "sinh",
    "cosh",
    "tanh",
}


def _mojo_expr_to_python(expr: str) -> str:
    """Convert a Mojo expression to Python."""
    # Mojo owned/move suffix operator: result^ → result
    # Only remove ^ that is immediately after a word char and NOT followed by space+word
    # (to preserve XOR: a ^ b, and ^= compound assignment)
    expr = re.sub(r"(?<=\w)\^(?=[,)\]\s;]|$)", "", expr)

    # NOTE: previously these patterns used unbounded '(?:[^\[\]]+|\[[^\[\]]*\])+'
    # which is polynomial-backtracking on inputs missing the closing ']'. We
    # bound them by length and limit nesting to a single level using a
    # non-quantified outer group, which is what the benchmark actually needs.
    # Real Mojo source never approaches the cap.
    list_inner = r"(?:[^\[\]]{0,512}(?:\[[^\[\]]{0,512}\][^\[\]]{0,512})?)"
    # List constructor: List[T]() → []  (handles nested like List[List[Bool]]())
    expr = re.sub(rf"\bList\[{list_inner}\]\(\)", "[]", expr)
    # List with capacity hint: List[T](capacity=N) → []
    # (handles a single level of nested parens like len(...))
    expr = re.sub(
        rf"\bList\[{list_inner}\]\((?:[^()]{{0,512}}(?:\([^()]{{0,512}}\)[^()]{{0,512}})?)\)",
        "[]",
        expr,
    )
    # Bare List[] type reference (not constructor) → list
    expr = re.sub(rf"\bList\[{list_inner}\](?!\()", "list", expr)

    # Mojo String methods
    expr = re.sub(r"\.as_bytes\(\)", ".encode('utf-8')", expr)
    expr = re.sub(r"\.count\(\)", ".encode('utf-8')", expr)  # byte count

    # Remove Mojo type casts: Float64(x) → float(x), Int(x) → int(x)
    expr = re.sub(r"\bFloat64\(", "float(", expr)
    expr = re.sub(r"\bInt\(", "int(", expr)
    expr = re.sub(r"\bInt64\(", "int(", expr)
    expr = re.sub(r"\bFloat32\(", "float(", expr)
    expr = re.sub(r"\bUInt64\(", "int(", expr)
    expr = re.sub(r"\bUInt32\(", "int(", expr)
    expr = re.sub(r"\bUInt16\(", "int(", expr)
    expr = re.sub(r"\bUInt8\(", "int(", expr)
    expr = re.sub(r"\bString\(", "str(", expr)

    # pow(a, b) → a ** b
    expr = re.sub(r"\bpow\(([^,]+),\s*([^)]+)\)", r"(\1) ** (\2)", expr)
    # Private helpers like _pow, _log, _sqrt, _exp, _log10, _log2
    expr = re.sub(r"\b_pow\(([^,]+),\s*([^)]+)\)", r"(\1) ** (\2)", expr)
    expr = re.sub(r"\b_log\b", "math.log", expr)
    expr = re.sub(r"\b_log10\b", "math.log10", expr)
    expr = re.sub(r"\b_log2\b", "math.log2", expr)
    expr = re.sub(r"\b_sqrt\b", "math.sqrt", expr)
    expr = re.sub(r"\b_exp\b", "math.exp", expr)
    expr = re.sub(r"\b_sin\b", "math.sin", expr)
    expr = re.sub(r"\b_cos\b", "math.cos", expr)

    # Standard math functions
    for fn in _MOJO_MATH_FNS:
        expr = re.sub(rf"\b{fn}\(", f"math.{fn}(", expr)

    # Constants
    expr = re.sub(r"\bPI\b", "math.pi", expr)
    expr = re.sub(r"\bE\b", "math.e", expr)
    expr = re.sub(r"\bINF\b", "math.inf", expr)

    # Mojo bool literals (capitalize already matches Python, but aliases)
    expr = re.sub(r"\bTrue\b", "True", expr)
    expr = re.sub(r"\bFalse\b", "False", expr)

    # Strip any Mojo 'var' keyword in compound statements (e.g. "x = a; var y = b")
    expr = re.sub(r"\bvar\s+(\w+)\s*(?::[^=;]+)?\s*=", r"\1 =", expr)
    expr = expr.replace("math.math.", "math.")

    return expr


def _last_structural_colon(s: str) -> int:
    """Return index of the last ':' not inside a string literal or brackets."""
    depth = 0
    in_str: str | None = None
    last_colon = -1
    i = 0
    while i < len(s):
        c = s[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c in ('"', "'"):
                in_str = c
            elif c in ("(", "[", "{"):
                depth += 1
            elif c in (")", "]", "}"):
                depth -= 1
            elif c == ":" and depth == 0:
                last_colon = i
        i += 1
    return last_colon


def _mojo_line_to_python(line: str, indent_base: int = 0) -> str | None:
    """Convert one Mojo body line to Python. Returns None to skip."""
    stripped = line.strip()
    if not stripped or stripped.startswith('"""') or stripped.startswith("#"):
        return ""  # empty line / docstring / comment
    # Skip Mojo-only declarations
    # Skip Mojo decorators (e.g. @always_inline, @parameter, @staticmethod)
    if stripped.startswith("@"):
        return None
    if stripped.startswith("comptime "):
        # comptime x: Type = val  → treat as regular variable assignment
        m = re.match(r"comptime\s+(\w+)\s*(?::[^=]+)?\s*=\s*(.+)", stripped)
        if m:
            indent = " " * max(0, len(line) - len(line.lstrip()) - indent_base + 4)
            return f"{indent}{m.group(1)} = {_mojo_expr_to_python(m.group(2))}"
        return None  # skip incomprehensible comptime lines
    if stripped.startswith("alias "):
        # alias NAME = value  → NAME = value
        m = re.match(r"alias\s+(\w+)\s*(?::[^=]+)?\s*=\s*(.+)", stripped)
        if m:
            indent = " " * max(0, len(line) - len(line.lstrip()) - indent_base + 4)
            return f"{indent}{m.group(1)} = {_mojo_expr_to_python(m.group(2))}"
        return None
    if stripped.startswith("constrained[") or stripped.startswith("debug_assert"):
        return None  # skip Mojo debug assertions
    if stripped.startswith("var "):
        # var x: Type = expr  → x = expr
        m = re.match(r"var\s+(\w+)\s*(?::[^=]+)?\s*=\s*(.+)", stripped)
        if m:
            indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
            return f"{indent}{m.group(1)} = {_mojo_expr_to_python(m.group(2))}"
        # var x: List[T]  → x = []
        m_list = re.match(r"var\s+(\w+)\s*:\s*List\[", stripped)
        if m_list:
            indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
            return f"{indent}{m_list.group(1)} = []"
        m2 = re.match(r"var\s+(\w+)\s*:\s*(\w+)", stripped)
        if m2:
            indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
            default = "0.0" if "Float" in m2.group(2) else ("[]" if "List" in m2.group(2) else "0")
            return f"{indent}{m2.group(1)} = {default}"
        return None
    if stripped.startswith("return "):
        rest = stripped[7:]
        indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
        return f"{indent}return {_mojo_expr_to_python(rest)}"
    if stripped.startswith("if ") or stripped.startswith("elif ") or stripped.startswith("else"):
        # Strip trailing comment first (# not inside strings), then find last structural colon
        no_comment = re.split(r"\s+#", stripped)[0]  # "if cond:  # comment" → "if cond:"
        last_colon = _last_structural_colon(no_comment)
        head = no_comment[:last_colon] if last_colon >= 0 else no_comment
        inline_body = no_comment[last_colon + 1 :].strip() if last_colon >= 0 else ""
        cond_match = re.match(r"(if|elif)\s+(.+)", head)
        else_match = re.match(r"else\s*$", head)
        indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
        if cond_match:
            cond = _mojo_expr_to_python(cond_match.group(2))
            # Multi-line condition: "if (" with unbalanced parens — don't add ":"
            if cond.count("(") > cond.count(")"):
                return f"{indent}{cond_match.group(1)} {cond}"
            py_head = f"{indent}{cond_match.group(1)} {cond}:"
            if inline_body:
                # One-liner "if cond: body" — convert body with extra indent
                body_indent = " " * (len(line) - len(line.lstrip()) - indent_base + 8)
                body_converted = _mojo_line_to_python(body_indent + inline_body, indent_base)
                if body_converted and body_converted.strip():
                    return py_head + "\n" + body_converted
            return py_head
        elif else_match:
            py_else = f"{indent}else:"
            if inline_body:
                body_indent = " " * (len(line) - len(line.lstrip()) - indent_base + 8)
                body_converted = _mojo_line_to_python(body_indent + inline_body, indent_base)
                if body_converted and body_converted.strip():
                    return py_else + "\n" + body_converted
            return py_else
    if stripped.startswith("for ") or stripped.startswith("while "):
        indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
        return f"{indent}{_mojo_expr_to_python(stripped)}"
    # Assignment (including compound: +=, -=, *=, /=, ^=, |=, &=, //=)
    # Use (?!=) to avoid matching == as an assignment (first = of ==)
    m = re.match(r"(\w+)\s*(?:\+|-|\*|/|\^|\||\&|//)?=(?!=)\s*(.+)", stripped)
    if (
        m
        and not stripped.startswith("fn ")
        and not stripped.startswith("def ")
        and not stripped.startswith("struct ")
    ):
        indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
        op_match = re.match(r"\w+\s*(\+|-|\*|/|\^|\||\&|//)?=(?!=)", stripped)
        op = op_match.group(1) if op_match and op_match.group(1) else ""
        rhs = _mojo_expr_to_python(m.group(2))
        return f"{indent}{m.group(1)} {op}= {rhs}" if op else f"{indent}{m.group(1)} = {rhs}"
    # Pass through with expression conversion
    indent = " " * (len(line) - len(line.lstrip()) - indent_base + 4)
    return f"{indent}{_mojo_expr_to_python(stripped)}"


def _strip_docstrings(lines: list[str]) -> list[str]:
    """Remove Mojo/Python docstring blocks from body lines."""
    result = []
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if in_docstring:
            if '"""' in stripped or "'''" in stripped:
                in_docstring = False
            continue  # skip docstring content
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # Check if docstring closes on same line
            rest = stripped[3:]
            if '"""' in rest or "'''" in rest:
                continue  # single-line docstring — skip
            in_docstring = True
            continue
        result.append(line)
    return result


def transpile_function(fn: FnInfo) -> str | None:
    """Return a Python def for the given Mojo function, or None if too complex."""
    if fn.ret.startswith("SIMD["):
        return None
    # Block mut only on primitive scalar types; structs/lists are pass-by-ref in Python
    if any(p.is_mut and p.typ in _PRIMITIVE_TYPES for p in fn.params):
        return None
    if any(p.typ in SKIP_PARAM_TYPES for p in fn.params):
        return None

    # Build Python param list (names with defaults if available)
    py_params = [
        f"{p.name}={p.default_val}" if p.default_val is not None else p.name for p in fn.params
    ]

    # Strip docstrings from body before processing
    clean_body = _strip_docstrings(fn.body_lines)

    # Find body indent base
    body = [line for line in clean_body if line.strip()]
    indent_base = len(body[0]) - len(body[0].lstrip()) if body else 4

    py_lines = [f"def {fn.name}({', '.join(py_params)}):"]
    for bl in clean_body:
        pl = _mojo_line_to_python(bl, indent_base)
        if pl is None:
            continue
        py_lines.append(pl)

    # Ensure function has a body
    body_content = [line for line in py_lines[1:] if line.strip()]
    if not body_content:
        return None

    return "\n".join(py_lines)


def _transpile_struct_method(
    method_nm: str, raw_params: str, body_lines: list[str], lib: str
) -> str | None:
    """Transpile a Mojo struct method; returns 4-space-indented Python, or None."""
    # Strip self / mut self / out self from params
    params_no_self = re.sub(
        r"^(?:mut\s+|out\s+|owned\s+|ref\s+)?self\s*,?\s*", "", raw_params.strip()
    )
    params = _parse_params(params_no_self) if params_no_self.strip() else []
    if params is None:
        params = []
    # Block mut on primitive types only (same rule as transpile_function)
    if any(p.is_mut and p.typ in _PRIMITIVE_TYPES for p in params):
        return None
    fn_info = FnInfo(method_nm, params, "None", body_lines, lib)
    result = transpile_function(fn_info)
    if result is None:
        return None
    # Re-insert `self` as first parameter
    result = re.sub(
        rf"^def {re.escape(method_nm)}\((.*?)\)",
        lambda m: (
            f"def {method_nm}(self, {m.group(1)})"
            if m.group(1).strip()
            else f"def {method_nm}(self)"
        ),
        result,
        count=1,
        flags=re.MULTILINE,
    )
    # Indent all lines 4 spaces for class body
    return "\n".join("    " + ln for ln in result.split("\n"))


# ── argument builder ──────────────────────────────────────────────────────────


def _arg_values(fn: FnInfo) -> list[str] | None:
    """Return Python literal arg expressions for a function call."""
    override = _PARAM_OVERRIDES.get((fn.lib, fn.name))
    args = []
    for i, p in enumerate(fn.params):
        # If we have an override for this param, skip type checks and use it directly
        if override is not None and i < len(override):
            args.append(override[i])
            continue
        if (p.is_mut and not p.typ.startswith("List[")) or p.typ in SKIP_PARAM_TYPES:
            return None
        if any(p.typ.startswith(pfx) for pfx in _SKIP_TYPE_PREFIXES):
            return None
        typ = p.typ
        if typ in ("Float64", "Float32"):
            args.append(SCALAR_VAL)
        elif typ == "Int":
            args.append(INT_VAL)
        elif typ in ("Bool",):
            args.append("True")
        elif typ in ("UInt64", "UInt32", "UInt8"):
            args.append("1")
        elif typ == "String":
            args.append('"test"')
        elif typ == "List[Float64]":
            args.append(LIST_VALS)
        elif typ == "List[Int]":
            args.append(INT_LIST)
        elif typ == "List[Bool]":
            args.append("[True, False, True, True, False]")
        elif typ == "List[String]":
            args.append('["a", "b", "c", "d", "e"]')
        elif typ == "List[List[Float64]]":
            args.append("[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]")
        elif typ == "List[List[Int]]":
            args.append("[[0,1,1],[1,0,1],[1,1,0]]")
        elif typ == "List[UInt8]":
            args.append("[1, 2, 3, 4, 5]")
        elif typ.startswith("List[List"):
            return None
        elif any(typ.startswith(pfx) for pfx in _SKIP_TYPE_PREFIXES):
            return None
        else:
            return None
    return args


# ── Module-level constant and helper extractor ────────────────────────────────


def _extract_cross_module_imports(lib_path: Path) -> str:
    """Parse 'from X import A, B, C' lines in a Mojo source and emit Python imports."""
    imports: list[str] = []
    try:
        lines = lib_path.read_text(encoding="utf-8", errors="replace").splitlines()
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            i += 1
            if not s.startswith("from ") or " import " not in s:
                # Stop at struct/fn (past the import section)
                if re.match(r"(fn|struct|def)\s+\w", s):
                    break
                continue
            m = re.match(r"from\s+([\w./]+)\s+import\s+(.+)", s)
            if not m:
                continue
            # Convert module path to a Python module name (last component, no extension)
            mod_path = m.group(1).replace("\\", "/")
            mod_name = mod_path.split("/")[-1].replace(".mojo", "")
            symbols_raw = m.group(2).strip()
            # Handle multi-line imports: from X import (\n    A,\n    B,\n)
            if symbols_raw.startswith("("):
                symbol_parts = [symbols_raw[1:]]  # strip leading '('
                while i < len(lines):
                    cont = lines[i].strip()
                    i += 1
                    if cont.endswith(")"):
                        symbol_parts.append(cont[:-1])
                        break
                    symbol_parts.append(cont)
                symbols = ", ".join(
                    p.strip().rstrip(",") for p in symbol_parts if p.strip().rstrip(",")
                )
            else:
                symbols = symbols_raw
            if not symbols:
                continue
            # Import each symbol separately so a missing one doesn't break the others
            symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
            for sym in symbol_list:
                imports.append(
                    f"try:\n    from {mod_name} import {sym}\nexcept Exception:\n    pass"
                )
    except Exception:
        pass
    return "\n".join(imports)


def _extract_module_preamble(lib_path: Path) -> str:
    """Extract module-level alias constants and var declarations as Python code."""
    lines = lib_path.read_text(encoding="utf-8", errors="replace").splitlines()
    preamble: list[str] = []
    in_docstring = False
    for ln in lines:
        s = ln.strip()
        # Skip docstrings first (before fn check, to handle fn refs inside docstrings)
        if in_docstring:
            if '"""' in s or "'''" in s:
                in_docstring = False
            continue
        if s.startswith('"""') or s.startswith("'''"):
            rest = s[3:]
            if '"""' not in rest and "'''" not in rest:
                in_docstring = True
            continue
        # Stop at first function/struct definition (module preamble ends)
        if re.match(r"(fn|struct|def)\s+\w", s):
            break
        # Extract: alias NAME = VALUE  or  alias NAME: TYPE = VALUE
        m = re.match(r"alias\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?\s*=\s*(.+)", s)
        if m:
            val = _mojo_expr_to_python(m.group(2).strip())
            preamble.append(f"{m.group(1)} = {val}")
            continue
        # Extract: var/comptime NAME: TYPE = VALUE  (module-level constants)
        for kw in ("var", "comptime", "let"):
            m2 = re.match(rf"{kw}\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?\s*=\s*(.+)", s)
            if m2:
                val = _mojo_expr_to_python(m2.group(2).strip())
                preamble.append(f"{m2.group(1)} = {val}")
                break
    return "\n".join(preamble)


def _struct_field_default(ftype: str, known_structs: set[str]) -> str:
    """Return a Python default initializer expression for a Mojo field type."""
    ftype = ftype.split("=")[0].strip()
    if "List[" in ftype:
        return "[]"
    if ftype in ("Int", "UInt8", "UInt32", "UInt64", "UInt16"):
        return "0"
    if ftype in ("Float64", "Float32"):
        return "0.0"
    if ftype == "Bool":
        return "False"
    if ftype == "String":
        return '""'
    if ftype in known_structs:
        return f"{ftype}()"
    return "None"


def _extract_struct_stubs(lib_path: Path) -> str:
    """Generate Python class stubs for Mojo structs with proper field defaults and methods."""
    text = lib_path.read_text(encoding="utf-8", errors="replace")
    all_lines = text.splitlines()
    lib_name = lib_path.stem

    # First pass: collect all struct names (for default-initializer generation)
    known_structs: set[str] = set()
    for ln in all_lines:
        m = re.match(r"struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]", ln.strip())
        if m:
            known_structs.add(m.group(1))

    stubs: list[str] = []
    i = 0
    in_docstring = False

    while i < len(all_lines):
        ln = all_lines[i]
        s = ln.strip()

        # Docstring tracking (top-level)
        if in_docstring:
            if '"""' in s or "'''" in s:
                in_docstring = False
            i += 1
            continue
        if s.startswith('"""') or s.startswith("'''"):
            rest = s[3:]
            if '"""' not in rest and "'''" not in rest:
                in_docstring = True
            i += 1
            continue

        # Detect struct at top level (no leading whitespace)
        if not ln.startswith(" ") and not ln.startswith("\t"):
            m = re.match(r"struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]", s)
            if m:
                struct_name = m.group(1)
                # (field_name, field_type) — all var fields in the struct
                fields_typed: list[tuple[str, str]] = []
                # init_params: params of fn __init__ (overrides fields_typed for signature)
                init_params: list[tuple[str, str]] | None = None
                methods_code: list[str] = []
                in_struct_doc = False
                i += 1

                # Parse struct body: all indented lines
                while i < len(all_lines):
                    inner_ln = all_lines[i]
                    inner_s = inner_ln.strip()

                    # Struct body ends at top-level non-empty line
                    if (
                        not inner_ln.startswith(" ")
                        and not inner_ln.startswith("\t")
                        and inner_s
                        and not inner_s.startswith("#")
                    ):
                        break

                    # Track docstrings inside struct
                    if in_struct_doc:
                        if '"""' in inner_s or "'''" in inner_s:
                            in_struct_doc = False
                        i += 1
                        continue
                    if inner_s.startswith('"""') or inner_s.startswith("'''"):
                        rest_d = inner_s[3:]
                        if '"""' not in rest_d and "'''" not in rest_d:
                            in_struct_doc = True
                        i += 1
                        continue

                    # Collect field declarations
                    fm = re.match(r"var\s+(\w+)\s*:\s*(.+)", inner_s)
                    if fm:
                        fname = fm.group(1)
                        ftype = fm.group(2).strip().split("=")[0].strip()
                        # Remove Mojo type prefixes (owned/mut/ref)
                        for pfx in ("owned ", "mut ", "ref ", "inout "):
                            if ftype.startswith(pfx):
                                ftype = ftype[len(pfx) :]
                        fields_typed.append((fname, ftype))
                        i += 1
                        continue

                    # Detect method declarations
                    fn_m = re.match(r"(?:fn|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", inner_s)
                    if fn_m:
                        method_nm = fn_m.group(1)
                        method_indent = len(inner_ln) - len(inner_ln.lstrip())

                        if method_nm.startswith("__") and method_nm != "__init__":
                            # Skip all dunder methods except __init__
                            i += 1
                            while i < len(all_lines):
                                skip_ln = all_lines[i]
                                skip_s = skip_ln.strip()
                                if not skip_s:
                                    i += 1
                                    continue
                                skip_ind = len(skip_ln) - len(skip_ln.lstrip())
                                if skip_ind <= method_indent and re.match(r"(?:fn|def)\s+", skip_s):
                                    break
                                if not skip_ln.startswith(" ") and not skip_ln.startswith("\t"):
                                    break
                                i += 1
                            continue

                        if method_nm == "__init__":
                            # Parse __init__ signature to know actual constructor params
                            sig_i = [inner_s]
                            i += 1
                            while i < len(all_lines) and not inner_s.rstrip().endswith(":"):
                                nxt = all_lines[i].strip()
                                sig_i.append(nxt)
                                inner_s = nxt
                                i += 1
                                if nxt.rstrip().endswith(":"):
                                    break
                            full_init_sig = " ".join(sig_i)
                            dp = 0
                            ps = -1
                            pstr = ""
                            for ci, ch in enumerate(full_init_sig):
                                if ch == "(" and ps == -1:
                                    ps = ci + 1
                                    dp = 1
                                elif ch == "(":
                                    dp += 1
                                elif ch == ")":
                                    dp -= 1
                                    if dp == 0:
                                        pstr = full_init_sig[ps:ci]
                                        break
                            # Remove self/out self/mut self then parse remaining params
                            pstr_clean = re.sub(
                                r"^(?:mut\s+|out\s+|owned\s+|ref\s+)?self\s*,?\s*", "", pstr.strip()
                            )
                            if pstr_clean.strip():
                                init_param_list = _parse_params(pstr_clean)
                                if init_param_list is not None:
                                    init_params = [(p2.name, p2.typ) for p2 in init_param_list]
                            # Skip __init__ body
                            while i < len(all_lines):
                                skip_ln = all_lines[i]
                                skip_s = skip_ln.strip()
                                if not skip_s:
                                    i += 1
                                    continue
                                skip_ind = len(skip_ln) - len(skip_ln.lstrip())
                                if skip_ind <= method_indent and re.match(r"(?:fn|def)\s+", skip_s):
                                    break
                                if not skip_ln.startswith(" ") and not skip_ln.startswith("\t"):
                                    break
                                i += 1
                            continue

                        # Collect method signature (may be multi-line)
                        sig_parts = [inner_s]
                        i += 1
                        while i < len(all_lines) and not inner_s.rstrip().endswith(":"):
                            nxt = all_lines[i].strip()
                            sig_parts.append(nxt)
                            inner_s = nxt
                            i += 1
                            if nxt.rstrip().endswith(":"):
                                break

                        full_sig = " ".join(sig_parts)
                        # Extract params (handle nested brackets in List[X])
                        depth_p = 0
                        p_start = -1
                        params_str = ""
                        for ci, ch in enumerate(full_sig):
                            if ch == "(" and p_start == -1:
                                p_start = ci + 1
                                depth_p = 1
                            elif ch == "(":
                                depth_p += 1
                            elif ch == ")":
                                depth_p -= 1
                                if depth_p == 0:
                                    params_str = full_sig[p_start:ci]
                                    break

                        # Collect method body (indent > method_indent)
                        body_lines: list[str] = []
                        while i < len(all_lines):
                            body_ln = all_lines[i]
                            body_s = body_ln.strip()
                            if not body_s:
                                body_lines.append(body_ln)
                                i += 1
                                continue
                            body_ind = len(body_ln) - len(body_ln.lstrip())
                            if body_ind <= method_indent:
                                break
                            body_lines.append(body_ln)
                            i += 1

                        # Transpile the method
                        method_py = _transpile_struct_method(
                            method_nm, params_str, body_lines, lib_name
                        )
                        if method_py:
                            methods_code.append(method_py)
                        continue

                    i += 1

                # Generate class stub
                if not fields_typed and not methods_code:
                    # Check manual methods
                    manual = _STRUCT_MANUAL_METHODS.get((lib_name, struct_name), [])
                    if not manual:
                        continue

                # Build __init__: use init_params for signature, but initialize all struct fields
                sig_params = init_params if init_params is not None else fields_typed
                init_lines = ["    def __init__(self, *args, **kwargs):"]
                sig_names = {fname for fname, _ in sig_params}
                for fi, (fname, ftype) in enumerate(sig_params):
                    dflt = _struct_field_default(ftype, known_structs)
                    init_lines.append(
                        f"        _v{fi} = args[{fi}] if {fi} < len(args) else kwargs.get('{fname}')"
                    )
                    init_lines.append(
                        f"        self.{fname} = _v{fi} if _v{fi} is not None else {dflt}"
                    )
                # Initialize any struct fields NOT in the __init__ signature with defaults
                for fname, ftype in fields_typed:
                    if fname not in sig_names:
                        dflt = _struct_field_default(ftype, known_structs)
                        init_lines.append(f"        self.{fname} = {dflt}")
                # Apply any dynamic init extras (e.g. pre-allocate List fields)
                for extra_line in _STRUCT_INIT_EXTRAS.get((lib_name, struct_name), []):
                    init_lines.append(extra_line)
                init_lines.append("    def __repr__(self):")
                init_lines.append(f"        return f'{struct_name}({{vars(self)}})'")

                class_code = f"class {struct_name}:\n" + "\n".join(init_lines)

                # Add auto-transpiled methods
                if methods_code:
                    class_code += "\n" + "\n".join(methods_code)

                # Add manual methods (override/supplement auto ones)
                for manual_m in _STRUCT_MANUAL_METHODS.get((lib_name, struct_name), []):
                    class_code += "\n" + manual_m.rstrip("\n")

                stubs.append(class_code)
                continue

        i += 1

    return "\n\n".join(stubs)


# ── Python lib file generator ─────────────────────────────────────────────────


def generate_python_lib(
    lib: str, fns: list[FnInfo], import_path: str | None = None, lib_path: Path | None = None
) -> tuple[str, list[FnInfo]]:
    """Return (python source code, list of successfully transpiled functions)."""
    src_path = import_path or lib
    lines = [
        f'"""Python equivalent of mojo/engine/{src_path}.mojo (auto-generated)."""',
        "import math",
        "import random as _rng",
        "",
    ]

    # Add module-level constants and struct stubs if we have the source path
    if lib_path is not None:
        cross_imports = _extract_cross_module_imports(lib_path)
        if cross_imports:
            lines.append(cross_imports)
            lines.append("")
        preamble = _extract_module_preamble(lib_path)
        if preamble:
            lines.append(preamble)
            lines.append("")
        struct_stubs = _extract_struct_stubs(lib_path)
        if struct_stubs:
            lines.append(struct_stubs)
            lines.append("")

    # Common Mojo runtime stubs not in stdlib
    lines += [
        "def random_float64(lo=0.0, hi=1.0): return _rng.uniform(lo, hi)",
        "def random_si64(): return _rng.randint(-2**31, 2**31)",
        "def random_ui64(): return _rng.randint(0, 2**32)",
        "",
        # ── Fallback stubs for Mojo cross-module helpers ──────────────────────
        # json/parser: stubs used by engines/* libraries when real Mojo module unavailable
        "def json_get_string(raw, key, default=''):",
        "    try:",
        "        import json as _j; v = _j.loads(raw).get(key)",
        "        return str(v) if v is not None else default",
        "    except Exception: return default",
        "def json_get_float(raw, key, default=0.0):",
        "    try:",
        "        import json as _j; v = _j.loads(raw).get(key)",
        "        return float(v) if v is not None else default",
        "    except Exception: return default",
        "def json_get_int(raw, key, default=0):",
        "    try:",
        "        import json as _j; v = _j.loads(raw).get(key)",
        "        return int(v) if v is not None else default",
        "    except Exception: return default",
        "def json_get_bool(raw, key, default=False):",
        "    try:",
        "        import json as _j; v = _j.loads(raw).get(key)",
        "        return bool(v) if v is not None else default",
        "    except Exception: return default",
        "def json_get_object(raw, key, default='{}'):",
        "    try:",
        "        import json as _j; v = _j.loads(raw).get(key, {})",
        "        return _j.dumps(v) if isinstance(v, dict) else default",
        "    except Exception: return default",
        "def json_get_array(raw, key, default='[]'):",
        "    try:",
        "        import json as _j; v = _j.loads(raw).get(key, [])",
        "        return _j.dumps(v) if isinstance(v, list) else default",
        "    except Exception: return default",
        "def json_array_len(arr):",
        "    try:",
        "        import json as _j; return len(_j.loads(arr))",
        "    except Exception: return 0",
        "def json_array_get(arr, index):",
        "    try:",
        "        import json as _j; v = _j.loads(arr)",
        "        return _j.dumps(v[index]) if index < len(v) else ''",
        "    except Exception: return ''",
        # field_mapper stubs
        "def to_lower(s): return s.lower()",
        "def contains_keyword(text, keyword): return keyword.lower() in text.lower()",
        "def detect_polarity(field_name):",
        "    n = field_name.lower()",
        "    if any(k in n for k in ('cost','expense','loss','debit','charge','penalty','tax')): return -1",
        "    if any(k in n for k in ('revenue','profit','income','gain','credit','sales')): return 1",
        "    return 0",
        "def detect_unit_hint(field_name):",
        "    n = field_name.lower()",
        "    if any(k in n for k in ('cost','price','revenue','profit','amount','value','dollar')): return 'currency'",
        "    if any(k in n for k in ('pct','percent','ratio','rate','margin')): return 'percentage'",
        "    if any(k in n for k in ('qty','quantity','count','units','volume')): return 'count'",
        "    return ''",
        "def infer_distribution_from_values(values): return ('normal', '{}')",
        "def map_fields(raw): return []",
        "def build_objective_function(mappings): return ''",
        "def build_variables_json(mappings): return '[]'",
        "class FieldMapping: pass",
        # string_distance stubs
        "def dice_coefficient(a, b):",
        "    if not a or not b: return 0.0",
        "    def _bg(s): return set(s[i:i+2] for i in range(len(s)-1))",
        "    ag, bg = _bg(a), _bg(b)",
        "    if not ag or not bg: return 0.0",
        "    return 2.0 * len(ag & bg) / (len(ag) + len(bg))",
        "def edit_similarity(a, b):",
        "    if not a and not b: return 1.0",
        "    if not a or not b: return 0.0",
        "    m, n = len(a), len(b); dp = list(range(n+1))",
        "    for i in range(1, m+1):",
        "        prev, dp[0] = dp[0], i",
        "        for j in range(1, n+1):",
        "            t = dp[j]; dp[j] = prev if a[i-1]==b[j-1] else 1+min(prev,dp[j],dp[j-1]); prev=t",
        "    return 1.0 - dp[n] / max(m, n)",
        # set_ops stubs
        "def jaccard_index(a, b):",
        "    sa, sb = set(a), set(b)",
        "    if not sa and not sb: return 1.0",
        "    if not sa or not sb: return 0.0",
        "    return len(sa & sb) / len(sa | sb)",
        "def to_set(lst): return list(set(lst))",
        # conv stubs
        "def parse_float64(s, default=0.0):",
        "    try: return float(s)",
        "    except Exception: return default",
        "def parse_int(s, default=0):",
        "    try: return int(float(s))",
        "    except Exception: return default",
        # dimensions stubs (used by relation_detector)
        "DIM_UNKNOWN = 0; DIM_COUNT = 1; DIM_CURRENCY = 2; DIM_RATE = 3",
        "DIM_RATIO = 4; DIM_IDENTIFIER = 5; DIM_INVALID = -1",
        "def infer_from_samples(values): return DIM_UNKNOWN",
        "def propagate(a, b, op): return DIM_UNKNOWN",
        "def role_for_dimension(dim): return 'metric'",
        # Python interop stub (used by env.mojo)
        "class Python:",
        "    @staticmethod",
        "    def import_module(name):",
        "        import importlib; return importlib.import_module(name)",
        "",
    ]

    # First pass: transpile ALL functions (public and private) for dependency lookup
    all_transpiled: dict[str, str] = {}
    all_fns_map: dict[str, FnInfo] = {}
    for fn in fns:
        py_fn = transpile_function(fn)
        if py_fn:
            all_transpiled[fn.name] = py_fn
            all_fns_map[fn.name] = fn

    # Include private helpers first (they're called by public functions)
    for fn in fns:
        if fn.name.startswith("_") and fn.name in all_transpiled:
            lines.append(all_transpiled[fn.name])
            lines.append("")

    # Include public functions that have testable args
    transpiled: list[FnInfo] = []
    for fn in fns:
        if fn.name.startswith("_"):
            continue
        if _arg_values(fn) is None:
            continue
        if fn.name not in all_transpiled:
            continue
        lines.append(all_transpiled[fn.name])
        lines.append("")
        transpiled.append(fn)

    # If no public testable functions, fall back to private ones (e.g. csv_parser helpers)
    if not transpiled:
        for fn in fns:
            if not fn.name.startswith("_"):
                continue
            if _arg_values(fn) is None:
                continue
            if fn.name not in all_transpiled:
                continue
            transpiled.append(fn)

    return "\n".join(lines), transpiled


# ── Mojo benchmark file generator ─────────────────────────────────────────────


def _mojo_arg(p: Param, override_args: list[str] | None, idx: int) -> str:
    # Use override if available for this index; fall through to type-based defaults otherwise
    if override_args is not None and idx < len(override_args):
        return override_args[idx]
    typ = p.typ
    if typ in ("Float64", "Float32"):
        return "0.5"
    if typ == "Int":
        return "5"
    if typ in ("Bool",):
        return "True"
    if typ in ("UInt64", "UInt32", "UInt8"):
        return "UInt64(1)" if "UInt64" in typ else "1"
    if typ == "String":
        return '"test"'
    if typ == "List[Float64]":
        return "_lf5"
    if typ == "List[Int]":
        return "_li5"
    if typ == "List[Bool]":
        return "_lb5"
    if typ == "List[String]":
        return '["a","b","c","d","e"]'
    if typ == "List[List[Float64]]":
        return "[[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]"
    if typ == "List[List[Int]]":
        return "[[0,1,1],[1,0,1],[1,1,0]]"
    if typ == "List[UInt8]":
        return "_lub5"
    return "0.5"


_PRIMITIVE_TYPES = {
    "Float64",
    "Float32",
    "Int",
    "Bool",
    "UInt64",
    "UInt32",
    "UInt8",
    "String",
    "None",
}


def _get_struct_fields(lib_path: Path | None) -> dict[str, list[tuple[str, str]]]:
    """Return {struct_name: [(field_name, field_type), ...]} for all structs in source."""
    if lib_path is None:
        return {}
    result: dict[str, list[tuple[str, str]]] = {}
    try:
        text = lib_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        in_struct = False
        struct_name = ""
        in_docstring = False
        for ln in lines:
            s = ln.strip()
            if in_docstring:
                if '"""' in s or "'''" in s:
                    in_docstring = False
                continue
            if s.startswith('"""') or s.startswith("'''"):
                rest = s[3:]
                if '"""' not in rest and "'''" not in rest:
                    in_docstring = True
                continue
            if not in_struct:
                m = re.match(r"struct\s+([A-Za-z_][A-Za-z0-9_]*)", s)
                if m:
                    in_struct = True
                    struct_name = m.group(1)
                    result[struct_name] = []
            else:
                m = re.match(r"var\s+(\w+)\s*:\s*(\w+)", s)
                if m:
                    result[struct_name].append((m.group(1), m.group(2)))
                elif (
                    re.match(r"(fn|struct)\s+\w", s)
                    and not ln.startswith(" ")
                    and not ln.startswith("\t")
                ):
                    in_struct = False
                    m2 = re.match(r"struct\s+([A-Za-z_][A-Za-z0-9_]*)", s)
                    if m2:
                        in_struct = True
                        struct_name = m2.group(1)
                        result[struct_name] = []
    except Exception:
        pass
    return result


def _get_copyable_structs(lib_path: Path | None) -> set[str]:
    """Return set of struct names that implement Copyable in the given Mojo source."""
    if lib_path is None:
        return set()
    copyable: set[str] = set()
    try:
        text = lib_path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", text):
            traits = m.group(2)
            if "Copyable" in traits:
                copyable.add(m.group(1))
    except Exception:
        pass
    return copyable


def _manual_python_module_path(lib: str) -> Path:
    return PY_MANUAL_LIBS / f"{lib}.py"


def _manual_python_source(lib: str) -> str | None:
    path = _manual_python_module_path(lib)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _manual_transpiled_functions(lib: str, fns: list[FnInfo]) -> list[FnInfo]:
    path = _manual_python_module_path(lib)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    available = {
        fn.name
        for fn in fns
        if re.search(rf"^def {re.escape(fn.name)}\(", text, flags=re.MULTILINE)
    }
    return [fn for fn in fns if fn.name in available]


def _stable_hash_bytes(data: bytes) -> str:
    value = 7
    for byte in data:
        value = (value * 131 + byte) % 2147483647
    return str(value)


def _format_summary_float(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return str(float(value))


def _parse_summary_float(raw: str) -> float | None:
    if raw == "nan":
        return math.nan
    if raw == "inf":
        return math.inf
    if raw == "-inf":
        return -math.inf
    try:
        return float(raw)
    except ValueError:
        return None


def _result_summaries_match(py_summary: str | None, mojo_summary: str | None) -> bool | None:
    if py_summary is None or mojo_summary is None:
        return None
    if py_summary == mojo_summary:
        return True
    if py_summary.startswith("float:") and mojo_summary.startswith("float:"):
        py_value = _parse_summary_float(py_summary.removeprefix("float:"))
        mojo_value = _parse_summary_float(mojo_summary.removeprefix("float:"))
        if py_value is None or mojo_value is None:
            return False
        if math.isnan(py_value) and math.isnan(mojo_value):
            return True
        if math.isinf(py_value) or math.isinf(mojo_value):
            return py_value == mojo_value
        return math.isclose(py_value, mojo_value, rel_tol=1e-9, abs_tol=1e-9)
    return False


def _extract_attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _candidate_table_summary(value: Any) -> str:
    entries = _extract_attr(value, "entries", [])
    parts: list[str] = []
    for entry in entries:
        vec = _extract_attr(entry, "vec", {})
        vec_data = _extract_attr(vec, "data", [])
        vec_summary = _python_result_summary(
            list(vec_data),
            lib="vector_kernels_table",
            function="__candidate_vec__",
        )
        vec_norm_inv = _extract_attr(vec, "norm_inv", 0.0)
        parts.append(
            ":".join(
                [
                    str(int(_extract_attr(entry, "column_id", 0))),
                    str(int(_extract_attr(entry, "source_id", 0))),
                    str(int(_extract_attr(entry, "role_id", 0))),
                    f"float:{_format_summary_float(float(_extract_attr(entry, 'norm_inv', 0.0)))}",
                    f"float:{_format_summary_float(float(vec_norm_inv))}",
                    vec_summary or "none",
                ]
            )
        )
    return f"candidate_table:{len(entries)}:{_stable_hash_bytes('|'.join(parts).encode('utf-8'))}"


def _rank_request_summary(value: Any) -> str:
    source_id = int(_extract_attr(value, "source_id", 0))
    role_id = int(_extract_attr(value, "role_id", 0))
    top_k = int(_extract_attr(value, "top_k", 0))
    query_norm_inv = float(_extract_attr(value, "query_norm_inv", 0.0))
    query_vec = _extract_attr(value, "query_vec", {})
    vec_data = _extract_attr(query_vec, "data", [])
    vec_summary = _python_result_summary(
        list(vec_data),
        lib="vector_kernels_table",
        function="__query_vec__",
    )
    return (
        "rank_request:"
        f"{source_id}:{role_id}:{top_k}:"
        f"float:{_format_summary_float(query_norm_inv)}:{_stable_hash_bytes((vec_summary or 'none').encode('utf-8'))}"
    )


def _rounded_float_matrix_summary(value: list[list[float]]) -> str:
    child_parts: list[str] = []
    for row in value:
        rounded = [f"float:{round(float(item), 6)}" for item in row]
        child_parts.append(
            f"list:{len(row)}:{_stable_hash_bytes('|'.join(rounded).encode('utf-8'))}"
        )
    return f"list:{len(value)}:{_stable_hash_bytes('|'.join(child_parts).encode('utf-8'))}"


def _rounded_float_list_summary(value: list[float]) -> str:
    rounded = [f"float:{round(float(item), 6)}" for item in value]
    return f"list:{len(value)}:{_stable_hash_bytes('|'.join(rounded).encode('utf-8'))}"


def _python_result_summary(value: Any, *, lib: str, function: str) -> str | None:
    if lib == "vector_kernels_table" and function == "build_table_json":
        return _candidate_table_summary(value)
    if lib == "vector_kernels_table" and function == "build_query":
        return _rank_request_summary(value)
    if lib == "embeddings" and function == "cosine_similarity_matrix":
        return _rounded_float_matrix_summary(value)
    if lib == "image_resize" and function == "bilinear_downscale":
        return _rounded_float_matrix_summary(value)
    if lib == "video_quality" and function == "frame_quality_series":
        return _rounded_float_list_summary(value)
    if value is None:
        return "none"
    if isinstance(value, bool):
        return f"bool:{int(value)}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, float):
        return f"float:{_format_summary_float(value)}"
    if isinstance(value, str):
        digest = _stable_hash_bytes(value.encode("utf-8"))
        return f"str:{len(value.encode('utf-8'))}:{digest}"
    if isinstance(value, list):
        child_parts = []
        for item in value:
            child_summary = _python_result_summary(item, lib=lib, function=function)
            if child_summary is None:
                return None
            child_parts.append(child_summary)
        digest = _stable_hash_bytes("|".join(child_parts).encode("utf-8"))
        return f"list:{len(value)}:{digest}"
    if isinstance(value, dict):
        child_parts = []
        for key in sorted(value):
            child_summary = _python_result_summary(value[key], lib=lib, function=function)
            if child_summary is None:
                return None
            child_parts.append(f"{key}={child_summary}")
        digest = _stable_hash_bytes("|".join(child_parts).encode("utf-8"))
        return f"dict:{len(value)}:{digest}"
    if hasattr(value, "__dict__"):
        child_parts = []
        for key in sorted(vars(value)):
            child_summary = _python_result_summary(
                getattr(value, key),
                lib=lib,
                function=function,
            )
            if child_summary is None:
                return None
            child_parts.append(f"{key}={child_summary}")
        digest = _stable_hash_bytes("|".join(child_parts).encode("utf-8"))
        return f"obj:{type(value).__name__}:{digest}"
    return None


def _emit_mojo_summary_helpers(include_vector_kernels_table_helpers: bool) -> list[str]:
    lines = [
        "fn _summary_hash_string(value: String) -> Int:",
        "    var h = 7",
        "    var bytes = value.as_bytes()",
        "    for i in range(len(bytes)):",
        "        h = (h * 131 + Int(bytes[i])) % 2147483647",
        "    return h",
        "",
        "fn _summary_float64(value: Float64) -> String:",
        '    if isnan(value): return "float:nan"',
        '    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"',
        '    return "float:" + String(value)',
        "",
        "fn _summary_float64_rounded6(value: Float64) -> String:",
        '    if isnan(value): return "float:nan"',
        '    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"',
        "    var scaled = value * 1000000.0",
        "    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0",
        '    return "float:" + String(rounded)',
        "",
        "fn _summary_float32(value: Float32) -> String:",
        "    return _summary_float64(Float64(value))",
        "",
        "fn _summary_int(value: Int) -> String:",
        '    return "int:" + String(value)',
        "",
        "fn _summary_uint8(value: UInt8) -> String:",
        '    return "int:" + String(value)',
        "",
        "fn _summary_uint16(value: UInt16) -> String:",
        '    return "int:" + String(value)',
        "",
        "fn _summary_uint32(value: UInt32) -> String:",
        '    return "int:" + String(value)',
        "",
        "fn _summary_uint64(value: UInt64) -> String:",
        '    return "int:" + String(value)',
        "",
        "fn _summary_bool(value: Bool) -> String:",
        '    return "bool:1" if value else "bool:0"',
        "",
        "fn _summary_string(value: String) -> String:",
        '    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))',
        "",
        "fn _summary_list_float64(value: List[Float64]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_float64(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_float64_rounded6(value: List[Float64]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_float64_rounded6(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_float32(value: List[Float32]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_float32(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_int(value: List[Int]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_int(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_bool(value: List[Bool]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_bool(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_string(value: List[String]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_string(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_list_float64(value: List[List[Float64]]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_list_float64(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        '        var row_joined = String("")',
        "        for j in range(len(value[i])):",
        '            if j > 0: row_joined += "|"',
        "            row_joined += _summary_float64_rounded6(value[i][j])",
        '        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))',
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_list_int(value: List[List[Int]]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_list_int(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
        "fn _summary_list_list_string(value: List[List[String]]) -> String:",
        '    var joined = String("")',
        "    for i in range(len(value)):",
        '        if i > 0: joined += "|"',
        "        joined += _summary_list_string(value[i])",
        '    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))',
        "",
    ]
    if include_vector_kernels_table_helpers:
        lines.extend(
            [
                "fn _summary_rank_request(value: RankRequest) -> String:",
                "    var vec_summary = _summary_list_float32(value.query_vec.data)",
                '    return "rank_request:" + String(value.source_id) + ":" + String(value.role_id) + ":" + String(value.top_k) + ":" + _summary_float32(value.query_norm_inv) + ":" + String(_summary_hash_string(vec_summary))',
                "",
                "fn _summary_candidate_table(value: CandidateTable) -> String:",
                '    var joined = String("")',
                "    for i in range(len(value.entries)):",
                '        if i > 0: joined += "|"',
                "        var vec_summary = _summary_list_float32(value.entries[i].vec.data)",
                '        joined += String(value.entries[i].column_id) + ":"',
                '        joined += String(value.entries[i].source_id) + ":"',
                '        joined += String(value.entries[i].role_id) + ":"',
                '        joined += _summary_float32(value.entries[i].norm_inv) + ":"',
                '        joined += _summary_float32(value.entries[i].vec.norm_inv) + ":"',
                "        joined += vec_summary",
                '    return "candidate_table:" + String(len(value.entries)) + ":" + String(_summary_hash_string(joined))',
                "",
            ]
        )
    return lines


def _mojo_summary_call_expression(lib: str, fn: FnInfo, value_name: str) -> str | None:
    if lib == "vector_kernels_table" and fn.name == "build_query":
        return f"_summary_rank_request({value_name})"
    if lib == "vector_kernels_table" and fn.name == "build_table_json":
        return f"_summary_candidate_table({value_name})"
    if lib == "embeddings" and fn.name == "cosine_similarity_matrix":
        return f"_summary_list_list_float64_rounded6({value_name})"
    if lib == "image_resize" and fn.name == "bilinear_downscale":
        return f"_summary_list_list_float64_rounded6({value_name})"
    if lib == "video_quality" and fn.name == "frame_quality_series":
        return f"_summary_list_float64_rounded6({value_name})"
    if fn.ret == "None":
        return '"none"'
    if fn.ret == "Bool":
        return f"_summary_bool({value_name})"
    if fn.ret == "String":
        return f"_summary_string({value_name})"
    if fn.ret == "Int":
        return f"_summary_int({value_name})"
    if fn.ret == "UInt8":
        return f"_summary_uint8({value_name})"
    if fn.ret == "UInt16":
        return f"_summary_uint16({value_name})"
    if fn.ret == "UInt32":
        return f"_summary_uint32({value_name})"
    if fn.ret == "UInt64":
        return f"_summary_uint64({value_name})"
    if fn.ret == "Float32":
        return f"_summary_float32({value_name})"
    if fn.ret == "Float64":
        return f"_summary_float64({value_name})"
    if fn.ret == "List[Float64]":
        return f"_summary_list_float64({value_name})"
    if fn.ret == "List[Float32]":
        return f"_summary_list_float32({value_name})"
    if fn.ret == "List[Int]":
        return f"_summary_list_int({value_name})"
    if fn.ret == "List[Bool]":
        return f"_summary_list_bool({value_name})"
    if fn.ret == "List[String]":
        return f"_summary_list_string({value_name})"
    if fn.ret == "List[List[Float64]]":
        return f"_summary_list_list_float64({value_name})"
    if fn.ret == "List[List[Int]]":
        return f"_summary_list_list_int({value_name})"
    if fn.ret == "List[List[String]]":
        return f"_summary_list_list_string({value_name})"
    return None


def generate_mojo_benchmark(
    lib: str,
    fns: list[FnInfo],
    n: int,
    import_path: str | None = None,
    lib_path: Path | None = None,
) -> str:
    """Return a Mojo benchmark file that times each function over N iterations."""
    benchable = [
        f
        for f in fns
        if _arg_values(f) is not None
        and not f.ret.startswith("SIMD[")
        and not any(p.is_mut and not p.typ.startswith("List[") for p in f.params)
    ]
    fn_imports = [f.name for f in benchable]
    if not fn_imports:
        return ""

    copyable_structs = _get_copyable_structs(lib_path)
    struct_fields = _get_struct_fields(lib_path)

    # Also import struct types used as return values or as parameter values in overrides
    # Only include structs that are Copyable (required for List[T])
    _struct_type_re = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\s*\(")  # e.g. "Trie(" or "Point("
    extra_struct_types: set[str] = set()
    for f in benchable:
        override = _PARAM_OVERRIDES.get((lib, f.name))
        if override:
            for arg_str in override:
                for m_st in _struct_type_re.finditer(arg_str):
                    extra_struct_types.add(m_st.group(1))
    # Get all known struct names in this module
    all_struct_names: set[str] = set(struct_fields.keys()) | set(copyable_structs)
    struct_imports = sorted(
        {
            f.ret
            for f in benchable
            if f.ret not in _PRIMITIVE_TYPES
            and not f.ret.startswith("List[")
            and not f.ret.startswith("SIMD[")
            and f.ret != "None"
            and f.ret in copyable_structs
        }
        | (
            {"CandidateTable", "RankRequest"}
            if lib == "vector_kernels_table"
            and any(f.ret in {"CandidateTable", "RankRequest"} for f in benchable)
            else set()
        )
        | {t for t in extra_struct_types if t in all_struct_names}
    )
    all_imports = fn_imports + struct_imports
    include_candidate_table_summary = lib == "vector_kernels_table" and any(
        f.ret in {"CandidateTable", "RankRequest"} for f in benchable
    )

    mod = import_path or lib
    # Extra imports needed for certain libraries
    extra_imports: list[str] = []
    if lib == "linalg_ext":
        extra_imports.append("from linalg import mat_from_list, Matrix")
    lines = (
        [
            f'"""bench_{lib}.mojo — auto-generated timing benchmark."""',
            "from std.math import isnan, isinf",
            f"from {mod} import {', '.join(all_imports)}",
            "from std.time import perf_counter_ns",
        ]
        + extra_imports
        + _emit_mojo_summary_helpers(include_candidate_table_summary)
        + [
            "",
            "def main() raises:",
            "    var _lf5 = List[Float64]()",
            "    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)",
            "    _lf5.append(0.4); _lf5.append(0.3)",
            "    var _lf12_colorcheck2x2 = List[Float64]()",
            "    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)",
            "    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)",
            "    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)",
            "    _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(200.0)",
            "    var _lf48_video3x4x4 = List[Float64]()",
            "    for _ in range(16):",
            "        _lf48_video3x4x4.append(10.0)",
            "    for pixel in range(16):",
            "        if pixel < 4:",
            "            _lf48_video3x4x4.append(200.0)",
            "        else:",
            "            _lf48_video3x4x4.append(10.0)",
            "    for _ in range(16):",
            "        _lf48_video3x4x4.append(200.0)",
            "    var _lf48_video3x4x4_alt = List[Float64]()",
            "    for _ in range(16):",
            "        _lf48_video3x4x4_alt.append(12.0)",
            "    for pixel in range(16):",
            "        if pixel < 4:",
            "            _lf48_video3x4x4_alt.append(188.0)",
            "        else:",
            "            _lf48_video3x4x4_alt.append(12.0)",
            "    for _ in range(16):",
            "        _lf48_video3x4x4_alt.append(192.0)",
            "    var _lf36_video_rgb3x2x2 = List[Float64]()",
            "    for _ in range(4):",
            "        _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)",
            "    for pixel in range(4):",
            "        if pixel < 3:",
            "            _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)",
            "        else:",
            "            _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)",
            "    for _ in range(4):",
            "        _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)",
            "    var _lf25_block5x5 = List[Float64]()",
            "    for y in range(5):",
            "        for x in range(5):",
            "            if y >= 1 and y <= 3 and x >= 1 and x <= 3:",
            "                _lf25_block5x5.append(255.0)",
            "            else:",
            "                _lf25_block5x5.append(0.0)",
            "    var _lf25_ring5x5 = List[Float64]()",
            "    for y in range(5):",
            "        for x in range(5):",
            "            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):",
            "                _lf25_ring5x5.append(255.0)",
            "            else:",
            "                _lf25_ring5x5.append(0.0)",
            "    var _lf36_components6x6 = List[Float64]()",
            "    for y in range(6):",
            "        for x in range(6):",
            "            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):",
            "                _lf36_components6x6.append(255.0)",
            "            else:",
            "                _lf36_components6x6.append(0.0)",
            "    var _lf64_doc8x8 = List[Float64]()",
            "    var _lf64_doc8x8_alt = List[Float64]()",
            "    var _lf64_docmask8x8 = List[Float64]()",
            "    for y in range(8):",
            "        for x in range(8):",
            "            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):",
            "                _lf64_doc8x8.append(20.0)",
            "                _lf64_doc8x8_alt.append(60.0)",
            "                _lf64_docmask8x8.append(255.0)",
            "            else:",
            "                _lf64_doc8x8.append(240.0)",
            "                _lf64_doc8x8_alt.append(235.0)",
            "                _lf64_docmask8x8.append(0.0)",
            "    var _lf36_adaptive_doc6x6 = List[Float64]()",
            "    for y in range(6):",
            "        for x in range(6):",
            "            if y == 2 and x >= 2 and x <= 3:",
            "                _lf36_adaptive_doc6x6.append(40.0)",
            "            elif x < 3:",
            "                _lf36_adaptive_doc6x6.append(220.0)",
            "            else:",
            "                _lf36_adaptive_doc6x6.append(245.0)",
            "    var _lf36_skewmask6x6 = List[Float64]()",
            "    for y in range(6):",
            "        for x in range(6):",
            "            if y >= 1 and y <= 4 and x == y:",
            "                _lf36_skewmask6x6.append(255.0)",
            "            else:",
            "                _lf36_skewmask6x6.append(0.0)",
            "    var _lf64_blobdoc8x8 = List[Float64]()",
            "    for y in range(8):",
            "        for x in range(8):",
            "            if (y >= 2 and y <= 4 and x >= 1 and x <= 3) or (x == 6 and (y == 1 or y == 2)):",
            "                _lf64_blobdoc8x8.append(20.0)",
            "            else:",
            "                _lf64_blobdoc8x8.append(235.0)",
            "    var _lf64_doccolumns8x8 = List[Float64]()",
            "    for y in range(8):",
            "        for x in range(8):",
            "            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):",
            "                _lf64_doccolumns8x8.append(255.0)",
            "            else:",
            "                _lf64_doccolumns8x8.append(0.0)",
            "    var _lf81_doctable9x9 = List[Float64]()",
            "    for y in range(9):",
            "        for x in range(9):",
            "            if ((y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)) and ((x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)):",
            "                _lf81_doctable9x9.append(255.0)",
            "            else:",
            "                _lf81_doctable9x9.append(0.0)",
            "    var _lf256_texture16x16 = List[Float64]()",
            "    for y in range(16):",
            "        for x in range(16):",
            "            if y >= 8 and x >= 8:",
            "                _lf256_texture16x16.append(255.0 if (x + y) % 2 == 0 else 0.0)",
            "            else:",
            "                _lf256_texture16x16.append(64.0)",
            "    var _lf75_video_motion3x5x5 = List[Float64]()",
            "    for _ in range(25):",
            "        _lf75_video_motion3x5x5.append(10.0)",
            "    for y in range(5):",
            "        for x in range(5):",
            "            if y >= 1 and y <= 2 and x >= 1 and x <= 2:",
            "                _lf75_video_motion3x5x5.append(200.0)",
            "            else:",
            "                _lf75_video_motion3x5x5.append(10.0)",
            "    for y in range(5):",
            "        for x in range(5):",
            "            if (y >= 1 and y <= 2 and x >= 1 and x <= 2) or (x == 4 and y == 4):",
            "                _lf75_video_motion3x5x5.append(200.0)",
            "            else:",
            "                _lf75_video_motion3x5x5.append(10.0)",
            "    var _lf16_grid4x4 = List[Float64]()",
            "    for i in range(16):",
            "        _lf16_grid4x4.append(Float64(i))",
            "    var _li5 = List[Int]()",
            "    _li5.append(0); _li5.append(1); _li5.append(2)",
            "    _li5.append(3); _li5.append(4)",
            "    var _li4_box_a = List[Int]()",
            "    _li4_box_a.append(0); _li4_box_a.append(0); _li4_box_a.append(2); _li4_box_a.append(2)",
            "    var _li4_box_b = List[Int]()",
            "    _li4_box_b.append(1); _li4_box_b.append(1); _li4_box_b.append(3); _li4_box_b.append(3)",
            "    var _lb5 = List[Bool]()",
            "    _lb5.append(True); _lb5.append(False); _lb5.append(True)",
            "    _lb5.append(True); _lb5.append(False)",
            "    var _lub5 = List[UInt8]()",
            "    _lub5.append(1); _lub5.append(2); _lub5.append(3)",
            "    _lub5.append(4); _lub5.append(5)",
            # Pre-built 3x3 float matrix (avoids repeated allocation in loop for overrides)
            "    var _llf3 = List[List[Float64]]()",
            "    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())",
            "    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)",
            "    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)",
            "    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)",
            "    var _llf3_imageops = List[List[Float64]]()",
            "    _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]())",
            "    _llf3_imageops[0].append(0.5); _llf3_imageops[0].append(0.6); _llf3_imageops[0].append(0.7)",
            "    _llf3_imageops[1].append(0.4); _llf3_imageops[1].append(0.3); _llf3_imageops[1].append(0.2)",
            "    _llf3_imageops[2].append(0.1); _llf3_imageops[2].append(0.2); _llf3_imageops[2].append(0.3)",
            # Pre-built 3x3 Matrix (linalg and linalg_ext overrides reference _mat3)
            *(
                [
                    "    var _mat3_data = List[Float64]()",
                    "    _mat3_data.append(1.0); _mat3_data.append(0.0); _mat3_data.append(0.0)",
                    "    _mat3_data.append(0.0); _mat3_data.append(2.0); _mat3_data.append(0.0)",
                    "    _mat3_data.append(0.0); _mat3_data.append(0.0); _mat3_data.append(3.0)",
                    "    var _mat3 = mat_from_list(_mat3_data, 3, 3)",
                ]
                if lib in {"linalg", "linalg_ext"}
                else []
            ),
            f"    var N: Int = {n}",
            "",
        ]
    )

    for fn in fns:
        args_list = _arg_values(fn)
        if args_list is None:
            continue
        if fn.ret.startswith("SIMD[") or any(
            p.is_mut and not p.typ.startswith("List[") for p in fn.params
        ):
            continue

        mojo_args: list[str] = []
        mojo_override = _MOJO_PARAM_OVERRIDES.get((lib, fn.name)) or _PARAM_OVERRIDES.get(
            (lib, fn.name)
        )
        for idx, p in enumerate(fn.params):
            mojo_args.append(_mojo_arg(p, mojo_override, idx))

        call = f"{fn.name}({', '.join(mojo_args)})"
        vn = f"_acc_{fn.name}"
        lines += [
            f"    var {vn}: Float64 = 0.0",
            f"    var _t0_{fn.name} = perf_counter_ns()",
            "    for _ in range(N):",
        ]
        # Accumulate differently based on return type
        primitive_types = {
            "Float64",
            "Float32",
            "Int",
            "Bool",
            "UInt64",
            "UInt32",
            "UInt8",
            "String",
            "None",
        }
        if fn.ret == "Float64":
            lines.append(f"        {vn} += {call}")
        elif fn.ret in ("Int", "Bool", "UInt64", "UInt32", "UInt8"):
            lines.append(f"        {vn} += Float64({call})")
        elif fn.ret.startswith("List["):
            # List-returning: accumulate length to prevent dead-code elim
            lines.append(f"        var _r_{fn.name} = {call}")
            lines.append(f"        {vn} += Float64(len(_r_{fn.name}))")
        elif fn.ret not in primitive_types and fn.ret != "None" and not fn.ret.startswith("SIMD["):
            if fn.ret in copyable_structs:
                # Copyable struct: store in 1-element List to prevent DCE
                lines_before = [
                    f"    var _keeper_{fn.name} = List[{fn.ret}]()",
                    f"    _keeper_{fn.name}.append({call})",
                ]
                # Insert before timing block (pop last 3 lines, insert keepers, re-add)
                timing_lines = lines[-3:]
                lines[-3:] = lines_before + timing_lines
                lines.append(f"        _keeper_{fn.name}[0] = {call}")
                lines.append(f"        {vn} += Float64(len(_keeper_{fn.name}))")
            else:
                # Non-Copyable struct: access a numeric field to prevent DCE
                fields = struct_fields.get(fn.ret, [])
                numeric_field = next(
                    (
                        f
                        for f, t in fields
                        if t in ("Float64", "Float32", "Int", "UInt32", "UInt64")
                    ),
                    None,
                )
                if numeric_field:
                    lines.append(f"        var _r_{fn.name} = {call}")
                    lines.append(f"        {vn} += Float64(_r_{fn.name}.{numeric_field})")
                else:
                    lines.append(f"        _ = {call}")
        else:
            lines.append(f"        _ = {call}")
        lines += [
            f"    var _t1_{fn.name} = perf_counter_ns()",
            f"    var _ns_{fn.name} = Float64(_t1_{fn.name} - _t0_{fn.name}) / Float64(N)",
            f'    print("MOJO_TIMING {lib}::{fn.name}", _ns_{fn.name}, {vn})',
        ]
        summary_expr = _mojo_summary_call_expression(lib, fn, f"_result_{fn.name}")
        if summary_expr is not None:
            lines += [
                f"    var _result_{fn.name} = {call}",
                f"    var _summary_{fn.name} = {summary_expr}",
                f'    print("MOJO_RESULT {lib}::{fn.name}", _summary_{fn.name})',
            ]

    return "\n".join(lines) + "\n"


# ── benchmark runner ──────────────────────────────────────────────────────────


def _run_mojo_benchmark(
    lib: str, bench_file: Path
) -> tuple[dict[str, float], dict[str, str], str | None]:
    """Run a Mojo benchmark file and parse per-function ns-per-call + summaries."""
    try:
        result = subprocess.run(
            ["pixi", "run", "mojo", "run", f"-I{MOJO_DIR}", str(bench_file)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=str(MOJO_ENV),
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return {}, {}, "timeout"
    except Exception:
        return {}, {}, "runner_error"

    timings: dict[str, float] = {}
    summaries: dict[str, str] = {}
    for line in output.splitlines():
        m = re.match(r"MOJO_TIMING\s+(\S+)\s+([\d.e+\-]+)", line)
        if m:
            fn_key = m.group(1)  # "lib::fn"
            ns = float(m.group(2))
            timings[fn_key] = ns
            continue
        m = re.match(r"MOJO_RESULT\s+(\S+)\s+(.+)", line)
        if m:
            summaries[m.group(1)] = m.group(2).strip()
    error = None if result.returncode == 0 else output.strip()[-400:]
    return timings, summaries, error


def _run_python_benchmark(lib: str, py_src: str, fns: list[FnInfo]) -> dict[str, dict]:
    """Import generated Python lib, call each function N times, return timing + value."""
    ns = {}
    try:
        exec(compile(py_src, f"<{lib}>", "exec"), ns)
    except Exception as e:
        # Return all functions as errored
        err = f"{type(e).__name__}: {e}"[:80]
        return {
            f"{lib}::{fn.name}": {"py_ns": None, "py_result": None, "py_error": err} for fn in fns
        }

    results: dict[str, dict] = {}
    for fn in fns:
        args = _arg_values(fn)
        if args is None:
            continue
        py_fn = ns.get(fn.name)
        if py_fn is None:
            continue
        try:
            # Evaluate arg literals (use module namespace so struct types resolve)
            py_args = [eval(a, ns) for a in args]
            # Warmup
            py_fn(*py_args)
            start_time = time.perf_counter()
            acc = 0.0
            for _ in range(N_ITER):
                v = py_fn(*py_args)
                if isinstance(v, float):
                    acc += v
                elif isinstance(v, int | bool):
                    acc += float(v)
            t1 = time.perf_counter()
            ns_per_call = (t1 - start_time) * 1e9 / N_ITER
            results[f"{lib}::{fn.name}"] = {
                "py_ns": ns_per_call,
                "py_result": float(v) if isinstance(v, int | float | bool) else None,
                "py_summary": _python_result_summary(v, lib=lib, function=fn.name),
            }
        except Exception as e:
            results[f"{lib}::{fn.name}"] = {
                "py_ns": None,
                "py_result": None,
                "py_summary": None,
                "py_error": str(e)[:80],
            }
    return results


def run_library_benchmark(entry: LibEntry) -> dict[str, Any]:
    """Full benchmark for one library. Returns result dict."""
    lib_path = entry.path
    lib = entry.lib_id
    import_path = entry.import_path
    t_start = time.perf_counter()

    # 1. Parse
    fns = parse_library(lib_path, lib_id=lib)
    testable = [
        f
        for f in fns
        if not f.name.startswith("_")
        if _arg_values(f) is not None
        and not f.ret.startswith("SIMD[")
        and not any(p.is_mut and not p.typ.startswith("List[") for p in f.params)
        and not any(p.typ in SKIP_PARAM_TYPES for p in f.params)
        and not any(any(p.typ.startswith(pfx) for pfx in _SKIP_TYPE_PREFIXES) for p in f.params)
    ]
    testable = _filter_testable_functions_for_library(lib, testable)
    if not testable:
        return {"lib": lib, "status": "skipped", "reason": "no testable functions"}

    # 2. Generate Python equivalent (pass ALL fns so private helpers are included)
    manual_py_src = _manual_python_source(lib)
    if manual_py_src is not None:
        py_src = manual_py_src
        transpiled = _manual_transpiled_functions(lib, testable)
    else:
        py_src, transpiled = generate_python_lib(
            lib, fns, import_path=import_path, lib_path=lib_path
        )
    (PY_LIBS / f"{lib}.py").write_text(py_src, encoding="utf-8")

    # 3. Generate Mojo benchmark
    mojo_bench_src = generate_mojo_benchmark(
        lib, transpiled, N_ITER, import_path=import_path, lib_path=lib_path
    )
    if not mojo_bench_src:
        return {"lib": lib, "status": "skipped", "reason": "no Mojo benchmark generated"}
    bench_file = MOJO_BENCH / f"bench_{lib}.mojo"
    bench_file.write_text(mojo_bench_src, encoding="utf-8")

    # 4. Run Python benchmark
    py_results = _run_python_benchmark(lib, py_src, transpiled)

    # 5. Run Mojo benchmark
    mojo_timings, mojo_summaries, mojo_error = _run_mojo_benchmark(lib, bench_file)

    # 6. Merge results
    fn_results: list[dict] = []
    total_py_ns = 0.0
    total_mojo_ns = 0.0
    n_compared = 0
    n_timed = 0

    for fn in transpiled:
        key = f"{lib}::{fn.name}"
        py = py_results.get(key, {})
        py_ns = py.get("py_ns")
        py_val = py.get("py_result")
        py_summary = py.get("py_summary")
        py_err = py.get("py_error")
        mojo_ns = mojo_timings.get(key)
        mojo_summary = mojo_summaries.get(key)

        speedup = None
        if py_summary is not None and mojo_summary is not None:
            n_compared += 1
        if py_ns is not None and mojo_ns is not None:
            if mojo_ns > 0 and py_ns > 0:
                speedup = py_ns / mojo_ns
                total_py_ns += py_ns
                total_mojo_ns += mojo_ns
            n_timed += 1

        fn_results.append(
            {
                "function": fn.name,
                "py_ns": round(py_ns, 3) if py_ns is not None else None,
                "mojo_ns": round(mojo_ns, 3) if mojo_ns is not None else None,
                "speedup_x": round(speedup, 2) if speedup else None,
                "py_result": round(py_val, 6)
                if py_val is not None and not math.isnan(py_val)
                else py_val,
                "py_summary": py_summary,
                "mojo_summary": mojo_summary,
                "result_match": _result_summaries_match(py_summary, mojo_summary),
                "py_error": py_err,
            }
        )

    overall_speedup = (total_py_ns / total_mojo_ns) if total_mojo_ns > 0 else None
    elapsed = time.perf_counter() - t_start

    result = {
        "lib": lib,
        "status": "ok",
        "n_functions": len(fn_results),
        "n_compared": n_compared,
        "n_timed": n_timed,
        "overall_speedup_x": round(overall_speedup, 2) if overall_speedup is not None else None,
        "total_py_ns": round(total_py_ns, 2),
        "total_mojo_ns": round(total_mojo_ns, 2),
        "elapsed_s": round(elapsed, 2),
        "n_iterations": N_ITER,
        "mojo_error": mojo_error,
        "functions": fn_results,
    }

    # Save per-library JSON
    (RESULTS / f"{lib}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    for d in [RESULTS, MOJO_BENCH, PY_LIBS]:
        d.mkdir(parents=True, exist_ok=True)

    # Ensure python_libs is on sys.path so cross-module imports work inside exec()
    import sys as _sys

    py_libs_str = str(PY_LIBS)
    if py_libs_str not in _sys.path:
        _sys.path.insert(0, py_libs_str)

    libs = get_all_libs()

    inventory_breakdown = get_benchmark_inventory_breakdown(libs)
    shipping_contract = get_shipping_runtime_contract_counts()

    print("=" * 72)
    print("  Mojo vs Python — Benchmark Suite (Dynamic Discovery Inventory)")
    print("=" * 72)
    print(
        "  Discovery inventory: "
        f"{inventory_breakdown['total_libraries']} libraries "
        f"({inventory_breakdown['top_level_library_count']} top-level, "
        f"{inventory_breakdown['nested_library_count']} nested)"
    )
    print(
        "  Shipping contract:   "
        f"{shipping_contract['module_count']} modules / "
        f"{shipping_contract['function_count']} functions"
    )
    print(f"  Iterations: {N_ITER:,} per function")
    print(f"  Workers:    {WORKERS} parallel")
    print(f"  Timeout:    {TIMEOUT}s per library")
    print("=" * 72)

    suite_start = time.perf_counter()
    all_results: list[dict] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(run_library_benchmark, entry): entry for entry in libs}
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            all_results.append(r)
            lib = r["lib"]
            if r["status"] == "skipped":
                print(f"  ⏭️  {lib:<42} skipped ({r.get('reason', '')})")
            else:
                sp = r.get("overall_speedup_x")
                sp_str = f"{sp:+.1f}x" if sp else "n/a"
                icon = "✅" if (sp is None or sp > 0) else "⚠️ "
                print(
                    f"  {icon}  {lib:<42}  speedup={sp_str:<8}  "
                    f"py={r['total_py_ns']:.0f}ns  "
                    f"mojo={r['total_mojo_ns']:.0f}ns  "
                    f"({r['elapsed_s']:.1f}s)"
                )

    suite_duration = time.perf_counter() - suite_start

    # Sort alphabetically for report
    all_results.sort(key=lambda r: r["lib"])

    # ── summary JSON ──
    summary: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_iterations": N_ITER,
        "n_libraries": len(all_results),
        "suite_duration_s": round(suite_duration, 1),
        "benchmark_inventory": inventory_breakdown,
        "shipping_runtime_contract": shipping_contract,
        "total_functions_declared": sum(r.get("n_functions", 0) for r in all_results),
        "total_functions_compared": sum(r.get("n_compared", 0) for r in all_results),
        "libraries": [],
    }
    total_speedups = [r["overall_speedup_x"] for r in all_results if r.get("overall_speedup_x")]
    if total_speedups:
        summary["median_speedup_x"] = round(sorted(total_speedups)[len(total_speedups) // 2], 2)
        summary["mean_speedup_x"] = round(sum(total_speedups) / len(total_speedups), 2)
        summary["max_speedup_x"] = round(max(total_speedups), 2)
        summary["min_speedup_x"] = round(min(total_speedups), 2)

    for r in all_results:
        summary["libraries"].append(
            {
                "lib": r["lib"],
                "status": r["status"],
                "n_functions": r.get("n_functions", 0),
                "n_compared": r.get("n_compared", 0),
                "speedup_x": r.get("overall_speedup_x"),
                "py_total_ns": r.get("total_py_ns"),
                "mojo_total_ns": r.get("total_mojo_ns"),
            }
        )

    SUMMARY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ── summary TXT ──
    txt_lines = [
        "Mojo vs Python Benchmark Summary",
        f"Generated: {summary['timestamp']}",
        "Inventory kind: benchmark discovery lane (dynamic scan of benchmarkable mojo/engine libraries)",
        f"Iterations per function: {N_ITER:,}",
        f"Libraries benchmarked: {inventory_breakdown['total_libraries']}",
        f"  Top-level libraries: {inventory_breakdown['top_level_library_count']}",
        f"  Nested libraries:    {inventory_breakdown['nested_library_count']}",
        "Shipping runtime contract: "
        f"{shipping_contract['module_count']} modules / {shipping_contract['function_count']} functions",
        "  Note: benchmark discovery is broader than the signed shipping manifest by design.",
        f"Functions declared: {summary['total_functions_declared']}",
        f"Functions compared: {summary['total_functions_compared']}",
        f"Suite duration: {suite_duration:.1f}s",
        "",
    ]
    if total_speedups:
        txt_lines += [
            "Overall speedup (Mojo vs Python):",
            f"  Median: {summary['median_speedup_x']}x",
            f"  Mean:   {summary['mean_speedup_x']}x",
            f"  Max:    {summary['max_speedup_x']}x",
            f"  Min:    {summary['min_speedup_x']}x",
            "",
        ]

    txt_lines += [
        f"{'Library':<42} {'Speedup':>9} {'Python ns':>12} {'Mojo ns':>10} {'Fns':>5}",
        "-" * 82,
    ]
    for r in all_results:
        sp = r.get("overall_speedup_x")
        sp_s = f"{sp:.2f}x" if sp else "n/a"
        txt_lines.append(
            f"  {r['lib']:<40} {sp_s:>9} "
            f"{r.get('total_py_ns', 0):>12.1f} "
            f"{r.get('total_mojo_ns', 0):>10.1f} "
            f"{r.get('n_compared', 0):>5}"
        )

    # Per-function detail for top/bottom speedups
    all_fns: list[dict] = []
    for r in all_results:
        for fn in r.get("functions", []):
            if fn.get("speedup_x"):
                all_fns.append({**fn, "lib": r["lib"]})
    all_fns.sort(key=lambda f: -(f["speedup_x"] or 0))

    if all_fns:
        txt_lines += ["", "Top 20 Fastest Mojo Functions:", "-" * 60]
        for fn in all_fns[:20]:
            txt_lines.append(
                f"  {fn['lib']:<30}::{fn['function']:<30} "
                f"{fn['speedup_x']:>6.1f}x  "
                f"(py={fn['py_ns']:.1f}ns  mojo={fn['mojo_ns']:.1f}ns)"
            )
        txt_lines += ["", "Bottom 20 (closest to Python speed):", "-" * 60]
        for fn in all_fns[-20:]:
            txt_lines.append(
                f"  {fn['lib']:<30}::{fn['function']:<30} "
                f"{fn['speedup_x']:>6.1f}x  "
                f"(py={fn['py_ns']:.1f}ns  mojo={fn['mojo_ns']:.1f}ns)"
            )

    SUMMARY_TXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_TXT_PATH.write_text("\n".join(txt_lines), encoding="utf-8")

    # ── console final ──
    print()
    print("=" * 72)
    print("  BENCHMARK SUMMARY")
    print("=" * 72)
    if total_speedups:
        print(
            f"  Median speedup:  {summary['median_speedup_x']}x  "
            f"(mean={summary['mean_speedup_x']}x  "
            f"max={summary['max_speedup_x']}x)"
        )
    print(f"  Total functions compared: {sum(r.get('n_compared', 0) for r in all_results)}")
    print(f"  Suite duration: {suite_duration:.1f}s")
    print(f"  Results written to {BENCH_DIR}/")
    print(f"    {SUMMARY_JSON_PATH}")
    print(f"    {SUMMARY_TXT_PATH}")
    print(f"    results/<lib>.json  ({len(all_results)} files)")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
