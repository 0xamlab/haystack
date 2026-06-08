from __future__ import annotations

import math
from typing import Any

_FAST_SCAN_ROWS = 200  # rows checked in fast path
_SPARSE_THRESHOLD = 10  # if fewer non-empty values in fast scan → deep scan
_TARGET_SAMPLES = 500  # non-empty values to collect per column (stop early)
_NUM_COERCE_CHARS = str.maketrans("", "", ",$% \t")  # strip before float() attempt


def _relation_detect_sample_limit(column_count: int) -> int:
    if column_count >= 128:
        return 64
    if column_count >= 64:
        return 128
    if column_count >= 32:
        return 192
    return _TARGET_SAMPLES


def _try_numeric(v: object) -> float | None:
    """Return float if v is numeric or a string that parses as a number, else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(v, str):
        s = v.strip().translate(_NUM_COERCE_CHARS)
        if not s:
            return None
        try:
            f = float(s)
            return None if math.isnan(f) or math.isinf(f) else f
        except ValueError:
            return None
    return None


def _profile_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Column-first profiler with lazy deep scan.

    Strategy per column:
      Fast path  — scan first _FAST_SCAN_ROWS rows.
      Deep scan  — if fewer than _SPARSE_THRESHOLD non-empty values found,
                   scan the entire dataset.  Stops once _TARGET_SAMPLES collected.

    This handles columns where data only appears further down the file
    (sparse columns, late-loaded enrichments, etc.).
    """
    if not records:
        return {}

    n_total = len(records)
    fields = list(records[0].keys())
    profile: dict[str, dict[str, Any]] = {}

    for field_name in fields:
        nums: list[float] = []
        strs: list[str] = []
        non_empty_count = 0
        unique_values: set[str] = set()

        def _ingest(
            value: object,
            *,
            unique_values_ref: set[str] = unique_values,
            nums_ref: list[float] = nums,
            strs_ref: list[str] = strs,
        ) -> None:
            nonlocal non_empty_count
            if value is None:
                return
            stripped = str(value).strip() if not isinstance(value, int | float) else None
            if stripped == "":
                return
            non_empty_count += 1
            numeric_value = _try_numeric(value)
            if numeric_value is not None:
                unique_values_ref.add(
                    str(int(numeric_value))
                    if float(numeric_value).is_integer()
                    else str(numeric_value)
                )
            else:
                unique_values_ref.add(stripped if stripped is not None else str(value))
            if len(nums_ref) + len(strs_ref) >= _TARGET_SAMPLES:
                return
            if numeric_value is not None:
                nums_ref.append(numeric_value)
            else:
                strs_ref.append(stripped if stripped is not None else str(value))

        fast_limit = min(_FAST_SCAN_ROWS, n_total)
        for index in range(fast_limit):
            _ingest(records[index].get(field_name))

        if n_total > fast_limit:
            for index in range(fast_limit, n_total):
                _ingest(records[index].get(field_name))

        entry: dict[str, Any] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": len(nums) > len(strs),
            "sample_values": [str(value) for value in nums[:50]] + strs[:50],
            "unique_count": len(unique_values),
            "total_count": non_empty_count,
            "non_empty": non_empty_count,
            "fill_rate": round(non_empty_count / n_total, 4),
        }
        if nums:
            mean = sum(nums) / len(nums)
            entry["mean"] = mean
            entry["std"] = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1))
        profile[field_name] = entry

    return profile


def _profile_records_and_arrow(
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], Any]:
    """
    Build planner profile stats and Arrow columns in one pass over row records.

    The upload/register path previously did two full Python scans after parse:
      1. `_profile_records(records)`
      2. build per-column Arrow arrays for Parquet serialization

    Combining them keeps the same profiling semantics while removing the second
    row-scale walk from hot registration paths.
    """
    import pyarrow as pa

    if not records:
        return {}, pa.table({})

    n_total = len(records)
    fields = list(records[0].keys())

    numeric_samples: dict[str, list[float]] = {field_name: [] for field_name in fields}
    string_samples: dict[str, list[str]] = {field_name: [] for field_name in fields}
    non_empty_counts: dict[str, int] = dict.fromkeys(fields, 0)
    unique_values: dict[str, set[str]] = {field_name: set() for field_name in fields}
    column_values: dict[str, list[Any]] = {field_name: [] for field_name in fields}

    for row in records:
        for field_name in fields:
            value = row.get(field_name)

            if value is None:
                column_values[field_name].append(None)
                continue

            stripped: str | None = None
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.lower() in {"", "?", "none", "null", "nan"}:
                    column_values[field_name].append(None)
                else:
                    column_values[field_name].append(value)
            else:
                column_values[field_name].append(value)

            if stripped == "":
                continue

            non_empty_counts[field_name] += 1

            numeric_value = _try_numeric(value)
            if numeric_value is not None:
                unique_values[field_name].add(
                    str(int(numeric_value))
                    if float(numeric_value).is_integer()
                    else str(numeric_value)
                )
                if (
                    len(numeric_samples[field_name]) + len(string_samples[field_name])
                    < _TARGET_SAMPLES
                ):
                    numeric_samples[field_name].append(numeric_value)
                continue

            string_value = stripped if stripped is not None else str(value)
            unique_values[field_name].add(string_value)
            if len(numeric_samples[field_name]) + len(string_samples[field_name]) < _TARGET_SAMPLES:
                string_samples[field_name].append(string_value)

    profile: dict[str, dict[str, Any]] = {}
    arrays: dict[str, Any] = {}

    for field_name in fields:
        nums = numeric_samples[field_name]
        strs = string_samples[field_name]
        entry: dict[str, Any] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": len(nums) > len(strs),
            "sample_values": [str(value) for value in nums[:50]] + strs[:50],
            "unique_count": len(unique_values[field_name]),
            "total_count": non_empty_counts[field_name],
            "non_empty": non_empty_counts[field_name],
            "fill_rate": round(non_empty_counts[field_name] / n_total, 4),
        }
        if nums:
            mean = sum(nums) / len(nums)
            entry["mean"] = mean
            entry["std"] = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1))
        profile[field_name] = entry

        try:
            arrays[field_name] = pa.array(column_values[field_name])
        except Exception:
            arrays[field_name] = pa.array(
                [str(value) if value is not None else None for value in column_values[field_name]],
                type=pa.string(),
            )

    return profile, pa.table(arrays)


