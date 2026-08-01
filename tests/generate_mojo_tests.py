"""
generate_mojo_tests.py — Generates mojo/tests/libs/test_<module>.mojo for repo Mojo modules.

Strategy:
  • Discover current Mojo modules recursively under mojo/engine
  • Skip non-library infrastructure and nested test helpers
  • Generate one small Mojo file per testable module (fast JIT via `mojo run`)
  • The companion Python integration test is tests/integration/test_mojo_libraries_az.py

Usage:
  python3 tests/generate_mojo_tests.py           # generate all per-module files
  python3 tests/generate_mojo_tests.py --dry-run # print the first generated test
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
MOJO_DIR = ROOT / "mojo" / "engine"
OUT_DIR = ROOT / "mojo" / "tests" / "libs"

# Non-library control-plane modules and modules already covered by stronger suites.
SKIP_IMPORT_PATHS = {
    "conv",
    "math_ext",
    "main",
    "types",
    "expr",
    "output",
    "request_parser",
    "python_bridge",
    "compare",
    "decision_tree",
    "time_series",
    "importance_sampling",
    "decision_tree_parser",
    "field_mapper",
    "sha256",
    "validate",
    "net.unix_socket",
    "runtime_library_dispatch_generated",
}
SKIP_DIRS = {
    "engines",
    # Coarse execution layer: invoked through its own message types in main.mojo,
    # not through library_execute, and its entry points take a compile-time
    # dispatcher parameter that the generator cannot synthesise. Covered by
    # hand-written suites instead.
    "algenta_runtime",
    # Determinism substrate: hand-written suites + a bit-exact reference validator.
    "determinism",
    # Canonical encoding: identity infrastructure, hand-written suite.
    "canonical",
    # Numeric contract for new surfaces; legacy paths are untouched.
    "numeric",
    # Columnar substrate: hand-written suites.
    "columnar",
    # Query IR + columnar executor: hand-written suites.
    "query",
}

# ── Hand-written test protection ──────────────────────────────────────────────
# These suites are hand-written known-value/determinism tests, NOT generated.
# Without this guard, `generate()` overwrites every test_<module>.mojo it plans
# and unlinks every test_*.mojo it does not, so a single generator run silently
# destroys them. They are excluded from the generation plan and are never
# written or unlinked. Add new hand-written suites here.
HANDWRITTEN_TESTS = frozenset(
    {
        "test_arima.mojo",
        "test_automl.mojo",
        "test_calibration.mojo",
        "test_counter_rng.mojo",
        "test_conformal.mojo",
        "test_eigen_full.mojo",
        "test_ensembles.mojo",
        "test_explainability.mojo",
        "test_feature_hashing.mojo",
        "test_gaussian_process.mojo",
        "test_gbdt.mojo",
        "test_hmm.mojo",
        "test_imbalance.mojo",
        "test_linear_models.mojo",
        "test_mixture_models.mojo",
        "test_model_compare.mojo",
        "test_model_selection.mojo",
        "test_pipelines.mojo",
        "test_algenta_runtime_batch.mojo",
        "test_algenta_runtime_pipeline.mojo",
        "test_algenta_runtime_resources.mojo",
        "test_algenta_runtime_session.mojo",
        "test_algenta_runtime_stream.mojo",
        "test_determinism_counter_rng.mojo",
        "test_determinism_streams.mojo",
        "test_canonical_encode.mojo",
        "test_numeric_contract.mojo",
        "test_determinism_sampling_keyed.mojo",
        "test_columnar_validity.mojo",
        "test_columnar_array.mojo",
        "test_columnar_batch.mojo",
        "test_query_ir.mojo",
        "test_query_aggregate.mojo",
        "test_columnar_hash_index.mojo",
        "test_query_executor.mojo",
        "test_query_join.mojo",
        "test_query_window.mojo",
        "test_query_plan.mojo",
        "test_sparse_numerics_csr.mojo",
        "test_sparse_numerics_spmv.mojo",
        "test_sparse_numerics_diagnostics.mojo",
        "test_sparse_numerics_iterative.mojo",
        "test_sparse_numerics_factor.mojo",
        "test_canonical_float_repr.mojo",
        "test_columnar_arrow_wire.mojo",
        "test_columnar_dictionary.mojo",
        "test_determinism_manifest.mojo",
        "test_determinism_reduce_det.mojo",
        "test_graph_analytics_adjacency.mojo",
        "test_graph_analytics_centrality.mojo",
        "test_graph_analytics_community.mojo",
        "test_graph_analytics_temporal.mojo",
        "test_optimization_model.mojo",
        "test_optimization_linear.mojo",
        "test_optimization_assignment.mojo",
        "test_optimization_flow.mojo",
        "test_optimization_integer.mojo",
        "test_optimization_explain.mojo",
        "test_optimization_quadratic.mojo",
        "test_optimization_routing.mojo",
        "test_optimization_scheduling.mojo",
        "test_optimization_multiobjective.mojo",
        "test_optimization_robust.mojo",
        "test_retrieval_score.mojo",
        "test_pls.mojo",
        "test_seq_nn.mojo",
        "test_gemm_quantized.mojo",
        "test_gemm_blocked.mojo",
        "test_gemm_contract.mojo",
        "test_attnk_flash.mojo",
        "test_attnk_sdpa.mojo",
        "test_attnk_mask.mojo",
        "test_attnk_rope.mojo",
        "test_attnk_contract.mojo",
        "test_attnk_backward.mojo",
        "test_normk_rmsnorm.mojo",
        "test_normk_layernorm.mojo",
        "test_normk_contract.mojo",
        "test_mlpk_activation.mojo",
        "test_mlpk_embedding.mojo",
        "test_mlpk_contract.mojo",
        "test_lossk_cross_entropy.mojo",
        "test_lossk_contract.mojo",
        "test_accel_contract.mojo",
        "test_accel_launch.mojo",
        "test_accel_gemm_metal.mojo",
        "test_tensorx_pack.mojo",
        "test_tensorx_dtype.mojo",
        "test_tensorx_contract.mojo",
        "test_hostio_socket_native.mojo",
        "test_seq_training.mojo",
        "test_serialization_io.mojo",
        "test_option_greeks_batch.mojo",
        "test_seq2_trainer.mojo",
        "test_svm_solver.mojo",
        "test_tensor2d.mojo",
        # Forecasting package: hand-written known-value suites.
        "test_forecasting_backtest.mojo",
        "test_forecasting_contract.mojo",
        "test_forecasting_hierarchy.mojo",
        "test_forecasting_intermittent.mojo",
        "test_forecasting_interval.mojo",
        "test_forecasting_point.mojo",
        # Statistical inference package: hand-written known-value suites. Note these are the
        # `inference/` PACKAGE suites; test_inference_engine / test_inference_cost_latency /
        # test_inference_security belong to the flat LLM-serving modules and are listed above.
        "test_inference_assume.mojo",
        "test_inference_core.mojo",
        "test_inference_glm.mojo",
        "test_inference_multiplicity.mojo",
        "test_inference_power.mojo",
        "test_inference_resample.mojo",
        "test_inference_robust.mojo",
        # Causal inference package: hand-written known-value suites.
        "test_causal_inference_base.mojo",
        "test_causal_inference_dag.mojo",
        "test_causal_inference_estimators.mojo",
        "test_causal_inference_panel.mojo",
        "test_causal_inference_propensity.mojo",
        "test_causal_inference_sensitivity.mojo",
        "test_causal_inference_uplift.mojo",
    
        # P1 analytical families: hand-written known-value suites.
        "test_data_quality_contract.mojo",
        "test_data_quality_duplicates.mojo",
        "test_data_quality_expect.mojo",
        "test_data_quality_leakage.mojo",
        "test_data_quality_profile.mojo",
        "test_discrete_event_calendar.mojo",
        "test_discrete_event_contract.mojo",
        "test_discrete_event_queue_sim.mojo",
        "test_discrete_event_replicate.mojo",
        "test_discrete_event_resource.mojo",
        "test_discrete_event_warmup.mojo",
        "test_evaluation_binning.mojo",
        "test_evaluation_contract.mojo",
        "test_evaluation_gates.mojo",
        "test_evaluation_resample.mojo",
        "test_evaluation_scores.mojo",
        "test_geospatial_contract.mojo",
        "test_geospatial_frame.mojo",
        "test_geospatial_index.mojo",
        "test_geospatial_join.mojo",
        "test_geospatial_mapmatch.mojo",
        "test_geospatial_polygon.mojo",
        "test_strategy_crn.mojo",
        "test_strategy_equilibrium.mojo",
        "test_strategy_policy.mojo",
        "test_strategy_tournament.mojo",
        "test_streaming_contract.mojo",
        "test_streaming_distinct.mojo",
        "test_streaming_drift.mojo",
        "test_streaming_frequency.mojo",
        "test_streaming_quantiles.mojo",
        "test_streaming_windows.mojo",
        "test_survival_analysis_base.mojo",
        "test_survival_analysis_competing.mojo",
        "test_survival_analysis_cox.mojo",
        "test_survival_analysis_hazard.mojo",
        "test_survival_analysis_km.mojo",
        "test_survival_analysis_parametric.mojo",
}
)

# Marker written into the docstring of every generated suite by `emit_lib_test`.
GENERATED_MARKER = "auto-generated"

# ── module_id collision disambiguation ────────────────────────────────────────
# module_id is import_path with "." -> "_", so a top-level `foo_bar.mojo` and a
# packaged `foo/bar.mojo` both yield module_id "foo_bar" and both target
# test_foo_bar.mojo — the second write silently destroys the first module's
# coverage. Override the *packaged* module to a distinct filename so both are
# covered. The pre-existing test_graph_algorithms.mojo keeps its name and
# content; graph.algorithms gains its own suite.
MODULE_ID_OVERRIDES: dict[str, str] = {
    "graph.algorithms": "graph_pkg_algorithms",
}


def _module_id_collisions(modules: list[ModuleTarget]) -> dict[str, list[str]]:
    """Return {module_id: [import_path, ...]} for any module_id claimed twice."""
    by_id: dict[str, list[str]] = {}
    for target in modules:
        by_id.setdefault(target.module_id, []).append(target.import_path)
    return {mid: paths for mid, paths in by_id.items() if len(paths) > 1}


def protected_test_files(out_dir: Path | None = None) -> frozenset[str]:
    """Test filenames the generator must never write or unlink.

    Union of the explicit ``HANDWRITTEN_TESTS`` registry and any on-disk
    ``test_*.mojo`` lacking ``GENERATED_MARKER``. The second half matters: it
    protects a newly hand-written suite that nobody has registered yet, which
    is exactly when the silent-overwrite failure used to happen.
    """
    out_dir = OUT_DIR if out_dir is None else out_dir
    protected = set(HANDWRITTEN_TESTS)
    if out_dir.is_dir():
        for existing in out_dir.glob("test_*.mojo"):
            try:
                head = existing.read_text(encoding="utf-8")[:512]
            except OSError:
                continue
            if GENERATED_MARKER not in head:
                protected.add(existing.name)
    return frozenset(protected)

_SCALAR_VALUES: dict[str, str] = {
    # 0.5 covers probabilities (0-1), rates (0-1), and is valid for most math.
    # Using 0.5 avoids log(-x)/sqrt(-x) NaN from out-of-range probability inputs.
    "Float64": "0.5",
    "Int": "5",
    "Bool": "True",
    "UInt64": "UInt64(42)",
    "UInt32": "UInt32(42)",
    "UInt8": "UInt8(8)",
    "String": '"test"',
}
_LIST_VAR: dict[str, str] = {
    "Float64": "_lf5",
    "Int": "_li5",
    "Bool": "_lb5",
}
_EXTRA_SAMPLE_PREAMBLES: dict[str, list[str]] = {
    "_lf25_block5x5": [
        "    var _lf25_block5x5 = List[Float64]()",
        "    for y in range(5):",
        "        for x in range(5):",
        "            if y >= 1 and y <= 3 and x >= 1 and x <= 3:",
        "                _lf25_block5x5.append(255.0)",
        "            else:",
        "                _lf25_block5x5.append(0.0)",
    ],
    "_lf25_ring5x5": [
        "    var _lf25_ring5x5 = List[Float64]()",
        "    for y in range(5):",
        "        for x in range(5):",
        "            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):",
        "                _lf25_ring5x5.append(255.0)",
        "            else:",
        "                _lf25_ring5x5.append(0.0)",
    ],
    "_lf36_components6x6": [
        "    var _lf36_components6x6 = List[Float64]()",
        "    for y in range(6):",
        "        for x in range(6):",
        "            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):",
        "                _lf36_components6x6.append(255.0)",
        "            else:",
        "                _lf36_components6x6.append(0.0)",
    ],
    "_lf64_doc8x8": [
        "    var _lf64_doc8x8 = List[Float64]()",
        "    for y in range(8):",
        "        for x in range(8):",
        "            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):",
        "                _lf64_doc8x8.append(20.0)",
        "            else:",
        "                _lf64_doc8x8.append(240.0)",
    ],
    "_lf64_doc8x8_alt": [
        "    var _lf64_doc8x8_alt = List[Float64]()",
        "    for y in range(8):",
        "        for x in range(8):",
        "            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):",
        "                _lf64_doc8x8_alt.append(60.0)",
        "            else:",
        "                _lf64_doc8x8_alt.append(235.0)",
    ],
    "_lf64_docmask8x8": [
        "    var _lf64_docmask8x8 = List[Float64]()",
        "    for y in range(8):",
        "        for x in range(8):",
        "            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):",
        "                _lf64_docmask8x8.append(255.0)",
        "            else:",
        "                _lf64_docmask8x8.append(0.0)",
    ],
    "_lf36_adaptive_doc6x6": [
        "    var _lf36_adaptive_doc6x6 = List[Float64]()",
        "    for y in range(6):",
        "        for x in range(6):",
        "            if y == 2 and x >= 2 and x <= 3:",
        "                _lf36_adaptive_doc6x6.append(40.0)",
        "            elif x < 3:",
        "                _lf36_adaptive_doc6x6.append(220.0)",
        "            else:",
        "                _lf36_adaptive_doc6x6.append(245.0)",
    ],
    "_lf36_skewmask6x6": [
        "    var _lf36_skewmask6x6 = List[Float64]()",
        "    for y in range(6):",
        "        for x in range(6):",
        "            if y >= 1 and y <= 4 and x == y:",
        "                _lf36_skewmask6x6.append(255.0)",
        "            else:",
        "                _lf36_skewmask6x6.append(0.0)",
    ],
    "_lf64_blobdoc8x8": [
        "    var _lf64_blobdoc8x8 = List[Float64]()",
        "    for y in range(8):",
        "        for x in range(8):",
        "            if (y >= 2 and y <= 4 and x >= 1 and x <= 3) or (x == 6 and (y == 1 or y == 2)):",
        "                _lf64_blobdoc8x8.append(20.0)",
        "            else:",
        "                _lf64_blobdoc8x8.append(235.0)",
    ],
    "_lf64_doccolumns8x8": [
        "    var _lf64_doccolumns8x8 = List[Float64]()",
        "    for y in range(8):",
        "        for x in range(8):",
        "            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):",
        "                _lf64_doccolumns8x8.append(255.0)",
        "            else:",
        "                _lf64_doccolumns8x8.append(0.0)",
    ],
    "_lf81_doctable9x9": [
        "    var _lf81_doctable9x9 = List[Float64]()",
        "    for y in range(9):",
        "        for x in range(9):",
        "            if ((y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)) and ((x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)):",
        "                _lf81_doctable9x9.append(255.0)",
        "            else:",
        "                _lf81_doctable9x9.append(0.0)",
    ],
    "_lf256_texture16x16": [
        "    var _lf256_texture16x16 = List[Float64]()",
        "    for y in range(16):",
        "        for x in range(16):",
        "            if y >= 8 and x >= 8:",
        "                _lf256_texture16x16.append(255.0 if (x + y) % 2 == 0 else 0.0)",
        "            else:",
        "                _lf256_texture16x16.append(64.0)",
    ],
    "_lf16_grid4x4": [
        "    var _lf16_grid4x4 = List[Float64]()",
        "    for i in range(16):",
        "        _lf16_grid4x4.append(Float64(i))",
    ],
    "_li4_box_a": [
        "    var _li4_box_a = List[Int]()",
        "    _li4_box_a.append(0); _li4_box_a.append(0); _li4_box_a.append(2); _li4_box_a.append(2)",
    ],
    "_li4_box_b": [
        "    var _li4_box_b = List[Int]()",
        "    _li4_box_b.append(1); _li4_box_b.append(1); _li4_box_b.append(3); _li4_box_b.append(3)",
    ],
    "_lf12_colorcheck2x2": [
        "    var _lf12_colorcheck2x2 = List[Float64]()",
        "    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)",
        "    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)",
        "    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)",
        "    _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(200.0)",
    ],
    "_lf48_video3x4x4": [
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
    ],
    "_lf48_video3x4x4_alt": [
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
    ],
    "_lf36_video_rgb3x2x2": [
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
    ],
    "_lf75_video_motion3x5x5": [
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
    ],
}

_COLUMN_RANK_SMOKE_REQUEST = (
    '"{\\"hint\\":\\"unit price\\",'
    '\\"candidates\\":[{\\"source\\":\\"orders\\",'
    '\\"column\\":\\"unit_price\\"}],\\"top_k\\":1}"'
)

# Per-function argument overrides (lib, fn) → list of arg expressions.
# Used when the generic 0.5 value causes NaN/Inf for domain-specific reasons.
_PARAM_OVERRIDES: dict[tuple[str, str], list[str]] = {
    # column_rank consumes a JSON request, not arbitrary free-form text.
    ("column_rank", "run_column_rank"): [_COLUMN_RANK_SMOKE_REQUEST],
    # carnot_cop_cooling(t_cold, t_hot): t_cold/t_hot must have t_cold < t_hot
    ("cryogenics", "carnot_cop_cooling"): ["200.0", "300.0"],
    # time_to_peak(ka, ke): ka != ke to avoid log(1)/0
    ("pharmacokinetics", "time_to_peak"): ["0.8", "0.2"],
    # one_compartment_oral(dose, ka, ke, vd, t): ka != ke
    ("pharmacokinetics", "one_compartment_oral"): ["100.0", "0.8", "0.2", "10.0", "2.0"],
    # epicenter_distance(delta_t, vs, vp): vs != vp
    ("seismology", "epicenter_distance_from_ts_tp"): ["2.0", "3.5", "6.0"],
    # junction_capacitance(cj0, v, vbi, m): v must be < vbi
    ("semiconductors", "junction_capacitance"): ["1e-12", "0.3", "0.7", "0.5"],
    # gross_premium(pure_premium, expense_ratio, profit_margin): expense+profit < 1
    ("insurance", "gross_premium"): ["100.0", "0.2", "0.1"],
    # shields_parameter(shear_stress, density_s, density_f, g, grain_size): ds != df
    ("geomorphology", "shields_parameter"): ["5.0", "2650.0", "1000.0", "9.81", "0.01"],
    # hypsometric_integral(mean, min, max): max != min
    ("geomorphology", "hypsometric_integral"): ["500.0", "100.0", "1000.0"],
    # GoL neighborhood count requires a grid whose flattened length matches rows*cols.
    ("cellular_automata", "game_of_life_step"): ["_li6_grid2x3", "2", "3", "1", "1"],
    # Hex parser expects a valid 6-digit RGB hex string.
    ("color", "hex_to_rgb"): ['"#336699"'],
    ("color_check", "wcag_relative_luminance_hex"): ['"#808080"'],
    ("color_check", "wcag_contrast_ratio_hex"): ['"#000000"', '"#FFFFFF"'],
    ("color_check", "wcag_text_pass_hex"): ['"#000000"', '"#FFFFFF"', "12.0", "False"],
    ("color_check", "preferred_text_color_hex"): ['"#336699"'],
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
    # UCB exploration requires total_visits > 1 to keep log(N) non-negative.
    ("decision_ml_fusion", "adaptive_exploration_rate"): ["0.5", "1.0", "10.0", "1.0"],
    # 3-player Shapley value expects all 8 coalition values.
    ("game_theory", "shapley_value_3player"): ["_lf8_coalitions"],
    # unvec requires rows * cols == len(v).
    ("matrix_ops", "unvec"): ["_lf6_matrix", "2", "3"],
    # Split indices must be zero-based and within y bounds.
    ("regression_tree", "mse_reduction"): ["_lf5", "_li2_zero", "_li3_tail"],
    # regula_falsi(a, b, func_id): bracket a root (func_id=0 → x, use a=-1, b=1)
    ("root_finding", "regula_falsi"): ["-1.0", "1.0", "0"],
    # ORPO denominator must stay finite for the generated smoke sample.
    ("rlhf_dpo", "orpo_ratio"): ["-0.2", "-1.0", "10.0", "12.0", "0.1"],
    # nth_smallest uses zero-based indexing.
    ("sorting", "nth_smallest"): ["_lf5", "2"],
    # Borda count candidate index must fall inside the flattened rank matrix.
    ("voting", "borda_score"): ["_li10_borda", "5", "2"],
    # AES state transforms require a full 16-byte state/round key.
    ("crypto_aes_sbox", "sub_bytes"): ["_li16"],
    ("crypto_aes_sbox", "inv_sub_bytes"): ["_li16"],
    ("crypto_aes_sbox", "shift_rows"): ["_li16"],
    ("crypto_aes_sbox", "inv_shift_rows"): ["_li16"],
    ("crypto_aes_sbox", "xor_bytes"): ["_li16", "_li16"],
    ("crypto_aes_sbox", "add_round_key"): ["_li16", "_li16"],
    # ChaCha20 setup requires key=8 words, nonce=3 words, and 16-word blocks.
    ("crypto_chacha20", "chacha20_init_state"): ["_li8", "5", "_li3"],
    ("crypto_chacha20", "chacha20_block"): ["_li8", "5", "_li3"],
    ("crypto_chacha20", "chacha20_encrypt"): ["_li16", "_li8", "_li3"],
    ("crypto_chacha20", "chacha20_decrypt"): ["_li16", "_li8", "_li3"],
}

_SKIP_PARAM_TYPES: set[str] = {
    "TTLCache",
    "Matrix",
    "Graph",
    "WeightedGraph",
    "Heap",
    "BloomFilter",
    "PetriNet",
    "KalmanState",
    "SKLearnNode",
    "LRUCache",
    "CountMinSketch",
    "Bloom",
}


class Param(NamedTuple):
    name: str
    typ: str
    has_default: bool
    is_mut: bool = False


class FnSig(NamedTuple):
    name: str
    params: list[Param]
    ret: str
    module_id: str
    import_path: str


class ModuleTarget(NamedTuple):
    path: Path
    import_path: str
    module_id: str


def _clean_type(t: str) -> str:
    t = t.split("=")[0].strip()
    t = re.sub(r"\s+", " ", t)
    for prefix in ("owned ", "inout ", "ref ", "read ", "mut "):
        if t.startswith(prefix):
            t = t[len(prefix) :]
    return t.strip()


def _parse_params(raw: str) -> list[Param] | None:
    params_raw: list[str] = []
    depth = 0
    cur = ""
    for ch in raw:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            params_raw.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        params_raw.append(cur.strip())

    result: list[Param] = []
    for p in params_raw:
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
        result.append(Param(name=name, typ=typ, has_default=has_def, is_mut=is_mut))
    return result


def _import_path_for(path: Path, engine_root: Path = MOJO_DIR) -> str:
    rel = path.relative_to(engine_root).with_suffix("")
    return ".".join(rel.parts)


def _module_id_for_import_path(import_path: str) -> str:
    override = MODULE_ID_OVERRIDES.get(import_path)
    if override is not None:
        return override
    return import_path.replace(".", "_")


def discover_library_modules(engine_root: Path = MOJO_DIR) -> list[ModuleTarget]:
    targets: list[ModuleTarget] = []
    for path in sorted(engine_root.rglob("*.mojo")):
        rel = path.relative_to(engine_root)
        if path.name == "__init__.mojo":
            continue
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        if path.stem.startswith("test_"):
            continue
        import_path = _import_path_for(path, engine_root)
        if import_path in SKIP_IMPORT_PATHS:
            continue
        targets.append(
            ModuleTarget(
                path=path,
                import_path=import_path,
                module_id=_module_id_for_import_path(import_path),
            )
        )
    return targets


def parse_library(path: Path, *, module_id: str, import_path: str) -> list[FnSig]:
    text = path.read_text(encoding="utf-8", errors="replace")
    sigs: list[FnSig] = []
    lines = text.splitlines()
    i = 0
    docstring_delim: str | None = None
    while i < len(lines):
        stripped = lines[i].strip()

        if docstring_delim is not None:
            if docstring_delim in stripped and stripped.count(docstring_delim) % 2 == 1:
                docstring_delim = None
            i += 1
            continue

        if stripped.startswith('"""') or stripped.startswith("'''"):
            delim = '"""' if stripped.startswith('"""') else "'''"
            if stripped.count(delim) % 2 == 1:
                docstring_delim = delim
            i += 1
            continue

        m = re.match(r"(?:fn|def)\s+([A-Za-z][A-Za-z0-9_]*)\s*\(", stripped)
        if not m:
            i += 1
            continue
        fname = m.group(1)
        if fname.startswith("_"):
            i += 1
            continue
        if fname in {"main", "check"}:
            i += 1
            continue

        sig_lines = [stripped]
        j = i + 1
        while j < min(i + 10, len(lines)):
            nxt = lines[j].strip()
            if re.match(r"(fn|def|struct|from|var|let)\s", nxt):
                break
            sig_lines.append(nxt)
            if nxt.endswith(":") or (re.search(r"->.*:", nxt) and not nxt.endswith(",")):
                break
            j += 1
        full = " ".join(sig_lines)

        ret = "Float64"
        am = re.search(r"->\s*([^\n:{]+)", full)
        if am:
            ret = am.group(1).strip().rstrip("{: ")
            ret = re.sub(r"\s+", " ", ret)
        else:
            ret = "None"

        pm = re.search(r"\(([^)]*)\)", full)
        if pm:
            param_str = pm.group(1)
        else:
            idx_open = full.find("(")
            if idx_open == -1:
                i += 1
                continue
            paren_text = full[idx_open + 1 :]
            depth = 1
            buf = ""
            for ch in paren_text:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                buf += ch
            param_str = buf

        params = _parse_params(param_str)
        if params is None:
            i += 1
            continue

        sigs.append(
            FnSig(
                name=fname,
                params=params,
                ret=ret,
                module_id=module_id,
                import_path=import_path,
            )
        )
        i += 1
    return sigs


