from __future__ import annotations

import csv
import io
from typing import Any

from apps.api_server.services.data_coercion import (
    _coerce_text_scalar,
    canonicalize_delimited_headers,
    coerce_scalar,
    is_identifier_field,
    looks_like_header_alias_row,
)

NULL_LIKE_STRINGS = frozenset({
    "",
    "?",
    "none",
    "null",
    "nan",
    "n/a",
    "na",
})

_ARROW_RETRY_MAX_BYTES = 32 * 1024 * 1024
_PANDAS_FALLBACK_MIN_BYTES = 1 * 1024 * 1024
_COERCION_CACHE_MAX_ENTRIES = 1024
_COERCION_CACHE_MAX_VALUE_LEN = 128
_CACHE_MISS = object()


def _normalized_delimited_scalar(value: Any) -> str | None:
    if value is None:
        return None
    normalized = value.strip() if isinstance(value, str) else str(value).strip()
    if normalized == "" or normalized.lower() in NULL_LIKE_STRINGS:
        return None
    return normalized


def normalize_scalar_for_arrow(
    field_name: str,
    value: Any,
    *,
    assume_coerced: bool = False,
) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in NULL_LIKE_STRINGS:
        return None
    if assume_coerced:
        return None if value == "" else value
    coerced = coerce_scalar(field_name, value, preserve_identifiers=True)
    return None if coerced == "" else coerced


def _to_arrow_array(values: list[Any]) -> Any:
    import pyarrow as pa

    try:
        return pa.array(values)
    except Exception:
        return pa.array(
            [str(value) if value is not None else None for value in values],
            type=pa.string(),
        )


def _strip_header_alias_row_from_table(table: Any) -> Any:
    if table is None or table.num_rows <= 0:
        return table
    try:
        first_row = table.slice(0, 1).to_pylist()[0]
    except Exception:
        return table
    field_names = list(table.column_names)
    values = [first_row.get(field_name) for field_name in field_names]
    if looks_like_header_alias_row(field_names, values):
        return table.slice(1)
    return table


def _coerce_scalar_for_arrow(
    field_name: str,
    value: Any,
    *,
    preserve_identifier_field: bool,
) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        raw = _normalized_delimited_scalar(value)
        if raw is None:
            return None
        if preserve_identifier_field:
            return raw
        coerced = _coerce_text_scalar(
            field_name,
            raw,
            preserve_identifiers=preserve_identifier_field,
        )
        return None if coerced == "" else coerced
    coerced = coerce_scalar(
        field_name,
        value,
        preserve_identifiers=preserve_identifier_field,
    )
    return None if coerced == "" else coerced


def _coerce_scalar_for_arrow_cached(
    field_name: str,
    value: Any,
    *,
    preserve_identifier_field: bool,
    cache: dict[str, Any],
) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return _coerce_scalar_for_arrow(
            field_name,
            value,
            preserve_identifier_field=preserve_identifier_field,
        )

    cache_key = _normalized_delimited_scalar(value)
    if cache_key is None:
        return None
    if preserve_identifier_field:
        return cache_key
    if len(cache_key) > _COERCION_CACHE_MAX_VALUE_LEN:
        coerced = _coerce_text_scalar(
            field_name,
            cache_key,
            preserve_identifiers=preserve_identifier_field,
        )
        return None if coerced == "" else coerced

    cached_value = cache.get(cache_key, _CACHE_MISS)
    if cached_value is not _CACHE_MISS:
        return cached_value

    coerced = _coerce_text_scalar(
        field_name,
        cache_key,
        preserve_identifiers=preserve_identifier_field,
    )
    if coerced == "":
        coerced = None
    if len(cache) < _COERCION_CACHE_MAX_ENTRIES:
        cache[cache_key] = coerced
    return coerced