def _profile_arrow_table(table: Any) -> dict[str, dict[str, Any]]:
    import pyarrow as pa
    import pyarrow.compute as pc

    if table is None or getattr(table, "num_rows", 0) == 0:
        return {}

    n_total = int(table.num_rows)
    profile: dict[str, dict[str, Any]] = {}

    def _non_null_count(array: Any) -> int:
        null_count = getattr(array, "null_count", None)
        if isinstance(null_count, int) and null_count >= 0:
            return max(n_total - null_count, 0)
        return int(pc.count(array, mode="only_valid").as_py() or 0)

    def _distinct_count(array: Any) -> int:
        try:
            return int(pc.count_distinct(array, mode="only_valid").as_py() or 0)
        except Exception:
            return len({value for value in array.to_pylist() if value is not None})

    def _sample_non_null_values(array: Any, limit: int) -> list[Any]:
        if limit <= 0:
            return []
        sample_values: list[Any] = []
        chunks = array.iterchunks() if hasattr(array, "iterchunks") else (array,)
        for chunk in chunks:
            valid_chunk = pc.drop_null(chunk)
            if len(valid_chunk) == 0:
                continue
            remaining = limit - len(sample_values)
            sample_values.extend(valid_chunk.slice(0, remaining).to_pylist())
            if len(sample_values) >= limit:
                break
        return sample_values

    def _sample_distinct_non_null_values(array: Any, limit: int) -> list[Any]:
        if limit <= 0:
            return []
        try:
            unique = pc.unique(pc.drop_null(array))
            return [value for value in unique.to_pylist() if value is not None][:limit]
        except Exception:
            seen: set[Any] = set()
            distinct_values: list[Any] = []
            for value in _sample_non_null_values(array, limit * 4):
                if value in seen:
                    continue
                seen.add(value)
                distinct_values.append(value)
                if len(distinct_values) >= limit:
                    break
            return distinct_values

    for field_name in table.column_names:
        column = table[field_name]
        if pa.types.is_dictionary(column.type):
            column = pc.dictionary_decode(column)

        is_numeric = (
            pa.types.is_integer(column.type)
            or pa.types.is_floating(column.type)
            or pa.types.is_decimal(column.type)
        )
        total_count = _non_null_count(column)
        fill_rate = round(total_count / n_total, 4) if n_total else 0.0
        if total_count <= 0:
            unique_count = 0
            sample_values = []
        else:
            unique_count = _distinct_count(column)
            if not is_numeric and 1 < unique_count <= 32:
                sample_values = _sample_distinct_non_null_values(column, _TARGET_SAMPLES)
            else:
                sample_values = _sample_non_null_values(column, _TARGET_SAMPLES)

        nums: list[float] = []
        strs: list[str] = []
        if is_numeric:
            for value in sample_values:
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isnan(numeric_value) and not math.isinf(numeric_value):
                    nums.append(numeric_value)
        else:
            strs = [str(value) for value in sample_values if value is not None]

        entry: dict[str, Any] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": is_numeric,
            "sample_values": [str(value) for value in sample_values[:50]],
            "unique_count": unique_count,
            "total_count": total_count,
            "non_empty": total_count,
            "fill_rate": fill_rate,
        }
        if nums:
            mean = sum(nums) / len(nums)
            entry["mean"] = mean
            entry["std"] = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1))
        profile[field_name] = entry

    return profile


__all__ = (
    "_profile_arrow_table",
    "_profile_records",
    "_profile_records_and_arrow",
    "_relation_detect_sample_limit",
    "_try_numeric",
)
