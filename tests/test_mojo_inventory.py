from __future__ import annotations

import time
from pathlib import Path

from apps.runtime import mojo_inventory


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discover_source_modules_collects_recursive_modules(tmp_path: Path) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    _write(engine_root / "finance.mojo", "def npv() -> Float64:\n    return 1.0\n")
    _write(engine_root / "crypto" / "hash.mojo", "fn digest() -> Int:\n    return 1\n")
    _write(engine_root / "crypto" / "__init__.mojo", "")

    modules = mojo_inventory.discover_source_modules(engine_root)

    assert [module.import_path for module in modules] == ["crypto.hash", "finance"]
    assert [module.lib_id for module in modules] == ["crypto_hash", "finance"]
    assert [module.public_functions for module in modules] == [("digest",), ("npv",)]


def test_parse_test_all_import_modules_ignores_std_imports(tmp_path: Path) -> None:
    test_all = tmp_path / "test_all_libraries.mojo"
    test_all.write_text(
        "\n".join(
            [
                "from std.math import is_finite",
                "from finance import npv",
                "from crypto.hash import digest",
            ]
        ),
        encoding="utf-8",
    )

    modules = mojo_inventory.parse_test_all_import_modules(test_all)

    assert modules == ("crypto.hash", "finance")


def test_build_inventory_report_flags_artifact_only_modules(tmp_path: Path) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    test_all = tmp_path / "mojo" / "tests" / "test_all_libraries.mojo"
    benchmark_results = tmp_path / "benchmarks" / "results"
    benchmark_benches = tmp_path / "benchmarks" / "mojo_benchmarks"

    _write(engine_root / "finance.mojo", "fn npv() -> Float64:\n    return 1.0\n")
    _write(engine_root / "crypto" / "hash.mojo", "fn digest() -> Int:\n    return 1\n")
    _write(
        test_all,
        "\n".join(
            [
                "from finance import npv",
                "from accounting import gross_margin",
                "from crypto.hash import digest",
            ]
        ),
    )
    _write(benchmark_results / "finance.json", "{}")
    _write(benchmark_results / "accounting.json", "{}")
    _write(benchmark_benches / "bench_finance.mojo", "from finance import npv\n")
    _write(benchmark_benches / "bench_accounting.mojo", "from accounting import gross_margin\n")

    report = mojo_inventory.build_inventory_report(
        engine_root=engine_root,
        test_all_path=test_all,
        benchmark_results_dir=benchmark_results,
        benchmark_mojo_dir=benchmark_benches,
        threshold_target=3,
    )

    assert report.source_module_count == 2
    assert report.source_modules_with_public_functions_count == 2
    assert report.source_public_function_count == 2
    assert report.test_all_missing_from_source == ("accounting",)
    assert report.benchmark_results_missing_from_source == ("accounting",)
    assert report.benchmark_benches_missing_from_source == ("accounting",)
    assert report.threshold_met is False
    assert report.threshold_gap == 1


def test_runtime_library_manifest_cache_reuses_cached_inventory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    cache_path = tmp_path / ".cache" / "runtime_library_inventory.json"
    _write(
        engine_root / "finance.mojo",
        "fn npv(rate: Float64) -> Float64:\n    return rate\n",
    )

    first = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    assert first[0].import_path == "finance"
    assert cache_path.exists()

    def _unexpected_parse(_: Path) -> tuple[mojo_inventory.RuntimeFunctionSpec, ...]:
        raise AssertionError("runtime inventory should load from manifest cache")

    monkeypatch.setattr(mojo_inventory, "_parse_runtime_function_specs", _unexpected_parse)

    second = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    assert second == first


def test_runtime_library_manifest_cache_invalidates_when_source_changes(tmp_path: Path) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    cache_path = tmp_path / ".cache" / "runtime_library_inventory.json"
    finance_module = engine_root / "finance.mojo"
    _write(
        finance_module,
        "fn npv(rate: Float64) -> Float64:\n    return rate\n",
    )

    first = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    time.sleep(0.01)
    _write(
        finance_module,
        (
            "fn npv(rate: Float64) -> Float64:\n    return rate\n\n"
            "fn irr(rate: Float64) -> Float64:\n    return rate\n"
        ),
    )

    refreshed = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    assert first[0].functions == (
        mojo_inventory.RuntimeFunctionSpec(
            name="npv",
            params=(
                mojo_inventory.RuntimeParamSpec(
                    name="rate",
                    typ="Float64",
                    has_default=False,
                    is_mut=False,
                ),
            ),
            return_type="Float64",
        ),
    )
    assert tuple(spec.name for spec in refreshed[0].functions) == ("npv", "irr")


def test_current_repo_inventory_report_detects_stale_artifact_gap() -> None:
    report = mojo_inventory.build_inventory_report()
    executable_modules = mojo_inventory.discover_runtime_library_modules(executable_only=True)

    assert report.source_module_count > 0
    assert report.source_modules_with_public_functions_count > 0
    assert report.source_public_function_count > 0
    assert report.test_all_missing_from_source == ()
    assert report.threshold_met is True
    assert len(executable_modules) >= 400