def _build_delimited_column_handler(
    field_name: str,
    *,
    preserve_identifier_field: bool,
    cache: dict[str, Any] | None = None,
):
    if preserve_identifier_field:
        def _handle_identifier(value: Any) -> Any:
            return _normalized_delimited_scalar(value)
        return _handle_identifier

    assert cache is not None

    def _handle_cached(value: Any) -> Any:
        return _coerce_scalar_for_arrow_cached(
            field_name,
            value,
            preserve_identifier_field=False,
            cache=cache,
        )

    return _handle_cached


def records_to_arrow_table(
    records: list[dict[str, Any]],
    *,
    assume_coerced: bool = False,
) -> Any:
    import pyarrow as pa

    if not records:
        return pa.table({})

    field_names: list[str] = []
    seen_fields: set[str] = set()
    for row in records:
        for field_name in row.keys():
            if field_name is None:
                continue
            normalized_name = str(field_name)
            if normalized_name not in seen_fields:
                seen_fields.add(normalized_name)
                field_names.append(normalized_name)

    columns: dict[str, list[Any]] = {field_name: [] for field_name in field_names}
    for row in records:
        for field_name in field_names:
            columns[field_name].append(
                normalize_scalar_for_arrow(
                    field_name,
                    row.get(field_name),
                    assume_coerced=assume_coerced,
                )
            )

    table = pa.table({
        field_name: _to_arrow_array(values)
        for field_name, values in columns.items()
    })
    return _strip_header_alias_row_from_table(table)


def _python_delimited_text_to_arrow_table(content: str, *, delimiter: str) -> Any:
    import pyarrow as pa

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    try:
        headers = canonicalize_delimited_headers(next(reader))
    except StopIteration:
        return pa.table({})

    if not headers:
        return pa.table({})

    field_names = list(headers)
    identifier_fields = [
        bool(field_name) and is_identifier_field(field_name)
        for field_name in field_names
    ]
    column_values: list[list[Any]] = [[] for _ in field_names]
    appenders = [values.append for values in column_values]
    coercion_caches: list[dict[str, Any]] = [{} for _ in headers]
    handlers = [
        _build_delimited_column_handler(
            field_name,
            preserve_identifier_field=identifier_fields[idx],
            cache=None if identifier_fields[idx] else coercion_caches[idx],
        )
        for idx, field_name in enumerate(field_names)
    ]
    header_count = len(field_names)
    for row in reader:
        row_len = len(row)
        shared_count = min(row_len, header_count)
        for idx in range(shared_count):
            appenders[idx](handlers[idx](row[idx]))
        for idx in range(shared_count, header_count):
            appenders[idx](None)

    table = pa.table({
        field_name: _to_arrow_array(values)
        for field_name, values in zip(field_names, column_values, strict=False)
    })
    return _strip_header_alias_row_from_table(table)


def _pandas_delimited_text_to_arrow_table(
    content: str,
    *,
    delimiter: str,
    headers: list[str],
) -> Any:
    import pandas as pd
    import pyarrow as pa

    dtype_map = {
        header: "string"
        for header in headers
        if header and is_identifier_field(header)
    }
    dataframe = pd.read_csv(
        io.StringIO(content),
        sep=delimiter,
        engine="c",
        dtype=dtype_map or None,
        keep_default_na=False,
        na_values=sorted(NULL_LIKE_STRINGS),
        on_bad_lines="error",
        low_memory=False,
    )
    return _strip_header_alias_row_from_table(
        pa.Table.from_pandas(dataframe, preserve_index=False)
    )


def _choose_delimiter(text: str, delimiter: str | None = ",", sniff: bool = True) -> str:
    chosen_delimiter = delimiter or ","
    if sniff and delimiter in (None, "", ","):
        try:
            sample = text[:4096]
            sniffed = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            chosen_delimiter = sniffed.delimiter
        except csv.Error:
            chosen_delimiter = delimiter or ","
    return chosen_delimiter