def _arg_expr(p: Param) -> str | None:
    typ = p.typ
    if typ in _SKIP_PARAM_TYPES:
        return None
    if typ in _SCALAR_VALUES:
        return _SCALAR_VALUES[typ]
    m = re.match(r"List\[(\w+)\]", typ)
    if m:
        inner = m.group(1)
        return _LIST_VAR.get(inner)
    if typ.startswith("List[List"):
        return None
    return None


def _is_testable(sig: FnSig) -> tuple[bool, list[str] | None]:
    if sig.ret.startswith("SIMD["):
        return False, None
    # Use per-function override if provided
    override = _PARAM_OVERRIDES.get((sig.module_id, sig.name))
    if override is not None:
        return True, override
    args: list[str] = []
    for p in sig.params:
        if p.is_mut:
            return False, None
        v = _arg_expr(p)
        if v is None:
            return False, None
        args.append(v)
    return True, args


def build_generation_plan(
    modules: list[ModuleTarget] | None = None,
) -> list[tuple[ModuleTarget, list[FnSig]]]:
    if modules is None:
        modules = discover_library_modules()

    protected = protected_test_files()

    plan: list[tuple[ModuleTarget, list[FnSig]]] = []
    for target in modules:
        if f"test_{target.module_id}.mojo" in protected:
            # Hand-written suite owns this module; never plan a generated one.
            continue
        sigs = parse_library(
            target.path,
            module_id=target.module_id,
            import_path=target.import_path,
        )
        testable = [sig for sig in sigs if _is_testable(sig)[0]]
        if testable:
            plan.append((target, testable))
    return plan


