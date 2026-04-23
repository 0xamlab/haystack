"""File-based data connector (CSV, TSV, JSON, Excel, Parquet)."""
from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import date, datetime, time
from typing import Any

try:
    from defusedxml import ElementTree
except ModuleNotFoundError:  # pragma: no cover - exercised in clean envs
    from xml.etree import ElementTree

from apps.api_server.services.columnar_loader import (
    delimited_text_to_arrow_table,
    normalize_scalar_for_arrow,
    records_to_arrow_table,
)
from apps.api_server.services.data_coercion import (
    _coerce_text_scalar,
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
    _COERCION_CACHE_MAX_ENTRIES = 1024
    _COERCION_CACHE_MAX_VALUE_LEN = 128
    _CACHE_MISS = object()
    _XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    _XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    _XLSX_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
    _XLSX_TAG_ROW = f"{{{_XLSX_MAIN_NS}}}row"
    _XLSX_TAG_CELL = f"{{{_XLSX_MAIN_NS}}}c"
    _XLSX_TAG_VALUE = f"{{{_XLSX_MAIN_NS}}}v"
    _XLSX_TAG_TEXT = f"{{{_XLSX_MAIN_NS}}}t"
    _XLSX_TAG_SHARED_STRING = f"{{{_XLSX_MAIN_NS}}}si"
    _XLSX_COLUMN_INDEX_CACHE_MAX = 128

    @staticmethod
    def _load_content(file_type: str, content: str | bytes, file_path: str) -> str | bytes:
        if file_path and not content:
            mode = "rb" if file_type in ("excel", "parquet") else "r"
            with open(file_path, mode) as f:
                return f.read()
        return content

    @staticmethod
    def _decode_binary_content(content_b64: str | bytes) -> bytes:
        if isinstance(content_b64, bytes):
            return content_b64
        return base64.b64decode(content_b64)

    @staticmethod
    def _xlsx_normalize_member_path(target: str) -> str:
        normalized = target.lstrip("/")
        if not normalized.startswith("xl/"):
            normalized = f"xl/{normalized}"
        return normalized

    @staticmethod
    def _xlsx_read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
        try:
            with archive.open("xl/sharedStrings.xml") as handle:
                strings: list[str] = []
                for _event, element in ElementTree.iterparse(handle, events=("end",)):  # noqa: S314
                    if element.tag == FileConnector._XLSX_TAG_SHARED_STRING:
                        strings.append("".join(element.itertext()))
                        element.clear()
                return strings
        except KeyError:
            return []

    @staticmethod
    def _xlsx_sheet_target(
        archive: zipfile.ZipFile,
        *,
        sheet: int | str = 0,
    ) -> tuple[str, datetime]:
        workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))  # noqa: S314
        workbook_props = workbook_root.find(f"{{{FileConnector._XLSX_MAIN_NS}}}workbookPr")
        date_epoch = datetime(1899, 12, 30)
        if workbook_props is not None and workbook_props.get("date1904") in {"1", "true", "True"}:
            date_epoch = datetime(1904, 1, 1)

        rels_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))  # noqa: S314
        rel_map = {
            rel.get("Id", ""): FileConnector._xlsx_normalize_member_path(rel.get("Target", ""))
            for rel in rels_root.findall(f"{{{FileConnector._XLSX_PKG_REL_NS}}}Relationship")
        }

        sheets_parent = workbook_root.find(f"{{{FileConnector._XLSX_MAIN_NS}}}sheets")
        if sheets_parent is None:
            raise KeyError("Workbook has no sheets")

        sheet_entries: list[tuple[str, str]] = []
        rel_attr = f"{{{FileConnector._XLSX_REL_NS}}}id"
        for sheet_meta in sheets_parent.findall(f"{{{FileConnector._XLSX_MAIN_NS}}}sheet"):
            rel_id = sheet_meta.get(rel_attr, "")
            target = rel_map.get(rel_id)
            if not target:
                continue
            sheet_entries.append((sheet_meta.get("name", ""), target))

        if isinstance(sheet, int):
            try:
                _sheet_name, target = sheet_entries[sheet]
            except IndexError as exc:
                raise IndexError(sheet) from exc
            return target, date_epoch

        for sheet_name, target in sheet_entries:
            if sheet_name == sheet:
                return target, date_epoch
        raise KeyError(sheet)

    @staticmethod
    def _xlsx_date_style_indexes(archive: zipfile.ZipFile) -> set[int]:
        try:
            styles_root = ElementTree.fromstring(archive.read("xl/styles.xml"))  # noqa: S314
        except KeyError:
            return set()

        from openpyxl.styles.numbers import BUILTIN_FORMATS, is_date_format

        custom_formats: dict[int, str] = {}
        num_fmts = styles_root.find(f"{{{FileConnector._XLSX_MAIN_NS}}}numFmts")
        if num_fmts is not None:
            for num_fmt in num_fmts.findall(f"{{{FileConnector._XLSX_MAIN_NS}}}numFmt"):
                num_fmt_id = num_fmt.get("numFmtId")
                if num_fmt_id is None:
                    continue
                custom_formats[int(num_fmt_id)] = num_fmt.get("formatCode", "")

        date_styles: set[int] = set()
        cell_xfs = styles_root.find(f"{{{FileConnector._XLSX_MAIN_NS}}}cellXfs")
        if cell_xfs is None:
            return date_styles

        for style_index, xf in enumerate(cell_xfs.findall(f"{{{FileConnector._XLSX_MAIN_NS}}}xf")):
            num_fmt_id = xf.get("numFmtId")
            if num_fmt_id is None:
                continue
            format_code = custom_formats.get(int(num_fmt_id)) or BUILTIN_FORMATS.get(
                int(num_fmt_id)
            )
            if format_code and is_date_format(format_code):
                date_styles.add(style_index)
        return date_styles

    @staticmethod
    def _xlsx_column_index_from_ref(
        ref: str | None,
        default_index: int,
        *,
        column_cache: dict[str, int] | None = None,
    ) -> int:
        if not ref:
            return default_index
        letters: list[str] = []
        for char in ref:
            if char.isalpha():
                letters.append(char.upper())
            else:
                break
        if not letters:
            return default_index
        cache_key = "".join(letters)
        if column_cache is not None:
            cached_index = column_cache.get(cache_key)
            if cached_index is not None:
                return cached_index
        column_index = 0
        for char in cache_key:
            column_index = (column_index * 26) + (ord(char) - 64)
        resolved_index = max(column_index - 1, default_index)
        if (
            column_cache is not None
            and len(column_cache) < FileConnector._XLSX_COLUMN_INDEX_CACHE_MAX
        ):
            column_cache[cache_key] = resolved_index
        return resolved_index

    @staticmethod
    def _xlsx_parse_cell_value(
        cell: ElementTree.Element,
        *,
        shared_strings: list[str],
        date_styles: set[int],
        date_epoch: datetime,
    ) -> Any:
        from openpyxl.utils.datetime import from_excel

        cell_type = cell.get("t")
        style_index = int(cell.get("s", "-1"))

        if cell_type == "inlineStr":
            value = "".join(
                text_node.text or ""
                for text_node in cell.iter(FileConnector._XLSX_TAG_TEXT)
            )
            return None if value == "" else value

        value_node = cell.find(FileConnector._XLSX_TAG_VALUE)
        if value_node is None or value_node.text is None:
            return None
        raw_value = value_node.text

        if cell_type == "s":
            shared_index = int(raw_value)
            if 0 <= shared_index < len(shared_strings):
                value = shared_strings[shared_index]
                return None if value == "" else value
            return raw_value
        if cell_type == "b":
            return raw_value == "1"
        if cell_type in {"str", "e"}:
            return raw_value
        if cell_type == "d":
            try:
                return datetime.fromisoformat(raw_value)
            except ValueError:
                return raw_value

        try:
            numeric_value = float(raw_value)
        except ValueError:
            return raw_value

        if style_index in date_styles:
            return from_excel(numeric_value, epoch=date_epoch)
        if numeric_value.is_integer():
            return int(numeric_value)
        return numeric_value

    @staticmethod
    def _iter_fast_xlsx_rows(content_b64: str | bytes, *, sheet: int | str = 0):
        raw = FileConnector._decode_binary_content(content_b64)
        archive = zipfile.ZipFile(io.BytesIO(raw))
        try:
            shared_strings = FileConnector._xlsx_read_shared_strings(archive)
            sheet_target, date_epoch = FileConnector._xlsx_sheet_target(archive, sheet=sheet)
            date_styles = FileConnector._xlsx_date_style_indexes(archive)
            column_index_cache: dict[str, int] = {}
            with archive.open(sheet_target) as handle:
                current_row: list[Any] = []
                next_default_index = 0
                for _event, element in ElementTree.iterparse(handle, events=("end",)):  # noqa: S314
                    if element.tag == FileConnector._XLSX_TAG_CELL:
                        column_index = FileConnector._xlsx_column_index_from_ref(
                            element.get("r"),
                            next_default_index,
                            column_cache=column_index_cache,
                        )
                        if column_index >= len(current_row):
                            current_row.extend([None] * (column_index + 1 - len(current_row)))
                        current_row[column_index] = FileConnector._xlsx_parse_cell_value(
                            element,
                            shared_strings=shared_strings,
                            date_styles=date_styles,
                            date_epoch=date_epoch,
                        )
                        next_default_index = column_index + 1
                        element.clear()
                        continue
                    if element.tag == FileConnector._XLSX_TAG_ROW:
                        yield tuple(current_row)
                        current_row = []
                        next_default_index = 0
                        element.clear()
        finally:
            archive.close()

    async def fetch_data(self) -> list[dict[str, Any]]:
        file_type: str = self.config.get("file_type", "csv").lower()
        content: str | bytes = self.config.get("content", "")
        file_path: str = self.config.get("file_path", "")

        content = self._load_content(file_type, content, file_path)

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
        content: str | bytes = self.config.get("content", "")
        file_path: str = self.config.get("file_path", "")

        content = self._load_content(file_type, content, file_path)

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

            raw = self._decode_binary_content(content)
            initialize_pyarrow_parquet_runtime()
            return pq.read_table(pa.BufferReader(raw))
        return None

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _open_excel_sheet(
        content_b64: str | bytes,
        sheet: int | str = 0,
        *,
        apply_styles: bool = False,
    ) -> tuple[Any, Any]:
        try:
            from openpyxl.reader.excel import ExcelReader, apply_stylesheet
            from openpyxl.worksheet._read_only import ReadOnlyWorksheet
        except ImportError as exc:
            raise ImportError(
                "Excel support requires openpyxl: pip install openpyxl"
            ) from exc

        raw = FileConnector._decode_binary_content(content_b64)
        reader = ExcelReader(
            io.BytesIO(raw),
            read_only=True,
            data_only=True,
            keep_links=False,
        )
        reader.read_manifest()
        reader.read_strings()
        reader.read_workbook()
        if apply_styles:
            apply_stylesheet(reader.archive, reader.wb)

        worksheet_entries: list[tuple[Any, Any]] = []
        for sheet_meta, rel in reader.parser.find_sheets():
            if rel.target not in reader.valid_files or "chartsheet" in rel.Type:
                continue
            worksheet_entries.append((sheet_meta, rel))

        if isinstance(sheet, int):
            try:
                sheet_meta, rel = worksheet_entries[sheet]
            except IndexError:
                reader.archive.close()
                raise
        else:
            selected = next(
                (
                    (sheet_meta, rel)
                    for sheet_meta, rel in worksheet_entries
                    if sheet_meta.name == sheet
                ),
                None,
            )
            if selected is None:
                reader.archive.close()
                raise KeyError(sheet)
            sheet_meta, rel = selected

        ws = ReadOnlyWorksheet(reader.wb, sheet_meta.name, rel.target, reader.shared_strings)
        ws.sheet_state = sheet_meta.state
        reader.wb._sheets.append(ws)
        return reader.wb, ws

    @staticmethod
    def _excel_headers(header_row: tuple[Any, ...]) -> list[str]:
        return [
            str(header) if header is not None else f"col_{index}"
            for index, header in enumerate(header_row)
        ]

    @staticmethod
    def _cacheable_excel_text_value(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cache_key = value.strip()
        if cache_key == "" or len(cache_key) > FileConnector._COERCION_CACHE_MAX_VALUE_LEN:
            return None
        return cache_key

    @staticmethod
    def _coerce_excel_record_value(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool | None = None,
    ) -> Any:
        if value is None:
            return ""
        if is_identifier_field(field_name) and isinstance(value, int | float):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        if isinstance(value, datetime | date | time):
            return str(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return value
        if isinstance(value, str):
            preserve_identifiers = (
                is_identifier_field(field_name)
                if preserve_identifier_field is None
                else preserve_identifier_field
            )
            return _coerce_text_scalar(
                field_name,
                value.strip(),
                preserve_identifiers=preserve_identifiers,
            )
        return coerce_scalar(field_name, value, preserve_identifiers=True)

    @staticmethod
    def _coerce_excel_arrow_value(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool | None = None,
    ) -> Any:
        if value is None:
            return None
        if is_identifier_field(field_name) and isinstance(value, int | float):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        if isinstance(value, datetime | date | time):
            return str(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return value
        if isinstance(value, str):
            preserve_identifiers = (
                is_identifier_field(field_name)
                if preserve_identifier_field is None
                else preserve_identifier_field
            )
            coerced = _coerce_text_scalar(
                field_name,
                value.strip(),
                preserve_identifiers=preserve_identifiers,
            )
            return None if coerced == "" else coerced
        return normalize_scalar_for_arrow(field_name, value)

    @staticmethod
    def _coerce_excel_record_value_cached(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool,
        cache: dict[str, Any],
    ) -> Any:
        cache_key = FileConnector._cacheable_excel_text_value(value)
        if cache_key is None:
            return FileConnector._coerce_excel_record_value(
                field_name,
                value,
                preserve_identifier_field=preserve_identifier_field,
            )
        cached = cache.get(cache_key, FileConnector._CACHE_MISS)
        if cached is not FileConnector._CACHE_MISS:
            return cached
        coerced = _coerce_text_scalar(
            field_name,
            cache_key,
            preserve_identifiers=preserve_identifier_field,
        )
        if len(cache) < FileConnector._COERCION_CACHE_MAX_ENTRIES:
            cache[cache_key] = coerced
        return coerced

    @staticmethod
    def _coerce_excel_arrow_value_cached(
        field_name: str,
        value: Any,
        *,
        preserve_identifier_field: bool,
        cache: dict[str, Any],
    ) -> Any:
        cache_key = FileConnector._cacheable_excel_text_value(value)
        if cache_key is None:
            return FileConnector._coerce_excel_arrow_value(
                field_name,
                value,
                preserve_identifier_field=preserve_identifier_field,
            )
        cached = cache.get(cache_key, FileConnector._CACHE_MISS)
        if cached is not FileConnector._CACHE_MISS:
            return cached
        coerced = _coerce_text_scalar(
            field_name,
            cache_key,
            preserve_identifiers=preserve_identifier_field,
        )
        normalized = None if coerced == "" else coerced
        if len(cache) < FileConnector._COERCION_CACHE_MAX_ENTRIES:
            cache[cache_key] = normalized
        return normalized

    @staticmethod
    def _final_excel_headers(
        headers: list[str],
    ) -> tuple[list[str], list[int]]:
        last_index: dict[str, int] = {}
        for index, header in enumerate(headers):
            last_index[header] = index
        final_headers = [
            header
            for index, header in enumerate(headers)
            if last_index[header] == index
        ]
        final_indexes = [last_index[header] for header in final_headers]
        return final_headers, final_indexes

    @staticmethod
    def _arrow_table_from_excel_columns(columns: dict[str, list[Any]]) -> Any | None:
        import pyarrow as pa

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

    @staticmethod
    def _fast_xlsx_to_arrow_table(content_b64: str | bytes, *, sheet: int | str = 0) -> Any | None:
        import pyarrow as pa

        raw = FileConnector._decode_binary_content(content_b64)
        archive = zipfile.ZipFile(io.BytesIO(raw))
        try:
            shared_strings = FileConnector._xlsx_read_shared_strings(archive)
            sheet_target, date_epoch = FileConnector._xlsx_sheet_target(archive, sheet=sheet)
            date_styles = FileConnector._xlsx_date_style_indexes(archive)
            column_index_cache: dict[str, int] = {}
            with archive.open(sheet_target) as handle:
                current_row: list[Any] = []
                next_default_index = 0
                final_headers: list[str] | None = None
                final_indexes: list[int] = []
                identifier_fields: list[bool] = []
                columns: dict[str, list[Any]] | None = None
                appenders: list[Any] = []
                coercion_caches: list[dict[str, Any]] = []
                header_count = 0

                for _event, element in ElementTree.iterparse(handle, events=("end",)):  # noqa: S314
                    if element.tag == FileConnector._XLSX_TAG_CELL:
                        column_index = FileConnector._xlsx_column_index_from_ref(
                            element.get("r"),
                            next_default_index,
                            column_cache=column_index_cache,
                        )
                        if column_index >= len(current_row):
                            current_row.extend([None] * (column_index + 1 - len(current_row)))
                        current_row[column_index] = FileConnector._xlsx_parse_cell_value(
                            element,
                            shared_strings=shared_strings,
                            date_styles=date_styles,
                            date_epoch=date_epoch,
                        )
                        next_default_index = column_index + 1
                        element.clear()
                        continue

                    if element.tag != FileConnector._XLSX_TAG_ROW:
                        continue

                    if final_headers is None:
                        headers = FileConnector._excel_headers(tuple(current_row))
                        final_headers, final_indexes = FileConnector._final_excel_headers(headers)
                        identifier_fields = [
                            bool(header) and is_identifier_field(header)
                            for header in final_headers
                        ]
                        columns = {header: [] for header in final_headers}
                        appenders = [columns[header].append for header in final_headers]
                        coercion_caches = [{} for _ in final_headers]
                        header_count = len(final_headers)
                    else:
                        row_len = len(current_row)
                        for idx in range(header_count):
                            column_index = final_indexes[idx]
                            value = current_row[column_index] if column_index < row_len else None
                            appenders[idx](
                                FileConnector._coerce_excel_arrow_value_cached(
                                    final_headers[idx],
                                    value,
                                    preserve_identifier_field=identifier_fields[idx],
                                    cache=coercion_caches[idx],
                                )
                            )

                    current_row = []
                    next_default_index = 0
                    element.clear()

            if columns is None:
                return pa.table({})
            return FileConnector._arrow_table_from_excel_columns(columns)
        finally:
            archive.close()

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
        try:
            headers = FileConnector._excel_headers(next(rows))
        except StopIteration:
            return []

        header_count = len(headers)
        identifier_fields = [
            bool(header) and is_identifier_field(header)
            for header in headers
        ]
        coercion_caches: list[dict[str, Any]] = [{} for _ in headers]
        records: list[dict[str, Any]] = []
        for row in rows:
            rec: dict[str, Any] = {}
            row_len = len(row)
            for idx in range(header_count):
                header = headers[idx]
                value = row[idx] if idx < row_len else None
                rec[header] = FileConnector._coerce_excel_record_value_cached(
                    header,
                    value,
                    preserve_identifier_field=identifier_fields[idx],
                    cache=coercion_caches[idx],
                )
            records.append(rec)
        return records

    @staticmethod
    def _arrow_table_from_excel_rows(rows: Any) -> Any | None:
        import pyarrow as pa

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
        identifier_fields = [
            bool(header) and is_identifier_field(header)
            for header in final_headers
        ]
        columns: dict[str, list[Any]] = {header: [] for header in final_headers}
        appenders = [columns[header].append for header in final_headers]
        coercion_caches: list[dict[str, Any]] = [{} for _ in final_headers]
        header_count = len(final_headers)

        for row in rows:
            row_len = len(row)
            for idx in range(header_count):
                index = final_indexes[idx]
                value = row[index] if index < row_len else None
                appenders[idx](
                    FileConnector._coerce_excel_arrow_value_cached(
                        final_headers[idx],
                        value,
                        preserve_identifier_field=identifier_fields[idx],
                        cache=coercion_caches[idx],
                    )
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

    @staticmethod
    def _parse_parquet(content_b64: str | bytes) -> list[dict[str, Any]]:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq  # lazy — optional dependency
        except ImportError as exc:
            raise ImportError(
                "Parquet support requires pyarrow: pip install pyarrow"
            ) from exc

        raw = FileConnector._decode_binary_content(content_b64)
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
