"""File-based data connector (CSV, TSV, JSON, Excel, Parquet)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from apps.api_server.services.columnar_loader import (
    delimited_text_to_arrow_table,
    records_to_arrow_table,
)
from apps.api_server.services.data_coercion import (
    _coerce_text_scalar as _coerce_text_scalar_impl,
)
from apps.api_server.services.data_coercion import (
    parse_delimited_records,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

from .base import BaseConnector, ConnectorRegistry
from .file_connector_excel import (
    CACHE_MISS as EXCEL_CACHE_MISS,
)
from .file_connector_excel import (
    COERCION_CACHE_MAX_ENTRIES,
    COERCION_CACHE_MAX_VALUE_LEN,
    XLSX_COLUMN_INDEX_CACHE_MAX,
    XLSX_MAIN_NS,
    XLSX_PKG_REL_NS,
    XLSX_REL_NS,
    XLSX_TAG_CELL,
    XLSX_TAG_ROW,
    XLSX_TAG_SHARED_STRING,
    XLSX_TAG_TEXT,
    XLSX_TAG_VALUE,
    arrow_table_from_excel_columns,
    arrow_table_from_excel_rows,
    cacheable_excel_text_value,
    coerce_excel_arrow_value,
    coerce_excel_arrow_value_cached,
    coerce_excel_record_value,
    coerce_excel_record_value_cached,
    decode_binary_content,
    excel_headers,
    fast_xlsx_to_arrow_table,
    final_excel_headers,
    iter_fast_xlsx_rows,
    open_excel_sheet,
    records_from_excel_rows,
    xlsx_column_index_from_ref,
    xlsx_date_style_indexes,
    xlsx_normalize_member_path,
    xlsx_parse_cell_value,
    xlsx_read_shared_strings,
    xlsx_sheet_target,
)
from .file_connector_json import (
    flatten_dict as _flatten_dict_impl,
)
from .file_connector_json import (
    parse_json_records,
)

_coerce_text_scalar = _coerce_text_scalar_impl


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
    _COERCION_CACHE_MAX_ENTRIES = COERCION_CACHE_MAX_ENTRIES
    _COERCION_CACHE_MAX_VALUE_LEN = COERCION_CACHE_MAX_VALUE_LEN
    _CACHE_MISS = EXCEL_CACHE_MISS
    _XLSX_MAIN_NS = XLSX_MAIN_NS
    _XLSX_REL_NS = XLSX_REL_NS
    _XLSX_PKG_REL_NS = XLSX_PKG_REL_NS
    _XLSX_TAG_ROW = XLSX_TAG_ROW
    _XLSX_TAG_CELL = XLSX_TAG_CELL
    _XLSX_TAG_VALUE = XLSX_TAG_VALUE
    _XLSX_TAG_TEXT = XLSX_TAG_TEXT
    _XLSX_TAG_SHARED_STRING = XLSX_TAG_SHARED_STRING
    _XLSX_COLUMN_INDEX_CACHE_MAX = XLSX_COLUMN_INDEX_CACHE_MAX

    @staticmethod
    def _load_content(file_type: str, content: str | bytes, file_path: str) -> str | bytes:
        if file_path and not content:
            if file_type in ("excel", "parquet"):
                with open(file_path, "rb") as handle:
                    return handle.read()
            with open(file_path, encoding="utf-8") as handle:
                return handle.read()
        return content

    @staticmethod
    def _text_content(content: str | bytes) -> str:
        return content.decode("utf-8") if isinstance(content, bytes) else content

    @staticmethod
    def _decode_binary_content(content_b64: str | bytes) -> bytes:
        return decode_binary_content(content_b64)

    @staticmethod
    def _xlsx_normalize_member_path(target: str) -> str:
        return xlsx_normalize_member_path(target)

    @staticmethod
    def _xlsx_read_shared_strings(archive: Any) -> list[str]:
        return xlsx_read_shared_strings(archive)

    @staticmethod
    def _xlsx_sheet_target(archive: Any, *, sheet: int | str = 0) -> tuple[str, Any]:
        return xlsx_sheet_target(archive, sheet=sheet)

    @staticmethod
    def _xlsx_date_style_indexes(archive: Any) -> set[int]:
        return xlsx_date_style_indexes(archive)

    @staticmethod
    def _xlsx_column_index_from_ref(
        ref: str | None,
        default_index: int,
        *,
        column_cache: dict[str, int] | None = None,
    ) -> int:
        return xlsx_column_index_from_ref(
            ref,
            default_index,
            column_cache=column_cache,
        )

    @staticmethod
    def _xlsx_parse_cell_value(
        cell: Any,
        *,
        shared_strings: list[str],
        date_styles: set[int],
        date_epoch: Any,
    ) -> Any:
        return xlsx_parse_cell_value(
            cell,
            shared_strings=shared_strings,
            date_styles=date_styles,
            date_epoch=date_epoch,
        )

    @staticmethod
    def _iter_fast_xlsx_rows(
        content_b64: str | bytes,
        *,
        sheet: int | str = 0,
    ) -> Iterable[tuple[Any, ...]]:
        return iter_fast_xlsx_rows(content_b64, sheet=sheet)

    async def fetch_data(self) -> list[dict[str, Any]]:
        file_type: str = self.config.get("file_type", "csv").lower()
        content: str | bytes = self.config.get("content", "")
        file_path: str = self.config.get("file_path", "")

        content = self._load_content(file_type, content, file_path)
        if not content:
            return []

        if file_type == "csv":
            return self._parse_csv(
                self._text_content(content),
                delimiter=self.config.get("delimiter", ","),
            )
        if file_type == "tsv":
            return self._parse_csv(self._text_content(content), delimiter="\t")
        if file_type == "json":
            return self._parse_json(
                self._text_content(content),
                path=self.config.get("json_path", ""),
            )
        if file_type == "excel":
            return self._parse_excel(content, sheet=self.config.get("sheet", 0))
        if file_type == "parquet":
            return self._parse_parquet(content)
        return []

    async def fetch_table(self) -> Any | None:
        file_type: str = self.config.get("file_type", "csv").lower()
        content: str | bytes = self.config.get("content", "")
        file_path: str = self.config.get("file_path", "")

        content = self._load_content(file_type, content, file_path)
        if not content:
            return None

        if file_type == "csv":
            try:
                return delimited_text_to_arrow_table(
                    self._text_content(content),
                    delimiter=self.config.get("delimiter", ","),
                    sniff=True,
                )
            except Exception:
                return None
        if file_type == "tsv":
            try:
                return delimited_text_to_arrow_table(
                    self._text_content(content),
                    delimiter="\t",
                    sniff=False,
                )
            except Exception:
                return None
        if file_type == "json":
            records = self._parse_json(
                self._text_content(content),
                path=self.config.get("json_path", ""),
            )
            if not records:
                return None
            return records_to_arrow_table(records)
        if file_type == "excel":
            return self._excel_to_arrow_table(content, sheet=self.config.get("sheet", 0))
        if file_type == "parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq

            raw = self._decode_binary_content(content)
            initialize_pyarrow_parquet_runtime()
            return pq.read_table(pa.BufferReader(raw))
        return None

    @staticmethod
    def _open_excel_sheet(
        content_b64: str | bytes,
        sheet: int | str = 0,
        *,
        apply_styles: bool = False,
    ) -> tuple[Any, Any]:
        return open_excel_sheet(content_b64, sheet=sheet, apply_styles=apply_styles)

    @staticmethod
    def _excel_headers(header_row: tuple[Any, ...]) -> list[str]:
        return excel_headers(header_row)

    @staticmethod
    def _cacheable_excel_text_value(value: Any) -> str | None:
        return cacheable_excel_text_value(value)

    @staticmethod
    def _coerce_excel_record_value(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool | None = None,
    ) -> Any:
        return coerce_excel_record_value(
            field_name,
            value,
            preserve_identifier_field=preserve_identifier_field,
        )

    @staticmethod
    def _coerce_excel_arrow_value(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool | None = None,
    ) -> Any:
        return coerce_excel_arrow_value(
            field_name,
            value,
            preserve_identifier_field=preserve_identifier_field,
        )

    @staticmethod
    def _coerce_excel_record_value_cached(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool,
        cache: dict[str, Any],
    ) -> Any:
        return coerce_excel_record_value_cached(
            field_name,
            value,
            preserve_identifier_field=preserve_identifier_field,
            cache=cache,
        )

    @staticmethod
    def _coerce_excel_arrow_value_cached(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool,
        cache: dict[str, Any],
    ) -> Any:
        return coerce_excel_arrow_value_cached(
            field_name,
            value,
            preserve_identifier_field=preserve_identifier_field,
            cache=cache,
        )

    @staticmethod
    def _final_excel_headers(headers: list[str]) -> tuple[list[str], list[int]]:
        return final_excel_headers(headers)

    @staticmethod
    def _arrow_table_from_excel_columns(columns: dict[str, list[Any]]) -> Any | None:
        return arrow_table_from_excel_columns(columns)

    @staticmethod
    def _fast_xlsx_to_arrow_table(content_b64: str | bytes, *, sheet: int | str = 0) -> Any | None:
        return fast_xlsx_to_arrow_table(content_b64, sheet=sheet)

    @staticmethod
    def _parse_csv(content: str, delimiter: str = ",") -> list[dict[str, Any]]:
        return parse_delimited_records(content, delimiter=delimiter, sniff=True)

    @staticmethod
    def _parse_json(content: str, path: str = "") -> list[dict[str, Any]]:
        return parse_json_records(content, path=path)

    @staticmethod
    def _parse_excel(content_b64: str | bytes, sheet: int | str = 0) -> list[dict[str, Any]]:
        try:
            wb, ws = FileConnector._open_excel_sheet(
                content_b64,
                sheet=sheet,
                apply_styles=True,
            )
            try:
                return FileConnector._records_from_excel_rows(ws.values)
            finally:
                wb.close()
        except Exception:
            rows = FileConnector._iter_fast_xlsx_rows(content_b64, sheet=sheet)
            return FileConnector._records_from_excel_rows(rows)

    @staticmethod
    def _openpyxl_excel_to_arrow_table(
        content_b64: str | bytes,
        sheet: int | str = 0,
    ) -> Any | None:
        wb, ws = FileConnector._open_excel_sheet(
            content_b64,
            sheet=sheet,
            apply_styles=True,
        )
        try:
            return FileConnector._arrow_table_from_excel_rows(ws.values)
        finally:
            wb.close()

    @staticmethod
    def _excel_to_arrow_table(content_b64: str | bytes, sheet: int | str = 0) -> Any | None:
        try:
            return FileConnector._openpyxl_excel_to_arrow_table(content_b64, sheet=sheet)
        except Exception:
            return FileConnector._fast_xlsx_to_arrow_table(content_b64, sheet=sheet)

    @staticmethod
    def _records_from_excel_rows(rows: Any) -> list[dict[str, Any]]:
        return records_from_excel_rows(rows)

    @staticmethod
    def _arrow_table_from_excel_rows(rows: Any) -> Any | None:
        return arrow_table_from_excel_rows(rows)

    @staticmethod
    def _parse_parquet(content_b64: str | bytes) -> list[dict[str, Any]]:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError("Parquet support requires pyarrow: pip install pyarrow") from exc

        raw = FileConnector._decode_binary_content(content_b64)
        initialize_pyarrow_parquet_runtime()
        table = pq.read_table(pa.BufferReader(raw))
        return (
            table.to_pydict()
            and [
                {column: table.column(column)[index].as_py() for column in table.schema.names}
                for index in range(table.num_rows)
            ]
            or []
        )

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            data = await self.fetch_data()
            return True, f"Parsed {len(data)} records."
        except Exception as exc:
            return False, f"Parse failed: {exc}"


def _flatten_dict(
    obj: dict[str, Any],
    prefix: str = "",
    sep: str = ".",
    max_depth: int = 5,
) -> dict[str, Any]:
    return _flatten_dict_impl(obj, prefix=prefix, sep=sep, max_depth=max_depth)
