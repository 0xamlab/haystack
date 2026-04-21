from __future__ import annotations

from pathlib import Path

from apps.api_server.services.data_coercion import (
    coerce_scalar,
    is_identifier_field,
    looks_like_header_alias_row,
    parse_delimited_records,
)


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


def test_parse_delimited_records_skips_header_alias_row() -> None:
    content = (
        "Store name as per Uber Eats manager,Order ID as per Uber Eats manager,Unique ID to identify the order \n"
        "Store Name,Order ID,Workflow ID\n"
        "Serafina (Downtown),#14E6E,beb8a6c0-5412-47c4-a3fd-39e4c6914e6e\n"
    )

    records = parse_delimited_records(content, delimiter=",", sniff=True)

    assert records == [
        {
            "Store name as per Uber Eats manager": "Serafina (Downtown)",
            "Order ID as per Uber Eats manager": "#14E6E",
            "Unique ID to identify the order": "beb8a6c0-5412-47c4-a3fd-39e4c6914e6e",
        }
    ]


def test_parse_delimited_records_skips_real_orders_financial_alias_row() -> None:
    csv_text = (
        Path(__file__).resolve().parents[1]
        / "test_files"
        / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
    ).read_text(encoding="utf-8-sig", errors="replace")

    records = parse_delimited_records(csv_text, delimiter=",", sniff=True)

    assert len(records) == 2026
    assert records[0]["Store name as per Uber Eats manager"] == "Serafina (Downtown)"


def test_parse_delimited_records_keeps_real_first_data_row() -> None:
    content = (
        "Store Name,Store ID,Order Count\n"
        "Serafina (Downtown),12345,17\n"
        "Serafina (Aventura),67890,11\n"
    )

    records = parse_delimited_records(content, delimiter=",", sniff=True)

    assert records == [
        {
            "Store Name": "Serafina (Downtown)",
            "Store ID": "12345",
            "Order Count": 17,
        },
        {
            "Store Name": "Serafina (Aventura)",
            "Store ID": "67890",
            "Order Count": 11,
        },
    ]


def test_looks_like_header_alias_row_keeps_identifier_prefixed_first_data_row() -> None:
    field_names = ["bridge_key", "geo_key", "bridge_label"]
    values = ["bridge_000", "geo_000", "label_3"]

    assert looks_like_header_alias_row(field_names, values) is False
