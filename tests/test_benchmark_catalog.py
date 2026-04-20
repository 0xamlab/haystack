from pathlib import Path


def test_generated_benchmark_avoids_fixture_specific_business_terms():
    text = Path("benchmarks/test_query_advanced.py").read_text()
    banned = ["Bookings", "Quotes", "Inventory", "POS", "Backlog", "EXT_PRICE", "PART_NUMBER"]
    assert all(term not in text for term in banned)


def test_generated_benchmark_uses_synthetic_sources_and_summary():
    text = Path("benchmarks/test_query_advanced.py").read_text()
    assert "Generated-Schema Query Benchmark" in text
    assert '"S0"' in text and '"S1"' in text and '"S2"' in text and '"S3"' in text
    assert "Generated benchmark summary" in text


def test_universal_benchmark_is_backend_matrix_and_schema_agnostic():
    text = Path("benchmarks/universal_benchmark.py").read_text()
    banned = ["Bookings", "Quotes", "Inventory", "POS", "Backlog", "hospitality", "restaurant"]
    assert all(term not in text for term in banned)
    assert '"csv"' in text
    assert '"parquet"' in text
    assert '"sqlite"' in text
    assert "Universal synthetic benchmark" in text
