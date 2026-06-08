from benchmarks.live_postgres_schema_match_benchmark import (
    BENCHMARK_QUERIES,
    BenchmarkResult,
    summarize_results,
)


def test_benchmark_query_corpus_is_unique() -> None:
    queries = [entry.query for entry in BENCHMARK_QUERIES]

    assert queries
    assert len(queries) == len(set(queries))


def test_summarize_results_counts_accuracy() -> None:
    summary = summarize_results(
        [
            BenchmarkResult(
                query="query-a",
                expected_tables=("table_a",),
                top_matches=("table_a", "table_b"),
                hit_top_1=True,
                hit_top_3=True,
                hit_top_6=True,
            ),
            BenchmarkResult(
                query="query-b",
                expected_tables=("table_c",),
                top_matches=("table_x", "table_y", "table_c"),
                hit_top_1=False,
                hit_top_3=True,
                hit_top_6=True,
            ),
            BenchmarkResult(
                query="query-c",
                expected_tables=("table_d",),
                top_matches=("table_x", "table_y", "table_z"),
                hit_top_1=False,
                hit_top_3=False,
                hit_top_6=False,
            ),
        ],
        schema="public",
        table_count=136,
        scorer="decision_engine_generic",
    )

    assert summary["scorer"] == "decision_engine_generic"
    assert summary["schema"] == "public"
    assert summary["table_count"] == 136
    assert summary["samples"] == 3
    assert summary["top1_accuracy"] == 0.3333
    assert summary["top3_accuracy"] == 0.6667
    assert summary["top6_accuracy"] == 0.6667
