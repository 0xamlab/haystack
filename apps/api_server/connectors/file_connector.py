"""File-based data connector (CSV, TSV, JSON, Excel, Parquet)."""
from __future__ import annotations

import base64
import io
import json
from typing import Any

from apps.api_server.services.columnar_loader import (
    delimited_text_to_arrow_table,
    normalize_scalar_for_arrow,
    records_to_arrow_table,
)
from apps.api_server.services.data_coercion import (
    coerce_scalar,
    is_identifier_field,
    parse_delimited_records,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

from .base import BaseConnector, ConnectorRegistry


@ConnectorRegistry.register
class FileConnector(BaseConnector):
    """Parse data from files in any common format.

    Config keys:
        file_type:   One of ``"csv"`` (default), ``"tsv"``, ``"json"``,
                     ``"excel"``, ``"parquet"``.
        content:     Raw file content as a string (CSV/TSV/JSON) or
                     base64-encoded bytes (Excel/Parquet).
        file_path:   Path on disk — used when *content* is empty.
        json_path:   Dot-separated path to the records array in JSON
                     (e.g. ``"data.items"``). Supports nested responses.
        sheet:       Excel sheet name or 0-based index (default 0).
        delimiter:   Column delimiter override (default auto-detected).
    """

    connector_type: str = "file"

    async def fetch_data(self) -> list[dict[str, Any]]:
        file_type: str = self.config.get("file_type", "csv").lower()
        content: str = self.config.get("content", "")
        file_path: str = self.config.get("file_path", "")

        if file_path and not content:
            mode = "rb" if file_type in ("excel", "parquet") else "r"
            with open(file_path, mode) as f:
                raw = f.read()
            if isinstance(raw, bytes):
                content = base64.b64encode(raw).decode()
            else:
                content = raw

        if not content:
            return []

        if file_type == "csv":
            return self._parse_csv(content, delimiter=self.config.get("delimiter", ","))
        if file_type == "tsv":
            return self._parse_csv(content, delimiter="\t")
        if file_type == "json":
            return self._parse_json(content, path=self.config.get("json_path", ""))
        if file_type == "excel":
            return self._parse_excel(content, sheet=self.config.get("sheet", 0))
        if file_type == "parquet":
            return self._parse_parquet(content)

        return []

    async def fetch_table(self) -> Any | None:
        file_type: str = self.config.get("file_type", "csv").lower()
        content: str = self.config.get("content", "")
        file_path: str = self.config.get("file_path", "")

        if file_path and not content:
            mode = "rb" if file_type in ("excel", "parquet") else "r"
            with open(file_path, mode) as f:
                raw = f.read()
            if isinstance(raw, bytes):
                content = base64.b64encode(raw).decode()
            else:
                content = raw

        if not content:
            return None

        if file_type == "csv":
            try:
                return delimited_text_to_arrow_table(
                    content,
                    delimiter=self.config.get("delimiter", ","),
                    sniff=True,
                )
            except Exception:
                return None
        if file_type == "tsv":
            try:
                return delimited_text_to_arrow_table(content, delimiter="\t", sniff=False)
            except Exception:
                return None
        if file_type == "json":
            records = self._parse_json(content, path=self.config.get("json_path", ""))
            if not records:
                return None
            return records_to_arrow_table(records)
        if file_type == "excel":
            return self._excel_to_arrow_table(content, sheet=self.config.get("sheet", 0))
        if file_type == "parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq

            raw = base64.b64decode(content)
            initialize_pyarrow_parquet_runtime()
            return pq.read_table(pa.BufferReader(raw))
        return None

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _open_excel_sheet(content_b64: str, sheet: int | str = 0) -> tuple[Any, Any]:
        try:
            import openpyxl  # lazy — optional dependency
        except ImportError as exc:
            raise ImportError(
                "Excel support requires openpyxl: pip install openpyxl"
            ) from exc

        raw = base64.b64decode(content_b64)
        wb = openpyxl.load_workbook(
            io.BytesIO(raw),
            read_only=True,
            data_only=True,
            keep_links=False,
        )
        ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
        return wb, ws

    @staticmethod
    def _excel_headers(header_row: tuple[Any, ...]) -> list[str]:
        return [
            str(header) if header is not None else f"col_{index}"
            for index, header in enumerate(header_row)
        ]

    @staticmethod
    def _coerce_excel_record_value(field_name: str, value: Any) -> Any:
        if value is None:
            return ""
        if is_identifier_field(field_name) and isinstance(value, int | float):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        return coerce_scalar(field_name, value, preserve_identifiers=True)

    @staticmethod
    def _coerce_excel_arrow_value(field_name: str, value: Any) -> Any:
        if value is None:
            return None
        if is_identifier_field(field_name) and isinstance(value, int | float):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        return normalize_scalar_for_arrow(field_name, value)

    @staticmethod
    def _parse_csv(content: str, delimiter: str = ",") -> list[dict[str, Any]]:
        return parse_delimited_records(content, delimiter=delimiter, sniff=True)

    @staticmethod
    def _parse_json(content: str, path: str = "") -> list[dict[str, Any]]:
        try:
            data: Any = json.loads(content.strip())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

        # Navigate dot-path (e.g. "data.items")
        if path:
            for key in path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])
                elif isinstance(data, list) and key.isdigit():
                    data = data[int(key)]

        # Auto-detect records array from common wrapper keys
        if isinstance(data, dict):
            for key in ("data", "records", "rows", "results", "items", "value"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = [data]

        if not isinstance(data, list):
            return []

        # Flatten nested objects so every field is top-level
        return [_flatten_dict(r) for r in data if isinstance(r, dict)]

    @staticmethod
    def _parse_excel(content_b64: str, sheet: int | str = 0) -> list[dict[str, Any]]:
        wb, ws = FileConnector._open_excel_sheet(content_b64, sheet=sheet)
        try:
            rows = ws.iter_rows(values_only=True)
            try:
                headers = FileConnector._excel_headers(next(rows))
            except StopIteration:
                return []

            records: list[dict[str, Any]] = []
            for row in rows:
                rec: dict[str, Any] = {}
                for header, value in zip(headers, row, strict=False):
                    rec[header] = FileConnector._coerce_excel_record_value(header, value)
                records.append(rec)
            return records
        finally:
            wb.close()

    @staticmethod
    def _excel_to_arrow_table(content_b64: str, sheet: int | str = 0) -> Any | None:
        import pyarrow as pa

        wb, ws = FileConnector._open_excel_sheet(content_b64, sheet=sheet)
        try:
            rows = ws.iter_rows(values_only=True)
            try:
                headers = FileConnector._excel_headers(next(rows))
            except StopIteration:
                return pa.table({})

            last_index: dict[str, int] = {}
            for index, header in enumerate(headers):
                last_index[header] = index
            final_headers = [
                header
                for index, header in enumerate(headers)
                if last_index[header] == index
            ]
            final_indexes = [last_index[header] for header in final_headers]
            columns: dict[str, list[Any]] = {header: [] for header in final_headers}

            for row in rows:
                for header, index in zip(final_headers, final_indexes, strict=True):
                    value = row[index] if index < len(row) else None
                    columns[header].append(
                        FileConnector._coerce_excel_arrow_value(header, value)
                    )

            arrays: dict[str, Any] = {}
            for header, values in columns.items():
                try:
                    arrays[header] = pa.array(values)
                except Exception:
                    arrays[header] = pa.array(
                        [str(value) if value is not None else None for value in values],
                        type=pa.string(),
                    )
            return pa.table(arrays)
        finally:
            wb.close()

    @staticmethod
    def _parse_parquet(content_b64: str) -> list[dict[str, Any]]:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq  # lazy — optional dependency
        except ImportError as exc:
            raise ImportError(
                "Parquet support requires pyarrow: pip install pyarrow"
            ) from exc

        raw = base64.b64decode(content_b64)
        initialize_pyarrow_parquet_runtime()
        table = pq.read_table(pa.BufferReader(raw))
        return table.to_pydict() and [
            {col: table.column(col)[i].as_py() for col in table.schema.names}
            for i in range(table.num_rows)
        ] or []

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            data = await self.fetch_data()
            return True, f"Parsed {len(data)} records."
        except Exception as exc:
            return False, f"Parse failed: {exc}"


# ── JSON flattening helper ─────────────────────────────────────────────────────

def _flatten_dict(
    obj: dict[str, Any],
    prefix: str = "",
    sep: str = ".",
    max_depth: int = 5,
) -> dict[str, Any]:
    """
    Recursively flatten a nested dict into a single-level dict.

    {"customer": {"name": "Acme", "city": "NY"}, "amount": 500}
    →
    {"customer.name": "Acme", "customer.city": "NY", "amount": 500}

    Lists are serialised as JSON strings (not exploded) to keep the row model flat.
    """
    result: dict[str, Any] = {}
    _flatten_into(obj, prefix, sep, max_depth, 0, result)
    return result


def _flatten_into(
    obj: Any,
    prefix: str,
    sep: str,
    max_depth: int,
    depth: int,
    out: dict[str, Any],
) -> None:
    if depth >= max_depth or not isinstance(obj, dict):
        out[prefix] = obj
        return
    for key, val in obj.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(val, dict) and depth < max_depth - 1:
            _flatten_into(val, full_key, sep, max_depth, depth + 1, out)
        elif isinstance(val, list):
            # Serialize short lists inline; skip huge nested arrays
            out[full_key] = json.dumps(val) if len(val) <= 20 else f"[{len(val)} items]"
        else:
            out[full_key] = val