def test_llm_rollout_modules_are_runtime_executable() -> None:
    modules = {
        module.import_path: tuple(spec.name for spec in module.functions)
        for module in mojo_inventory.discover_runtime_library_modules(executable_only=True)
    }

    assert modules["text.tokenizer"] == (
        "is_stopword",
        "word_tokenize",
        "sentence_tokenize",
        "char_ngrams",
        "word_ngrams",
        "remove_stopwords",
        "stem_simple",
        "vocabulary_size",
        "token_frequency",
        "pad_sequence",
    )
    assert modules["vector_kernels.ranker"] == ("run_column_rank_v2",)
    assert modules["vector_kernels.table"] == (
        "build_query",
        "source_id_of",
        "role_id_of",
        "build_table_json",
    )
    assert modules["column_rank"] == ("run_column_rank",)
    assert modules["color_science"] == (
        "delta_e_76",
        "lab_to_lch_l",
        "lab_to_lch_c",
        "lab_to_lch_h",
        "rgb_to_luminance",
        "contrast_ratio",
        "wcag_aa_pass",
        "color_temperature_approx",
        "metamerism_index",
        "chromatic_adaptation_von_kries",
        "cri_from_delta_e",
        "whiteness_index_cie",
    )
    assert modules["color_check"] == (
        "wcag_relative_luminance_rgb255",
        "wcag_relative_luminance_hex",
        "wcag_aa_required_contrast",
        "wcag_contrast_ratio_rgb255",
        "wcag_contrast_ratio_hex",
        "wcag_text_pass_rgb255",
        "wcag_text_pass_hex",
        "preferred_text_color_rgb255",
        "preferred_text_color_hex",
        "dominant_background_rgb255",
        "dominant_background_hex",
        "dominant_background_contrast_ratio_hex",
        "dominant_background_wcag_pass_hex",
        "preferred_text_color_for_image",
        "preferred_text_contrast_for_image",
        "preferred_text_pass_for_image",
    )
    assert modules["image_palette"] == (
        "dominant_palette_rgb255",
        "palette_size_estimate",
        "palette_entropy",
        "mean_saturation_rgb255",
        "warm_color_ratio_rgb255",
        "palette_contrast_score",
        "accent_color_hex",
        "is_monochrome_palette",
    )
    assert modules["image_morphology"] == (
        "binary_erode_flat",
        "binary_dilate_flat",
        "binary_open_flat",
        "binary_close_flat",
        "binary_fill_holes_flat",
        "connected_components_4_flat",
        "largest_component_bbox_flat",
        "distance_transform_cityblock_flat",
        "foreground_area_ratio_flat",
    )
    assert modules["document_vision"] == (
        "otsu_threshold_flat",
        "binarize_otsu_flat",
        "adaptive_mean_binarize_flat",
        "horizontal_projection",
        "vertical_projection",
        "mask_content_bbox_flat",
        "skew_angle_estimate_flat",
        "horizontal_text_score_flat",
        "document_scan_quality_flat",
    )
    assert modules["document_layout"] == (
        "text_line_boxes_flat",
        "line_count_flat",
        "column_boxes_flat",
        "column_count_flat",
        "text_density_grid_flat",
        "multi_column_score_flat",
        "table_like_score_flat",
    )
    assert modules["image_similarity"] == (
        "mean_squared_error_flat",
        "mean_abs_error_flat",
        "psnr_flat",
        "normalized_cross_correlation_flat",
        "ssim_global_flat",
        "diff_fraction_flat",
        "crop_region_similarity_flat",
        "duplicate_score_flat",
    )
    assert modules["image_regions"] == (
        "foreground_mask_otsu_flat",
        "connected_component_boxes_flat",
        "largest_foreground_box_flat",
        "saliency_box_flat",
        "extract_box_flat",
        "box_iou",
    )
    assert modules["video_ops"] == (
        "frame_count_from_flat",
        "frame_mean_intensity",
        "frame_mean_intensities",
        "frame_mean_abs_diff",
        "temporal_mean_abs_diff",
        "temporal_max_abs_diff",
        "freeze_frame_ratio",
        "sample_frame_indices",
    )
    assert modules["video_features"] == (
        "scene_change_scores",
        "scene_cut_count",
        "scene_cut_rate",
        "peak_motion_frame",
        "keyframe_indices",
    )
    assert modules["video_color"] == (
        "frame_mean_rgb255",
        "frame_mean_rgb_series",
        "clip_mean_rgb255",
        "dominant_clip_color_rgb255",
        "clip_mean_saturation_rgb255",
        "warm_frame_ratio_rgb255",
        "color_drift_score_rgb255",
        "preferred_text_contrast_for_video",
        "preferred_text_color_for_video",
    )
    assert modules["video_accessibility"] == (
        "frame_min_preferred_text_contrast_for_video",
        "frame_preferred_text_color_for_video",
        "sampled_video_min_text_contrast",
        "sampled_video_wcag_safe_ratio",
        "needs_text_backplate_for_video",
        "subtitle_band_min_preferred_text_contrast_for_video",
        "subtitle_band_preferred_text_color_for_video",
        "sampled_subtitle_band_wcag_safe_ratio",
        "subtitle_band_needs_backplate_for_video",
    )
    assert modules["video_storyboard"] == (
        "scene_start_indices",
        "scene_end_indices",
        "scene_lengths_frames",
        "scene_representative_frames",
        "longest_scene_index",
        "storyboard_frame_indices",
    )
    assert modules["video_quality"] == (
        "frame_quality_series",
        "average_frame_quality",
        "brightness_flicker_score",
        "temporal_stability_score",
        "video_quality_score",
        "is_usable_video",
    )
    assert modules["video_gate"] == (
        "should_use_cached_video",
        "needs_clearer_video",
        "quality_gate_passed_video",
        "is_mostly_static_video",
        "should_extract_keyframes",
        "route_video_request",
    )
    assert modules["video_regions"] == (
        "frame_diff_mask_flat",
        "motion_boxes_between_frames",
        "largest_motion_box_between_frames",
        "temporal_motion_area_series",
        "peak_motion_box_flat",
        "temporal_union_motion_box_flat",
        "motion_coverage_ratio_flat",
    )
    assert modules["video_similarity"] == (
        "frame_duplicate_scores",
        "average_frame_duplicate_score",
        "frame_hash_hamming_series",
        "average_frame_hash_hamming",
        "temporal_signature_distance",
        "clip_duplicate_score_flat",
        "is_duplicate_clip_flat",
    )
    assert modules["crypto.base64"] == (
        "b64_encode",
        "b64_decode",
        "b64_url_encode",
        "b64_url_decode",
    )
    assert modules["crypto.uuid"] == ("uuid4", "uuid4_hex")
    assert modules["json.writer"] == (
        "json_escape_string",
        "json_object_start",
        "json_object_end",
        "json_add_string",
        "json_add_int",
        "json_add_float",
        "json_add_bool",
        "json_add_null",
        "json_add_array_float",
        "json_add_array_string",
        "json_add_raw",
        "json_build_object",
    )
    assert "runtime_library_dispatch_generated" not in modules
    assert modules["rerank_eval"] == (
        "precision_at_k",
        "recall_at_k",
        "hit_rate_at_k",
        "mrr_at_k",
        "map_at_k",
        "ndcg_at_k",
        "pairwise_margin_accuracy",
        "score_separation",
        "latency_weighted_quality",
    )
    assert modules["inference_cost_latency"] == (
        "prompt_token_estimate",
        "completion_token_estimate",
        "kv_cache_bytes",
        "attention_flops",
        "prefill_latency_estimate",
        "decode_latency_estimate",
        "request_cost_estimate",
        "cost_latency_frontier_score",
        "batch_efficiency_estimate",
        "queue_delay_estimate",
        "speculative_decode_gain_estimate",
    )


