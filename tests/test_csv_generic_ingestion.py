from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services.columnar_loader import _choose_delimiter
from apps.api_server.services.data_coercion import parse_delimited_records
from tests.csv_invariant_helpers import (
    CsvModeError,
    build_generated_csv_cases,
    load_generated_csv_case,
    register_csv_and_query_count,
    reset_runtime_state,
    round_trip_generated_case,
    temporary_registry_dir,
    unique_auth,
)

_CASES = tuple(build_generated_csv_cases())


def _case(case_name: str):
    return next(case for case in _CASES if case.name == case_name)


def test_generated_csv_cases_are_deterministic_for_successful_modes() -> None:
    for case in _CASES:
        for mode in case.successful_modes:
            first = load_generated_csv_case(case, mode=mode)
            second = load_generated_csv_case(case, mode=mode)

            assert first.columns == second.columns, (case.name, mode)
            assert first.schema_columns == second.schema_columns, (case.name, mode)
            assert first.schema_hash == second.schema_hash, (case.name, mode)
            assert first.row_order_hash == second.row_order_hash, (case.name, mode)
            assert first.rows == second.rows, (case.name, mode)
            assert first.report == second.report, (case.name, mode)


def test_generated_csv_strict_and_multiline_modes_fail_explicitly_on_ragged_rows() -> None:
    for case in _CASES:
        if not case.malformed:
            continue
        for mode in ("strict", "multiline"):
            with pytest.raises(CsvModeError) as exc_info:
                load_generated_csv_case(case, mode=mode)
            assert exc_info.value.code == "row_length_mismatch"
            assert exc_info.value.report.mode == mode
            assert exc_info.value.report.rows_rejected == 1


def test_generated_csv_multiline_cells_require_multiline_mode() -> None:
    case = _case("multiline_quoted")

    with pytest.raises(CsvModeError) as exc_info:
        load_generated_csv_case(case, mode="strict")

    assert exc_info.value.code == "multiline_value"

    loaded = load_generated_csv_case(case, mode="multiline")
    assert loaded.rows[0]["description"] == "line one\nline two"
    assert loaded.report.rows_rejected == 0


def test_generated_csv_salvage_mode_emits_structured_parse_report() -> None:
    for case_name in ("ragged_missing_fields", "ragged_extra_fields"):
        loaded = load_generated_csv_case(_case(case_name), mode="salvage")

        assert loaded.report.mode == "salvage"
        assert loaded.report.rows_read == 3
        assert loaded.report.rows_emitted == 2
        assert loaded.report.rows_rejected == 1
        assert loaded.report.rejection_reasons == {"row_length_mismatch": 1}
        assert loaded.report.header_detected is True
        assert loaded.report.delimiter_detected == ","


def test_generated_csv_type_inference_and_identifier_preservation_are_stable() -> None:
    loaded = load_generated_csv_case(_case("identifier_tab"), mode="strict")
    schema = {column["name"]: column["physical_type"] for column in loaded.schema_columns}

    assert schema["part_number"] == "string"
    assert schema["zip_code"] == "string"
    assert schema["measure_total"] in {"int64", "int32"}
    assert loaded.rows[0]["part_number"] == "00123"
    assert loaded.rows[0]["zip_code"] == "02108"


def test_generated_csv_round_trip_integrity_is_stable_for_strict_and_multiline_modes() -> None:
    for case in _CASES:
        for mode in case.round_trip_modes:
            loaded, reloaded = round_trip_generated_case(case, mode=mode)

            assert loaded.columns == reloaded.columns, (case.name, mode)
            assert loaded.schema_hash == reloaded.schema_hash, (case.name, mode)
            assert loaded.row_order_hash == reloaded.row_order_hash, (case.name, mode)
            assert loaded.rows == reloaded.rows, (case.name, mode)


def test_generated_csv_delimiter_sniffing_is_deterministic_for_headered_cases() -> None:
    for case in _CASES:
        if not case.headers_present or case.malformed:
            continue
        first_delimiter = _choose_delimiter(case.content, delimiter=None, sniff=True)
        second_delimiter = _choose_delimiter(case.content, delimiter=None, sniff=True)
        assert first_delimiter == second_delimiter == case.delimiter, case.name

        first_rows = parse_delimited_records(case.content, delimiter=None, sniff=True)
        second_rows = parse_delimited_records(case.content, delimiter=None, sniff=True)
        assert first_rows == second_rows, case.name


@pytest.mark.anyio
async def test_generated_csv_registration_query_count_matches_loader_count() -> None:
    with temporary_registry_dir() as tmp_dir:
        registry_dir = Path(tmp_dir) / "registry"
        await reset_runtime_state(registry_dir)
        for case in _CASES:
            if not case.registration_modes:
                continue
            mode = case.registration_modes[0]
            loaded = load_generated_csv_case(case, mode=mode)
            registration = await register_csv_and_query_count(
                csv_text=case.content,
                source_name=f"Generated::{case.name}",
                auth=unique_auth("csv_generic"),
            )

            assert registration.loader_count == len(loaded.rows), case.name
            assert registration.query_count == len(loaded.rows), case.name
            assert registration.schema_hash == loaded.schema_hash, case.name
            assert registration.registered_schema_hash == loaded.schema_hash, case.name
