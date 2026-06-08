from __future__ import annotations

import io
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from apps.api_server.services import source_registry as sreg
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

_DEFAULT_SQL_REPORT_MAX_ROWS = 500
_MAX_SQL_REPORT_BYTES = 512_000
_SQL_REPORT_TIMEOUT_SECONDS = 5.0
_SQL_ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FORBIDDEN_SQL_TOKENS = (
    "insert",
    "update",
    "delete",
    "merge",
    "drop",
    "create",
    "alter",
    "call",
    "copy",
    "export",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "analyze",
)


@dataclass(slots=True)
class SQLReportServiceError(Exception):
    code: str
    message: str
    status_code: int = 422
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def normalize_sql_report_alias(dataset_id: str, alias: str | None) -> str:
    candidate = (alias or dataset_id).strip()
    if not candidate:
        raise SQLReportServiceError(
            code="sql_report_invalid_source",
            message="Each SQL report source must include a dataset_id or alias.",
        )
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", candidate)
    if normalized and normalized[0].isdigit():
        normalized = f"ds_{normalized}"
    if not _SQL_ALIAS_RE.fullmatch(normalized):
        raise SQLReportServiceError(
            code="sql_report_invalid_source_alias",
            message=f"Invalid SQL report alias '{candidate}'.",
            details={"alias": candidate},
        )
    return normalized


def validate_sql_report_sql(sql: str) -> str:
    normalized = sql.strip()
    if not normalized:
        raise SQLReportServiceError(
            code="sql_report_invalid_sql",
            message="SQL report statements cannot be empty.",
        )
    if "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise SQLReportServiceError(
            code="sql_report_comments_not_allowed",
            message="SQL report statements cannot include SQL comments.",
        )
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    if ";" in normalized:
        raise SQLReportServiceError(
            code="sql_report_multiple_statements_not_allowed",
            message="SQL report statements must contain exactly one statement.",
        )

    lowered = normalized.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise SQLReportServiceError(
            code="sql_report_read_only_required",
            message="SQL report statements must begin with SELECT or WITH.",
        )
    for token in _FORBIDDEN_SQL_TOKENS:
        if re.search(rf"\\b{token}\\b", lowered):
            raise SQLReportServiceError(
                code="sql_report_read_only_required",
                message=f"SQL report statements cannot include {token.upper()}.",
                details={"token": token},
            )
    return normalized


def _truncate_rows_to_max_bytes(
    rows: list[dict[str, Any]],
    *,
    max_bytes: int,
) -> tuple[list[dict[str, Any]], bool]:
    if len(json.dumps(rows, default=str).encode("utf-8")) <= max_bytes:
        return rows, False

    trimmed = list(rows)
    while trimmed and len(json.dumps(trimmed, default=str).encode("utf-8")) > max_bytes:
        trimmed.pop()
    return trimmed, True


def _load_dataset_frame(org_id: str, dataset_id: str) -> Any:
    parquet_bytes = sreg.get_source_parquet(org_id, dataset_id)
    if not parquet_bytes:
        raise SQLReportServiceError(
            code="sql_report_source_not_found",
            message=f"Dataset '{dataset_id}' does not have queryable storage.",
            status_code=404,
            details={"dataset_id": dataset_id},
        )
    import pandas as pd

    initialize_pyarrow_parquet_runtime()
    return pd.read_parquet(io.BytesIO(parquet_bytes))


def execute_sql_report(
    *,
    org_id: str,
    sources: list[tuple[str, str]],
    sql: str,
    max_rows: int | None = None,
    timeout_seconds: float = _SQL_REPORT_TIMEOUT_SECONDS,
    max_bytes: int = _MAX_SQL_REPORT_BYTES,
) -> dict[str, Any]:
    validated_sql = validate_sql_report_sql(sql)
    effective_max_rows = max_rows or _DEFAULT_SQL_REPORT_MAX_ROWS

    connection = sqlite3.connect(":memory:")
    deadline = time.monotonic() + timeout_seconds

    def _progress_handler() -> int:
        return 1 if time.monotonic() > deadline else 0

    connection.set_progress_handler(_progress_handler, 1_000)

    try:
        for alias, dataset_id in sources:
            frame = _load_dataset_frame(org_id, dataset_id)
            frame.to_sql(alias, connection, index=False, if_exists="replace")

        cursor = connection.execute(validated_sql)
        columns = [str(item[0]) for item in (cursor.description or [])]
        raw_rows = cursor.fetchmany(effective_max_rows + 1)
        truncated = len(raw_rows) > effective_max_rows
        if truncated:
            raw_rows = raw_rows[:effective_max_rows]
        rows = [dict(zip(columns, row, strict=False)) for row in raw_rows]
        rows, byte_truncated = _truncate_rows_to_max_bytes(rows, max_bytes=max_bytes)
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated or byte_truncated,
        }
    except sqlite3.OperationalError as exc:
        lowered = str(exc).lower()
        if "interrupted" in lowered:
            raise SQLReportServiceError(
                code="sql_report_timeout",
                message="SQL report execution exceeded the allowed time budget.",
                status_code=408,
            ) from exc
        raise SQLReportServiceError(
            code="sql_report_invalid_sql",
            message=f"SQL report execution failed: {exc}",
            details={"reason": str(exc)},
        ) from exc
    finally:
        connection.close()


__all__ = [
    "SQLReportServiceError",
    "execute_sql_report",
    "normalize_sql_report_alias",
    "validate_sql_report_sql",
]
