from __future__ import annotations

from tests.benchmark_mojo_vs_python import (
    FnInfo,
    Param,
    _arg_values,
    _filter_testable_functions_for_library,
    _python_result_summary,
    _result_summaries_match,
    _rollout_public_benchmark_functions,
)
from tests.llm_rollout_matrix import LLM_ROLLOUT_FUNCTIONS_BY_MODULE


def _param(name: str, typ: str) -> Param:
    return Param(name=name, typ=typ, has_default=False, is_mut=False)


def test_result_summaries_match_accepts_equivalent_float_formats() -> None:
    assert _result_summaries_match("float:1", "float:1.0") is True
    assert _result_summaries_match("float:0.333333333", "float:0.3333333333") is True
    assert _result_summaries_match("float:1.0", "float:1.1") is False


def test_python_result_summary_handles_vector_kernels_table_special_cases() -> None:
    rank_request = {
        "source_id": 1,
        "role_id": 1,
        "top_k": 2,
        "query_norm_inv": 0.3333333432674408,
        "query_vec": {"data": [0.0, 1.0, 0.0], "norm_inv": 0.0},
    }
    candidate_table = {
        "entries": [
            {
                "column_id": 1,
                "source_id": 1,
                "role_id": 1,
                "norm_inv": 0.3333333432674408,
                "vec": {"data": [0.0, 1.0, 0.0], "norm_inv": 0.0},
            }
        ]
    }

    rank_summary = _python_result_summary(
        rank_request,
        lib="vector_kernels_table",
        function="build_query",
    )
    table_summary = _python_result_summary(
        candidate_table,
        lib="vector_kernels_table",
        function="build_table_json",
    )

    assert rank_summary == "rank_request:1:1:2:float:0.3333333432674408:571407392"
    assert table_summary == "candidate_table:1:504549231"


def test_arg_values_support_llm_rollout_specific_overrides() -> None:
    build_query = FnInfo(
        name="build_query",
        params=[
            _param("name", "String"),
            _param("source_id", "UInt16"),
            _param("role_id", "UInt8"),
            _param("top_k", "UInt8"),
        ],
        ret="RankRequest",
        body_lines=[],
        lib="vector_kernels_table",
    )
    bigbird = FnInfo(
        name="bigbird_random_block_select",
        params=[
            _param("block_id", "Float64"),
            _param("n_blocks", "Float64"),
            _param("random_seed", "Float64"),
            _param("n_random", "Float64"),
        ],
        ret="Float64",
        body_lines=[],
        lib="sparse_attention",
    )

    assert _arg_values(build_query) == ['"unit_price"', "1", "1", "2"]
    assert _arg_values(bigbird) == ["1.0", "8.0", "3.0", "2.0"]


def test_rollout_public_benchmark_functions_match_runtime_surface() -> None:
    assert _rollout_public_benchmark_functions("text_tokenizer") == frozenset(
        LLM_ROLLOUT_FUNCTIONS_BY_MODULE["text.tokenizer"]
    )
    assert _rollout_public_benchmark_functions("vector_kernels_ranker") == frozenset(
        LLM_ROLLOUT_FUNCTIONS_BY_MODULE["vector_kernels.ranker"]
    )
    assert _rollout_public_benchmark_functions("vector_kernels_table") == frozenset(
        LLM_ROLLOUT_FUNCTIONS_BY_MODULE["vector_kernels.table"]
    )
    assert _rollout_public_benchmark_functions("rerank_eval") == frozenset(
        LLM_ROLLOUT_FUNCTIONS_BY_MODULE["rerank_eval"]
    )
    assert _rollout_public_benchmark_functions("inference_cost_latency") == frozenset(
        LLM_ROLLOUT_FUNCTIONS_BY_MODULE["inference_cost_latency"]
    )
    assert _rollout_public_benchmark_functions("not_a_rollout_lib") is None


def test_filter_testable_functions_for_library_excludes_rollout_helpers() -> None:
    functions = [
        FnInfo(
            name="_substr",
            params=[_param("value", "String"), _param("start", "Int"), _param("end", "Int")],
            ret="String",
            body_lines=[],
            lib="text_tokenizer",
        ),
        FnInfo(
            name="word_tokenize",
            params=[_param("text", "String")],
            ret="List[String]",
            body_lines=[],
            lib="text_tokenizer",
        ),
        FnInfo(
            name="_token_jaccard",
            params=[_param("left", "String"), _param("right", "String")],
            ret="Float64",
            body_lines=[],
            lib="vector_kernels_ranker",
        ),
        FnInfo(
            name="run_column_rank_v2",
            params=[_param("request_json", "String")],
            ret="String",
            body_lines=[],
            lib="vector_kernels_ranker",
        ),
    ]

    filtered_text = _filter_testable_functions_for_library(
        "text_tokenizer", functions[:2]
    )
    filtered_ranker = _filter_testable_functions_for_library(
        "vector_kernels_ranker", functions[2:]
    )

    assert [fn.name for fn in filtered_text] == ["word_tokenize"]
    assert [fn.name for fn in filtered_ranker] == ["run_column_rank_v2"]
