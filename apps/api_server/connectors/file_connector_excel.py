"""Excel and XLSX parsing helpers for the file connector."""

from __future__ import annotations

import base64
import io
import zipfile
from collections.abc import Generator
from datetime import date, datetime, time
from typing import Any

try:
    from defusedxml import ElementTree
except ModuleNotFoundError:  # pragma: no cover - exercised in clean envs
    from xml.etree import ElementTree

from apps.api_server.services.columnar_loader import normalize_scalar_for_arrow
from apps.api_server.services.data_coercion import (
    _coerce_text_scalar as _base_coerce_text_scalar,
)
from apps.api_server.services.data_coercion import (
    coerce_scalar,
    is_identifier_field,
)

COERCION_CACHE_MAX_ENTRIES = 1024
COERCION_CACHE_MAX_VALUE_LEN = 128
CACHE_MISS = object()
XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XLSX_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XLSX_TAG_ROW = f"{{{XLSX_MAIN_NS}}}row"
XLSX_TAG_CELL = f"{{{XLSX_MAIN_NS}}}c"
XLSX_TAG_VALUE = f"{{{XLSX_MAIN_NS}}}v"
XLSX_TAG_TEXT = f"{{{XLSX_MAIN_NS}}}t"
XLSX_TAG_SHARED_STRING = f"{{{XLSX_MAIN_NS}}}si"
XLSX_COLUMN_INDEX_CACHE_MAX = 128


def _coerce_text_scalar_for_file_connector(
    field_name: str,
    value: str,
    *,
    preserve_identifiers: bool,
) -> Any:
    from . import file_connector as file_connector_module

    hook = getattr(file_connector_module, "_coerce_text_scalar", _base_coerce_text_scalar)
    return hook(field_name, value, preserve_identifiers=preserve_identifiers)


def decode_binary_content(content_b64: str | bytes) -> bytes:
    if isinstance(content_b64, bytes):
        return content_b64
    return base64.b64decode(content_b64)


def xlsx_normalize_member_path(target: str) -> str:
    normalized = target.lstrip("/")
    if not normalized.startswith("xl/"):
        normalized = f"xl/{normalized}"
    return normalized


def xlsx_read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        with archive.open("xl/sharedStrings.xml") as handle:
            strings: list[str] = []
            for _event, element in ElementTree.iterparse(handle, events=("end",)):  # noqa: S314
                if element.tag == XLSX_TAG_SHARED_STRING:
                    strings.append("".join(element.itertext()))
                    element.clear()
            return strings
    except KeyError:
        return []


def xlsx_sheet_target(
    archive: zipfile.ZipFile,
    *,
    sheet: int | str = 0,
) -> tuple[str, datetime]:
    workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))  # noqa: S314
    workbook_props = workbook_root.find(f"{{{XLSX_MAIN_NS}}}workbookPr")
    date_epoch = datetime(1899, 12, 30)
    if workbook_props is not None and workbook_props.get("date1904") in {"1", "true", "True"}:
        date_epoch = datetime(1904, 1, 1)

    rels_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))  # noqa: S314
    rel_map = {
        rel.get("Id", ""): xlsx_normalize_member_path(rel.get("Target", ""))
        for rel in rels_root.findall(f"{{{XLSX_PKG_REL_NS}}}Relationship")
    }

    sheets_parent = workbook_root.find(f"{{{XLSX_MAIN_NS}}}sheets")
    if sheets_parent is None:
        raise KeyError("Workbook has no sheets")

    sheet_entries: list[tuple[str, str]] = []
    rel_attr = f"{{{XLSX_REL_NS}}}id"
    for sheet_meta in sheets_parent.findall(f"{{{XLSX_MAIN_NS}}}sheet"):
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


def xlsx_date_style_indexes(archive: zipfile.ZipFile) -> set[int]:
    try:
        styles_root = ElementTree.fromstring(archive.read("xl/styles.xml"))  # noqa: S314
    except KeyError:
        return set()

    from openpyxl.styles.numbers import BUILTIN_FORMATS, is_date_format

    custom_formats: dict[int, str] = {}
    num_fmts = styles_root.find(f"{{{XLSX_MAIN_NS}}}numFmts")
    if num_fmts is not None:
        for num_fmt in num_fmts.findall(f"{{{XLSX_MAIN_NS}}}numFmt"):
            num_fmt_id = num_fmt.get("numFmtId")
            if num_fmt_id is None:
                continue
            custom_formats[int(num_fmt_id)] = num_fmt.get("formatCode", "")

    date_styles: set[int] = set()
    cell_xfs = styles_root.find(f"{{{XLSX_MAIN_NS}}}cellXfs")
    if cell_xfs is None:
        return date_styles

    for style_index, xf in enumerate(cell_xfs.findall(f"{{{XLSX_MAIN_NS}}}xf")):
        num_fmt_id = xf.get("numFmtId")
        if num_fmt_id is None:
            continue
        format_code = custom_formats.get(int(num_fmt_id)) or BUILTIN_FORMATS.get(int(num_fmt_id))
        if format_code and is_date_format(format_code):
            date_styles.add(style_index)
    return date_styles