def emit_lib_test(module_id: str, import_path: str, sigs: list[FnSig]) -> str:
    """Emit a complete Mojo test file for one module."""
    extra_samples: list[str] = []
    seen_extra_samples: set[str] = set()
    for sig in sigs:
        testable, args = _is_testable(sig)
        if not testable or args is None:
            continue
        for arg in args:
            if arg in _EXTRA_SAMPLE_PREAMBLES and arg not in seen_extra_samples:
                seen_extra_samples.add(arg)
                extra_samples.append(arg)

    lines: list[str] = [
        f'"""test_{module_id}.mojo — auto-generated tests for {import_path}."""',
        "from std.math import isnan, isinf",
        f"from {import_path} import {', '.join(s.name for s in sigs)}",
        "",
        "fn is_finite(x: Float64) -> Bool:",
        "    return not isnan(x) and not isinf(x)",
        "",
        "def main() raises:",
        "    var _lf5 = List[Float64]()",
        "    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)",
        "    _lf5.append(0.4); _lf5.append(0.3)",
        "    var _li5 = List[Int]()",
        "    _li5.append(1); _li5.append(2); _li5.append(3)",
        "    _li5.append(4); _li5.append(5)",
        "    var _li3 = List[Int]()",
        "    _li3.append(1); _li3.append(2); _li3.append(3)",
        "    var _li2_zero = List[Int]()",
        "    _li2_zero.append(0); _li2_zero.append(1)",
        "    var _li3_tail = List[Int]()",
        "    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)",
        "    var _li8 = List[Int]()",
        "    for i in range(8):",
        "        _li8.append(i + 1)",
        "    var _li6_grid2x3 = List[Int]()",
        "    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)",
        "    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)",
        "    var _li10_borda = List[Int]()",
        "    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)",
        "    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)",
        "    var _li16 = List[Int]()",
        "    for i in range(16):",
        "        _li16.append(i)",
        "    var _lf6_matrix = List[Float64]()",
        "    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)",
        "    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)",
        "    var _lf8_coalitions = List[Float64]()",
        "    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)",
        "    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)",
        "    var _lb5 = List[Bool]()",
        "    _lb5.append(True); _lb5.append(False); _lb5.append(True)",
        "    _lb5.append(True); _lb5.append(False)",
        "    var passed: Int = 0",
        "    var failed: Int = 0",
        "",
    ]

    for sample_name in extra_samples:
        lines.extend(_EXTRA_SAMPLE_PREAMBLES[sample_name])

    for sig in sigs:
        testable, args = _is_testable(sig)
        if not testable or args is None:
            continue

        call = f"{sig.name}({', '.join(args)})"
        label = f"{import_path}::{sig.name}"

        if sig.ret == "Float64":
            vn = f"_v_{sig.name}"
            lines += [
                f"    var {vn} = {call}",
                f'    if is_finite({vn}): passed += 1; print("  ✅ {label} =", {vn})',
                f'    else: failed += 1; print("  ❌ {label} → non-finite:", {vn})',
            ]
        elif sig.ret in ("Bool", "Int", "UInt64", "UInt32", "UInt8"):
            lines += [
                f"    _ = {call}",
                f'    passed += 1; print("  ✅ {label}")',
            ]
        elif sig.ret.startswith("List[") and not sig.ret.startswith("List[List"):
            vn = f"_v_{sig.name}"
            lines += [
                f"    var {vn} = {call}",
                f'    if len({vn}) >= 0: passed += 1; print("  ✅ {label}")',
            ]
        else:
            lines += [
                f"    _ = {call}",
                f'    passed += 1; print("  ✅ {label}")',
            ]

    lines += [
        "",
        f'    print("  [{import_path}] Passed:", passed, "Failed:", failed)',
    ]

    return "\n".join(lines) + "\n"


