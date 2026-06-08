from __future__ import annotations

import io

import pandas as pd
import pytest

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

pytestmark = pytest.mark.anyio


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    initialize_pyarrow_parquet_runtime()
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture
async def sql_report_client(app, client):
    app.dependency_overrides[get_current_org] = lambda: {
        "org_id": "org_a",
        "role": "member",
        "user_id": "u1",
        "key_id": "k1",
    }
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


async def test_query_sql_report_returns_rows_for_visible_dataset(
    monkeypatch,
    sql_report_client,
) -> None:
    parquet_bytes = _parquet_bytes(
        pd.DataFrame(
            {
                "flight_month": ["2026-01-01", "2026-02-01"],
                "otp_rate_pct": [91.1, 92.4],
            }
        )
    )
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.get_visible_dataset_entry",
        lambda _org_id, dataset_id, _auth: (
            {"id": dataset_id, "name": "OTP"} if dataset_id == "ds_otp" else None
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.sql_report_service.sreg.get_source_parquet",
        lambda _org_id, _dataset_id: parquet_bytes,
    )

    response = await sql_report_client.post(
        "/v1/query/sql-report",
        json={
            "sources": [{"dataset_id": "ds_otp", "alias": "otp"}],
            "sql": "select flight_month, otp_rate_pct from otp order by flight_month",
            "max_rows": 100,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ["flight_month", "otp_rate_pct"]
    assert body["row_count"] == 2
    assert body["truncated"] is False
    assert body["request_id"]


async def test_query_sql_report_rejects_mutating_sql(monkeypatch, sql_report_client) -> None:
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.get_visible_dataset_entry",
        lambda _org_id, dataset_id, _auth: (
            {"id": dataset_id, "name": "OTP"} if dataset_id == "ds_otp" else None
        ),
    )

    response = await sql_report_client.post(
        "/v1/query/sql-report",
        json={
            "sources": [{"dataset_id": "ds_otp", "alias": "otp"}],
            "sql": "delete from otp",
            "max_rows": 100,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "sql_report_read_only_required"