def xlsx_column_index_from_ref(
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
            continue
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
    if column_cache is not None and len(column_cache) < XLSX_COLUMN_INDEX_CACHE_MAX:
        column_cache[cache_key] = resolved_index
    return resolved_index


def xlsx_parse_cell_value(
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
        value = "".join(text_node.text or "" for text_node in cell.iter(XLSX_TAG_TEXT))
        return None if value == "" else value

    value_node = cell.find(XLSX_TAG_VALUE)
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


def iter_fast_xlsx_rows(
    content_b64: str | bytes,
    *,
    sheet: int | str = 0,
) -> Generator[tuple[Any, ...], None, None]:
    raw = decode_binary_content(content_b64)
    archive = zipfile.ZipFile(io.BytesIO(raw))
    try:
        shared_strings = xlsx_read_shared_strings(archive)
        sheet_target, date_epoch = xlsx_sheet_target(archive, sheet=sheet)
        date_styles = xlsx_date_style_indexes(archive)
        column_index_cache: dict[str, int] = {}
        with archive.open(sheet_target) as handle:
            current_row: list[Any] = []
            next_default_index = 0
            for _event, element in ElementTree.iterparse(handle, events=("end",)):  # noqa: S314
                if element.tag == XLSX_TAG_CELL:
                    column_index = xlsx_column_index_from_ref(
                        element.get("r"),
                        next_default_index,
                        column_cache=column_index_cache,
                    )
                    if column_index >= len(current_row):
                        current_row.extend([None] * (column_index + 1 - len(current_row)))
                    current_row[column_index] = xlsx_parse_cell_value(
                        element,
                        shared_strings=shared_strings,
                        date_styles=date_styles,
                        date_epoch=date_epoch,
                    )
                    next_default_index = column_index + 1
                    element.clear()
                    continue
                if element.tag == XLSX_TAG_ROW:
                    yield tuple(current_row)
                    current_row = []
                    next_default_index = 0
                    element.clear()
    finally:
        archive.close()


def open_excel_sheet(
    content_b64: str | bytes,
    sheet: int | str = 0,
    *,
    apply_styles: bool = False,
) -> tuple[Any, Any]:
    try:
        from openpyxl.reader.excel import ExcelReader, apply_stylesheet
        from openpyxl.worksheet._read_only import ReadOnlyWorksheet
    except ImportError as exc:
        raise ImportError("Excel support requires openpyxl: pip install openpyxl") from exc

    raw = decode_binary_content(content_b64)
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


def excel_headers(header_row: tuple[Any, ...]) -> list[str]:
    return [
        str(header) if header is not None else f"col_{index}"
        for index, header in enumerate(header_row)
    ]


def cacheable_excel_text_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cache_key = value.strip()
    if cache_key == "" or len(cache_key) > COERCION_CACHE_MAX_VALUE_LEN:
        return None
    return cache_key


def coerce_excel_record_value(
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
        return _coerce_text_scalar_for_file_connector(
            field_name,
            value.strip(),
            preserve_identifiers=preserve_identifiers,
        )
    return coerce_scalar(field_name, value, preserve_identifiers=True)


def coerce_excel_arrow_value(
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
        coerced = _coerce_text_scalar_for_file_connector(
            field_name,
            value.strip(),
            preserve_identifiers=preserve_identifiers,
        )
        return None if coerced == "" else coerced
    return normalize_scalar_for_arrow(field_name, value)


def coerce_excel_record_value_cached(
    field_name: str,
    value: Any,
    *,
    preserve_identifier_field: bool,
    cache: dict[str, Any],
) -> Any:
    cache_key = cacheable_excel_text_value(value)
    if cache_key is None:
        return coerce_excel_record_value(
            field_name,
            value,
            preserve_identifier_field=preserve_identifier_field,
        )
    cached = cache.get(cache_key, CACHE_MISS)
    if cached is not CACHE_MISS:
        return cached

    coerced = _coerce_text_scalar_for_file_connector(
        field_name,
        cache_key,
        preserve_identifiers=preserve_identifier_field,
    )
    if len(cache) < COERCION_CACHE_MAX_ENTRIES:
        cache[cache_key] = coerced
    return coerced


def coerce_excel_arrow_value_cached(
    field_name: str,
    value: Any,
    *,
    preserve_identifier_field: bool,
    cache: dict[str, Any],
) -> Any:
    cache_key = cacheable_excel_text_value(value)
    if cache_key is None:
        return coerce_excel_arrow_value(
            field_name,
            value,
            preserve_identifier_field=preserve_identifier_field,
        )
    cached = cache.get(cache_key, CACHE_MISS)
    if cached is not CACHE_MISS:
        return cached

    coerced = _coerce_text_scalar_for_file_connector(
        field_name,
        cache_key,
        preserve_identifiers=preserve_identifier_field,
    )
    normalized = None if coerced == "" else coerced
    if len(cache) < COERCION_CACHE_MAX_ENTRIES:
        cache[cache_key] = normalized
    return normalized


def final_excel_headers(headers: list[str]) -> tuple[list[str], list[int]]:
    last_index: dict[str, int] = {}
    for index, header in enumerate(headers):
        last_index[header] = index

    final_headers = [header for index, header in enumerate(headers) if last_index[header] == index]
    final_indexes = [last_index[header] for header in final_headers]
    return final_headers, final_indexes


def arrow_table_from_excel_columns(columns: dict[str, list[Any]]) -> Any | None:
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


def records_from_excel_rows(rows: Any) -> list[dict[str, Any]]:
    row_iter = iter(rows)
    try:
        headers = excel_headers(next(row_iter))
    except StopIteration:
        return []

    header_count = len(headers)
    identifier_fields = [bool(header) and is_identifier_field(header) for header in headers]
    coercion_caches: list[dict[str, Any]] = [{} for _ in headers]
    records: list[dict[str, Any]] = []
    for row in row_iter:
        record: dict[str, Any] = {}
        row_len = len(row)
        for idx in range(header_count):
            header = headers[idx]
            value = row[idx] if idx < row_len else None
            record[header] = coerce_excel_record_value_cached(
                header,
                value,
                preserve_identifier_field=identifier_fields[idx],
                cache=coercion_caches[idx],
            )
        records.append(record)
    return records


def arrow_table_from_excel_rows(rows: Any) -> Any | None:
    import pyarrow as pa

    row_iter = iter(rows)
    try:
        headers = excel_headers(next(row_iter))
    except StopIteration:
        return pa.table({})

    final_headers, final_indexes = final_excel_headers(headers)
    identifier_fields = [bool(header) and is_identifier_field(header) for header in final_headers]
    columns: dict[str, list[Any]] = {header: [] for header in final_headers}
    appenders = [columns[header].append for header in final_headers]
    coercion_caches: list[dict[str, Any]] = [{} for _ in final_headers]
    header_count = len(final_headers)

    for row in row_iter:
        row_len = len(row)
        for idx in range(header_count):
            index = final_indexes[idx]
            value = row[index] if index < row_len else None
            appenders[idx](
                coerce_excel_arrow_value_cached(
                    final_headers[idx],
                    value,
                    preserve_identifier_field=identifier_fields[idx],
                    cache=coercion_caches[idx],
                )
            )

    return arrow_table_from_excel_columns(columns)


def fast_xlsx_to_arrow_table(content_b64: str | bytes, *, sheet: int | str = 0) -> Any | None:
    import pyarrow as pa

    raw = decode_binary_content(content_b64)
    archive = zipfile.ZipFile(io.BytesIO(raw))
    try:
        shared_strings = xlsx_read_shared_strings(archive)
        sheet_target, date_epoch = xlsx_sheet_target(archive, sheet=sheet)
        date_styles = xlsx_date_style_indexes(archive)
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
                if element.tag == XLSX_TAG_CELL:
                    column_index = xlsx_column_index_from_ref(
                        element.get("r"),
                        next_default_index,
                        column_cache=column_index_cache,
                    )
                    if column_index >= len(current_row):
                        current_row.extend([None] * (column_index + 1 - len(current_row)))
                    current_row[column_index] = xlsx_parse_cell_value(
                        element,
                        shared_strings=shared_strings,
                        date_styles=date_styles,
                        date_epoch=date_epoch,
                    )
                    next_default_index = column_index + 1
                    element.clear()
                    continue

                if element.tag != XLSX_TAG_ROW:
                    continue

                if final_headers is None:
                    headers = excel_headers(tuple(current_row))
                    final_headers, final_indexes = final_excel_headers(headers)
                    identifier_fields = [
                        bool(header) and is_identifier_field(header) for header in final_headers
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
                            coerce_excel_arrow_value_cached(
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
        return arrow_table_from_excel_columns(columns)
    finally:
        archive.close()