def test_runtime_executable_function_supports_struct_transport(tmp_path: Path) -> None:
    module_path = tmp_path / "cache.mojo"
    _write(
        module_path,
        "\n".join(
            [
                "struct CacheEntry(Copyable, Movable):",
                "    var key: Int",
                "    var value: Float64",
                "",
                "struct Cache(Copyable, Movable):",
                "    var entries: List[CacheEntry]",
                "    var hits: Int",
                "",
                "fn cache_put(mut cache: Cache, key: Int, value: Float64) -> Cache:",
                "    return cache",
            ]
        ),
    )
    functions = mojo_inventory._parse_runtime_function_specs(module_path)
    struct_specs = mojo_inventory.parse_runtime_struct_specs(module_path)

    assert len(functions) == 1
    assert mojo_inventory.is_runtime_executable_function(
        functions[0],
        import_path="cache",
        struct_specs=struct_specs,
    )


def test_struct_parser_excludes_method_local_variables(tmp_path: Path) -> None:
    module_path = tmp_path / "table.mojo"
    _write(
        module_path,
        "\n".join(
            [
                "struct Table(Copyable, Movable):",
                "    var rows: List[Int]",
                "    var count: Int",
                "",
                "    fn total(self) -> Int:",
                "        var count: Int = 0",
                "        var local_total: Int = 0",
                "        return local_total",
            ]
        ),
    )

    specs = mojo_inventory.parse_runtime_struct_specs(module_path)

    assert tuple((field.name, field.typ) for field in specs["Table"].fields) == (
        ("rows", "List[Int]"),
        ("count", "Int"),
    )


def test_current_repo_non_executable_benchmark_gap_does_not_regress() -> None:
    report = mojo_inventory.build_inventory_report()
    runtime_all = {
        module.lib_id: module
        for module in mojo_inventory.discover_runtime_library_modules(executable_only=False)
    }
    runtime_exec_ids = {
        module.lib_id
        for module in mojo_inventory.discover_runtime_library_modules(executable_only=True)
    }

    benchmark_ids = set(report.artifact_benchmark_result_libs) | set(
        report.artifact_benchmark_bench_libs
    )
    non_executable_gap = sorted(
        lib_id
        for lib_id in benchmark_ids
        if lib_id not in runtime_exec_ids and lib_id in runtime_all
    )

    assert len(non_executable_gap) <= 19