def _delimited_headers(text: str, delimiter: str) -> list[str]:
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        return canonicalize_delimited_headers(next(reader))
    except StopIteration:
        return []


def looks_arrow_friendly_delimited_text(
    content: str,
    *,
    delimiter: str | None = ",",
    sniff: bool = True,
) -> bool:
    if not content or not content.strip():
        return True

    text = content.lstrip("\ufeff")
    chosen_delimiter = _choose_delimiter(text, delimiter=delimiter, sniff=sniff)
    headers = _delimited_headers(text, chosen_delimiter)
    if len(headers) > 96:
        return False

    sample = text[:200_000]
    lines = [line for line in sample.splitlines() if line.strip()][:64]
    if len(lines) <= 1:
        return True

    counts = [line.count(chosen_delimiter) for line in lines]
    if max(counts) - min(counts) > 2:
        return False

    quote_density = sample.count('"') / max(len(sample), 1)
    if quote_density > 0.009:
        return False

    return True


def delimited_text_to_arrow_table(
    content: str,
    *,
    delimiter: str | None = ",",
    sniff: bool = True,
) -> Any:
    if not content or not content.strip():
        import pyarrow as pa
        return pa.table({})

    import pyarrow as pa
    import pyarrow.csv as pacsv

    text = content.lstrip("\ufeff")
    raw_bytes = text.encode("utf-8")
    arrow_friendly = looks_arrow_friendly_delimited_text(text, delimiter=delimiter, sniff=sniff)
    allow_retry = len(raw_bytes) <= _ARROW_RETRY_MAX_BYTES
    chosen_delimiter = _choose_delimiter(text, delimiter=delimiter, sniff=sniff)
    headers = _delimited_headers(text, chosen_delimiter)
    column_types = {
        header: pa.string()
        for header in headers
        if header and is_identifier_field(header)
    }

    convert_options = pacsv.ConvertOptions(
        column_types=column_types or None,
        null_values=sorted(NULL_LIKE_STRINGS),
        strings_can_be_null=True,
    )
    read_options_kwargs: dict[str, Any] = {
        "use_threads": True,
        "block_size": 1 << 20,
    }
    if headers:
        read_options_kwargs["column_names"] = headers
        read_options_kwargs["skip_rows"] = 1
    read_options = pacsv.ReadOptions(**read_options_kwargs)
    standard_parse_options = pacsv.ParseOptions(delimiter=chosen_delimiter)
    retry_parse_options = pacsv.ParseOptions(
        delimiter=chosen_delimiter,
        newlines_in_values=True,
    )
    last_error: Exception | None = None

    if arrow_friendly:
        try:
            return _strip_header_alias_row_from_table(
                pacsv.read_csv(
                    pa.BufferReader(raw_bytes),
                    read_options=read_options,
                    parse_options=standard_parse_options,
                    convert_options=convert_options,
                )
            )
        except Exception as exc:
            last_error = exc
    elif not allow_retry:
        last_error = ValueError(
            "delimited source is not Arrow-friendly enough for fast-path parsing"
        )

    if allow_retry:
        try:
            return _strip_header_alias_row_from_table(
                pacsv.read_csv(
                    pa.BufferReader(raw_bytes),
                    read_options=read_options,
                    parse_options=retry_parse_options,
                    convert_options=convert_options,
                )
            )
        except Exception as exc:
            last_error = exc

    if len(raw_bytes) >= _PANDAS_FALLBACK_MIN_BYTES:
        try:
            return _strip_header_alias_row_from_table(
                _pandas_delimited_text_to_arrow_table(
                    text,
                    delimiter=chosen_delimiter,
                    headers=headers,
                )
            )
        except Exception as exc:
            last_error = exc

    try:
        return _strip_header_alias_row_from_table(
            _python_delimited_text_to_arrow_table(
                text,
                delimiter=chosen_delimiter,
            )
        )
    except Exception as exc:
        if last_error is not None:
            raise last_error from exc
        raise