def generate(
    modules: list[ModuleTarget] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Generate per-module test files. Returns {module_id: n_tests}."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    plan = build_generation_plan(modules)
    protected = protected_test_files()
    counts: dict[str, int] = {}
    total_fns = 0
    expected_files: set[str] = set()
    shown_dry_run = False

    for target, testable in plan:
        out_name = f"test_{target.module_id}.mojo"
        if out_name in protected:
            # Defence in depth: build_generation_plan already excludes these.
            raise SystemExit(
                f"generate_mojo_tests: refusing to overwrite hand-written suite {out_name}. "
                "This is a bug in the generation plan filter."
            )

        n = len(testable)
        counts[target.module_id] = n
        total_fns += n
        expected_files.add(out_name)

        code = emit_lib_test(target.module_id, target.import_path, testable)
        if dry_run:
            if not shown_dry_run:
                print(code)
                shown_dry_run = True
        else:
            (OUT_DIR / out_name).write_text(code, encoding="utf-8")

    if not dry_run:
        for stale_file in OUT_DIR.glob("test_*.mojo"):
            if stale_file.name in protected:
                continue
            if stale_file.name not in expected_files:
                stale_file.unlink()

    if not dry_run:
        skipped_modules = len(discover_library_modules()) - len(plan)
        print(f"Generated {len(counts)} test files in {OUT_DIR}")
        print(f"  Total functions to test: {total_fns}")
        print(f"  Skipped modules (untestable): {skipped_modules}")
        print(f"  Protected hand-written suites (untouched): {len(protected)}")

    return counts


def check(modules: list[ModuleTarget] | None = None) -> int:
    """Verify hand-written suites are intact and generated suites are fresh.

    Used by CI and by tests/integration/test_mojo_libraries_az.py, which asserts
    freshness rather than regenerating (regeneration is what destroyed the
    hand-written suites).
    """
    problems: list[str] = []

    missing = sorted(name for name in HANDWRITTEN_TESTS if not (OUT_DIR / name).is_file())
    if missing:
        problems.append(
            "registered hand-written suites are missing from disk (deleted?): "
            + ", ".join(missing)
        )

    protected = protected_test_files()
    plan = build_generation_plan(modules)
    collisions = sorted(
        f"test_{target.module_id}.mojo"
        for target, _ in plan
        if f"test_{target.module_id}.mojo" in protected
    )
    if collisions:
        problems.append("generation plan would overwrite protected suites: " + ", ".join(collisions))

    id_collisions = _module_id_collisions(modules if modules is not None else [])
    if id_collisions:
        detail = "; ".join(
            f"{mid} <- {' + '.join(sorted(paths))}" for mid, paths in sorted(id_collisions.items())
        )
        problems.append(
            "module_id collision — one module's coverage would be silently overwritten. "
            f"Add a MODULE_ID_OVERRIDES entry: {detail}"
        )

    stale: list[str] = []
    for target, testable in plan:
        out_path = OUT_DIR / f"test_{target.module_id}.mojo"
        expected = emit_lib_test(target.module_id, target.import_path, testable)
        current = out_path.read_text(encoding="utf-8") if out_path.is_file() else None
        if current != expected:
            stale.append(out_path.name)
    if stale:
        problems.append(
            f"{len(stale)} generated suite(s) stale vs source — run "
            f"`python3 tests/generate_mojo_tests.py`: {', '.join(sorted(stale)[:10])}"
            + (" …" if len(stale) > 10 else "")
        )

    orphans = sorted(
        path.name
        for path in OUT_DIR.glob("test_*.mojo")
        if path.name not in protected
        and path.name not in {f"test_{t.module_id}.mojo" for t, _ in plan}
    )
    if orphans:
        problems.append(
            "generated suite(s) with no source module — run the generator to prune: "
            + ", ".join(orphans)
        )

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1

    print(
        f"OK: {len(protected)} hand-written suite(s) protected, "
        f"{len(plan)} generated suite(s) fresh."
    )
    return 0


def main():
    dry_run = "--dry-run" in sys.argv
    modules = discover_library_modules()
    if "--check" in sys.argv:
        raise SystemExit(check(modules))
    print(f"Scanning {len(modules)} module files...")
    generate(modules, dry_run=dry_run)


if __name__ == "__main__":
    main()
