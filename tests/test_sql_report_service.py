from __future__ import annotations

import io

import pandas as pd
import pytest

from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.sql_report_service import (
    SQLReportServiceError,
    execute_sql_report,
    validate_sql_report_sql,
)


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    initialize_pyarrow_parquet_runtime()
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def test_validate_sql_report_sql_rejects_comments_and_multiple_statements() -> None:
    with pytest.raises(SQLReportServiceError, match="comments"):
        validate_sql_report_sql("select * from otp -- hidden second statement")

    with pytest.raises(SQLReportServiceError, match="exactly one statement"):
        validate_sql_report_sql("select * from otp; select * from other")

    with pytest.raises(SQLReportServiceError, match="must begin with SELECT or WITH"):
        validate_sql_report_sql("delete from otp")


@pytest.mark.parametrize(
    "forbidden_keyword",
    ["insert", "update", "delete", "drop", "create", "alter", "attach", "pragma"],
)
def test_validate_sql_report_sql_rejects_forbidden_tokens_embedded_in_select(
    forbidden_keyword: str,
) -> None:
    sql = f"with t as (select 1) select * from t where x = '{forbidden_keyword} payload'"
    with pytest.raises(SQLReportServiceError) as exc_info:
        validate_sql_report_sql(sql)
    assert exc_info.value.code == "sql_report_read_only_required"
    assert exc_info.value.details == {"token": forbidden_keyword}


def test_execute_sql_report_enforces_row_and_byte_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    parquet_bytes = _parquet_bytes(
        pd.DataFrame(
            {
                "flight_month": ["2026-01-01", "2026-02-01", "2026-03-01"],
                "otp_rate_pct": [91.1, 92.4, 94.2],
                "notes": ["x" * 300, "y" * 300, "z" * 300],
            }
        )
    )
    monkeypatch.setattr(
        "apps.api_server.services.sql_report_service.sreg.get_source_parquet",
        lambda _org_id, _dataset_id: parquet_bytes,
    )

    limited = execute_sql_report(
        org_id="org_a",
        sources=[("otp", "ds_otp")],
        sql="select flight_month, otp_rate_pct from otp order by flight_month",
        max_rows=2,
    )
    assert limited["row_count"] == 2
    assert limited["truncated"] is True

    byte_limited = execute_sql_report(
        org_id="org_a",
        sources=[("otp", "ds_otp")],
        sql="select flight_month, otp_rate_pct, notes from otp order by flight_month",
        max_rows=3,
        max_bytes=250,
    )
    assert byte_limited["truncated"] is True
    assert byte_limited["row_count"] < 3


def test_execute_sql_report_enforces_timeout() -> None:
    with pytest.raises(SQLReportServiceError, match="time budget"):
        execute_sql_report(
            org_id="org_a",
            sources=[],
            sql=(
                "with recursive cnt(x) as ("
                "select 1 union all select x + 1 from cnt where x < 100000000"
                ") select sum(x) from cnt"
            ),
            timeout_seconds=0.0001,
        )
