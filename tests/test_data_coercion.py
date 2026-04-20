from __future__ import annotations

from apps.api_server.services.data_coercion import coerce_scalar, is_identifier_field


def test_is_identifier_field_distinguishes_identifier_from_measure_names() -> None:
    assert is_identifier_field("part_number") is True
    assert is_identifier_field("order_number") is True
    assert is_identifier_field("order_total") is False
    assert is_identifier_field("ext_price") is False


def test_coerce_scalar_preserves_identifier_text_with_leading_zeroes() -> None:
    assert coerce_scalar("part_number", "00123", preserve_identifiers=True) == "00123"
    assert coerce_scalar("ext_price", "00123", preserve_identifiers=True) == "00123"


def test_coerce_scalar_skips_numeric_regex_for_text_but_keeps_scientific_notation() -> None:
    assert coerce_scalar("customer_name", "ACME 123", preserve_identifiers=True) == "ACME 123"
    assert coerce_scalar("measure_total", "1e3", preserve_identifiers=True) == 1000.0
