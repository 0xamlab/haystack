"""
training/semantic/schema_ingestor.py — Universal schema ingestor.

Converts any tabular data source into the schema format expected by the pipeline:
    {"SourceName": [["COL_NAME", "role"], ...], ...}

Accepted inputs (unified via ingest()):
    File paths      CSV, TSV, JSON, JSONL, Excel (.xlsx/.xls), Parquet
    In-memory       dict[str, list]      column_name → values
                    list[dict]           array of records (JSON-style)
                    pandas DataFrame
                    list[str]            column names only (no data)

Column roles (mirrors semantic_types.mojo / build_dataset.py):
    derived_measure   — computed numeric (e.g. net_sales, ext_price)
    base_measure      — raw numeric (e.g. quantity, units)
    unit_measure      — per-unit numeric (e.g. unit_price)
    ratio             — 0–1 float or percentage (e.g. ppa, margin_pct)
    other             — date, dimension, or unclassified

Role inference uses column name heuristics + optional data sampling.
No hard external dependencies — pandas/pyarrow are used only if available.

Usage:
    from training.semantic.schema_ingestor import ingest, suggest_aliases

    # From any source
    schema = ingest("data/sales.csv",  source_name="Sales")
    schema = ingest("data/orders.json", source_name="Orders")
    schema = ingest(df,                 source_name="Transactions")
    schema = ingest({"col": [1,2,3]},   source_name="Raw")
    schema = ingest([{"a": 1}, {"a": 2}], source_name="Records")

    aliases = suggest_aliases(schema)
    # → feed both into run_pipeline(schema, domain_aliases=aliases)

Self-test:
    python3 training/semantic/schema_ingestor.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ── Role vocabulary ───────────────────────────────────────────────────────────

_DATE_TOKENS = {
    "date",
    "time",
    "period",
    "year",
    "month",
    "day",
    "week",
    "quarter",
    "at",
    "on",
    "created",
    "updated",
    "timestamp",
}
_MEASURE_TOKENS = {
    "revenue",
    "sales",
    "cost",
    "price",
    "amount",
    "value",
    "total",
    "sum",
    "net",
    "gross",
    "profit",
    "loss",
    "spend",
    "ext",
    "extended",
    "earned",
    "charged",
    "billed",
    "fee",
    "tax",
    "discount",
    "tips",
    "gratuity",
    "salary",
    "wage",
}
_UNIT_TOKENS = {
    "unit",
    "rate",
    "avg",
    "average",
    "per",
    "each",
    "ppa",
    "apc",
    "aov",
    "rpm",
    "cpm",
    "cpc",
    "ctr",
}
_RATIO_TOKENS = {
    "pct",
    "percent",
    "percentage",
    "ratio",
    "margin",
    "share",
    "fraction",
    "proportion",
    "utilization",
    "fill",
}
_COUNT_TOKENS = {
    "qty",
    "quantity",
    "count",
    "num",
    "number",
    "n",
    "units",
    "items",
    "rows",
    "volume",
    "sold",
    "ordered",
}
_ENTITY_TOKENS = {
    "id",
    "uuid",
    "key",
    "code",
    "ref",
    "number",
    "customer",
    "order",
    "employee",
    "server",
    "user",
    "product",
    "item",
    "sku",
    "invoice",
    "ticket",
    "seat",
    "guest",
    "diner",
    "cover",
}
_DIMENSION_TOKENS = {
    "name",
    "type",
    "status",
    "category",
    "region",
    "segment",
    "channel",
    "brand",
    "location",
    "store",
    "department",
    "division",
    "group",
    "class",
    "label",
    "flag",
    "mode",
    "source",
    "medium",
    "campaign",
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _tokenize_col(col_name: str) -> list[str]:
    """Split column name into lowercase tokens on non-alphanumeric boundaries."""
    return [t for t in re.split(r"[^a-z0-9]+", col_name.lower()) if t]


def _sample_numeric_ratio(samples: list[str]) -> float:
    """Return fraction of non-empty samples that parse as numbers."""
    non_empty = [s for s in samples if isinstance(s, str) and s.strip()]
    if not non_empty:
        return 0.0
    numeric = sum(1 for s in non_empty if re.fullmatch(r"-?\d+(\.\d+)?([eE][+-]?\d+)?", s.strip()))
    return numeric / len(non_empty)


def _samples_to_str(samples: list[Any]) -> list[str]:
    """Normalise mixed-type sample lists to strings for heuristic checks."""
    result = []
    for s in samples:
        if s is None:
            continue
        result.append(str(s))
    return result


def _looks_like_date(samples: list[str]) -> bool:
    date_re = re.compile(
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
        r"|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
        r"|\d{4}-\d{2}-\d{2}T"
    )
    non_empty = [s.strip() for s in samples if s.strip()]
    if not non_empty:
        return False
    return sum(1 for s in non_empty if date_re.search(s)) / len(non_empty) >= 0.6


def _looks_like_ratio(samples: list[str]) -> bool:
    non_empty = [s.strip() for s in samples if s.strip()]
    if not non_empty:
        return False
    try:
        vals = [float(s) for s in non_empty]
    except ValueError:
        return False
    return all(0.0 <= v <= 1.0 for v in vals) and any("." in s for s in non_empty)


# ── Role classification ───────────────────────────────────────────────────────


def _classify_role(col_name: str, samples: list[Any]) -> str:
    """
    Infer column role from name tokens + optional data samples.

    When no samples are provided, classification relies on name tokens alone.
    """
    tokens = set(_tokenize_col(col_name))
    str_samp = _samples_to_str(samples)
    has_data = bool(str_samp)
    num_ratio = _sample_numeric_ratio(str_samp) if has_data else 1.0

    # Date
    if tokens & _DATE_TOKENS:
        return "other"
    if has_data and _looks_like_date(str_samp):
        return "other"

    # Ratio
    if tokens & _RATIO_TOKENS:
        return "ratio"
    if has_data and _looks_like_ratio(str_samp):
        return "ratio"

    # Numeric (or name-only path where we assume numeric)
    if num_ratio >= 0.80:
        if tokens & _UNIT_TOKENS:
            return "unit_measure"
        if tokens & _COUNT_TOKENS:
            return "base_measure"
        if tokens & _MEASURE_TOKENS:
            return "derived_measure"
        if has_data:
            return "base_measure"

    return "other"


# ── Core builder (all paths converge here) ────────────────────────────────────


def _build_schema(
    col_samples: dict[str, list[Any]],
    source_name: str,
) -> dict[str, list[list[str]]]:
    """
    Given {col_name: [sample_values, ...]}, return a schema dict.
    Empty sample lists → name-only classification.
    """
    entries: list[list[str]] = []
    for col_name, samples in col_samples.items():
        col_name = col_name.strip()
        if not col_name:
            continue
        role = _classify_role(col_name, samples)
        entries.append([col_name, role])
    return {source_name: entries}


# ── Format-specific readers ───────────────────────────────────────────────────


def _read_csv(
    path: Path,
    sample_rows: int,
    encoding: str,
    delimiter: str = ",",
) -> dict[str, list[Any]]:
    col_samples: dict[str, list[Any]] = {}
    with open(path, newline="", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            return {}
        for h in headers:
            col_samples[h] = []
        for i, row in enumerate(reader):
            if i >= sample_rows:
                break
            for j, val in enumerate(row):
                if j < len(headers):
                    col_samples[headers[j]].append(val)
    return col_samples


def _read_json_file(path: Path, sample_rows: int) -> dict[str, list[Any]]:
    """
    Read a JSON file.  Handles:
      - Array of records: [{"col": val}, ...]
      - Single object: {"col": val, ...}   (treated as one record)
    """
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        records = raw[:sample_rows]
    elif isinstance(raw, dict):
        # Maybe it's a dict of arrays: {"col": [v1, v2, ...]}
        if all(isinstance(v, list) for v in raw.values()):
            return {k: v[:sample_rows] for k, v in raw.items()}
        records = [raw]
    else:
        raise ValueError(f"Unsupported JSON structure: {type(raw)}")
    return _records_to_col_samples(records)


def _read_jsonl_file(path: Path, sample_rows: int) -> dict[str, list[Any]]:
    records: list[dict] = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(records) >= sample_rows:
                break
    return _records_to_col_samples(records)


def _records_to_col_samples(records: list[dict[str, Any]]) -> dict[str, list[Any]]:
    col_samples: dict[str, list[Any]] = {}
    for record in records:
        for k, v in record.items():
            col_samples.setdefault(str(k), []).append(v)
    return col_samples


def _read_excel(path: Path, sample_rows: int, sheet: str | int = 0) -> dict[str, list[Any]]:
    """Read Excel via pandas (if available) or openpyxl."""
    try:
        import pandas as pd  # type: ignore[import]

        df = pd.read_excel(path, sheet_name=sheet, nrows=sample_rows)
        return {str(c): df[c].dropna().astype(str).tolist()[:sample_rows] for c in df.columns}
    except ImportError:
        pass
    try:
        import openpyxl  # type: ignore[import]

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {}
        headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
        col_samples = {h: [] for h in headers}
        for row in rows[1 : sample_rows + 1]:
            for j, val in enumerate(row):
                if j < len(headers) and val is not None:
                    col_samples[headers[j]].append(val)
        return col_samples
    except ImportError:
        raise ImportError(
            "Reading Excel requires pandas or openpyxl: "
            "pip install pandas  OR  pip install openpyxl"
        ) from None


def _read_parquet(path: Path, sample_rows: int) -> dict[str, list[Any]]:
    """Read Parquet via pyarrow or pandas."""
    try:
        import pyarrow.parquet as pq  # type: ignore[import]

        table = pq.read_table(path)
        df = table.slice(0, sample_rows).to_pandas()
        return {str(c): df[c].dropna().astype(str).tolist() for c in df.columns}
    except ImportError:
        pass
    try:
        import pandas as pd  # type: ignore[import]

        df = pd.read_parquet(path)
        return {str(c): df[c].dropna().astype(str).tolist()[:sample_rows] for c in df.columns}
    except ImportError:
        raise ImportError(
            "Reading Parquet requires pyarrow or pandas: "
            "pip install pyarrow  OR  pip install pandas"
        ) from None


# ── Unified ingest() ──────────────────────────────────────────────────────────


def ingest(
    source: Any,
    source_name: str | None = None,
    sample_rows: int = 200,
    encoding: str = "utf-8-sig",
    sheet: str | int = 0,
) -> dict[str, list[list[str]]]:
    """
    Universal schema ingestor.

    Args:
        source:      Any of:
                       str | Path      — file (CSV, TSV, JSON, JSONL, Excel, Parquet)
                       dict[str, list] — {column_name: [values]}
                       list[dict]      — array of records
                       list[str]       — column names only
                       pandas.DataFrame
        source_name: Label for this data source (default: filename stem or "data").
        sample_rows: Max rows to inspect for type inference.
        encoding:    File encoding (for text formats).
        sheet:       Sheet name or index for Excel files.

    Returns:
        {"SourceName": [["COL_NAME", "role"], ...]}
    """
    # ── pandas DataFrame ──────────────────────────────────────────────────────
    try:
        import pandas as pd  # type: ignore[import]

        if isinstance(source, pd.DataFrame):
            return ingest_dataframe(source, source_name or "data", sample_rows)
    except ImportError:
        pass

    # ── File path ─────────────────────────────────────────────────────────────
    if isinstance(source, str | Path):
        return ingest_file(
            Path(source),
            source_name=source_name,
            sample_rows=sample_rows,
            encoding=encoding,
            sheet=sheet,
        )

    # ── list[dict] — records ──────────────────────────────────────────────────
    if isinstance(source, list):
        if not source:
            return {source_name or "data": []}
        if isinstance(source[0], dict):
            return ingest_records(source, source_name or "data", sample_rows)
        if isinstance(source[0], str):
            return ingest_column_names(source, source_name or "data")
        raise TypeError(f"list elements must be dict or str, got {type(source[0])}")

    # ── dict ──────────────────────────────────────────────────────────────────
    if isinstance(source, dict):
        # {col: [values]} or {col: role_str}
        if all(isinstance(v, list | tuple) or v is None for v in source.values()):
            return ingest_column_data(source, source_name or "data", sample_rows)
        # Treat as {col: role} (pre-classified)
        entries = [[k, v or _classify_role(k, [])] for k, v in source.items()]
        return {source_name or "data": entries}

    raise TypeError(
        f"Unsupported source type: {type(source)}. "
        "Expected: file path, DataFrame, list[dict], list[str], or dict."
    )


# ── Named ingestors (callable directly) ───────────────────────────────────────


def ingest_file(
    path: Path | str,
    source_name: str | None = None,
    sample_rows: int = 200,
    encoding: str = "utf-8-sig",
    sheet: str | int = 0,
) -> dict[str, list[list[str]]]:
    """
    Ingest a file.  Format is detected from the extension:
        .csv                → CSV (comma-separated)
        .tsv / .txt         → TSV (tab-separated)
        .json               → JSON array of records or dict-of-arrays
        .jsonl / .ndjson    → Newline-delimited JSON
        .xlsx / .xls        → Excel (requires pandas or openpyxl)
        .parquet            → Parquet (requires pyarrow or pandas)
    """
    path = Path(path)
    if source_name is None:
        source_name = path.stem

    ext = path.suffix.lower()

    if ext == ".csv":
        col_samples = _read_csv(path, sample_rows, encoding, delimiter=",")
    elif ext in (".tsv", ".txt"):
        col_samples = _read_csv(path, sample_rows, encoding, delimiter="\t")
    elif ext == ".json":
        col_samples = _read_json_file(path, sample_rows)
    elif ext in (".jsonl", ".ndjson"):
        col_samples = _read_jsonl_file(path, sample_rows)
    elif ext in (".xlsx", ".xls"):
        col_samples = _read_excel(path, sample_rows, sheet=sheet)
    elif ext == ".parquet":
        col_samples = _read_parquet(path, sample_rows)
    else:
        # Try CSV as fallback
        col_samples = _read_csv(path, sample_rows, encoding, delimiter=",")

    return _build_schema(col_samples, source_name)


def ingest_records(
    records: list[dict[str, Any]],
    source_name: str = "data",
    sample_rows: int = 200,
) -> dict[str, list[list[str]]]:
    """
    Ingest a list of dicts (JSON-style records).

    Example:
        ingest_records([{"order_date": "2024-01-01", "net_sales": 100.0}, ...])
    """
    col_samples = _records_to_col_samples(records[:sample_rows])
    return _build_schema(col_samples, source_name)


def ingest_dataframe(
    df: Any,  # pandas.DataFrame
    source_name: str = "data",
    sample_rows: int = 200,
) -> dict[str, list[list[str]]]:
    """
    Ingest a pandas DataFrame.

    Example:
        import pandas as pd
        df = pd.read_csv("data.csv")
        schema = ingest_dataframe(df, source_name="Sales")
    """
    col_samples: dict[str, list[Any]] = {}
    sample = df.head(sample_rows)
    for col in sample.columns:
        col_samples[str(col)] = sample[col].dropna().tolist()
    return _build_schema(col_samples, source_name)


def ingest_column_data(
    columns: dict[str, list[Any] | None],
    source_name: str = "data",
    sample_rows: int = 200,
) -> dict[str, list[list[str]]]:
    """
    Ingest a dict of {column_name: [values]} or {column_name: None}.

    Example:
        ingest_column_data({"NET_SALES": [100, 200], "ORDER_DATE": None})
    """
    col_samples = {k: (v[:sample_rows] if v else []) for k, v in columns.items()}
    return _build_schema(col_samples, source_name)


def ingest_column_names(
    names: list[str],
    source_name: str = "data",
) -> dict[str, list[list[str]]]:
    """
    Ingest a bare list of column names (no data — name-only classification).

    Example:
        ingest_column_names(["NET_SALES", "ORDER_DATE", "GUESTS"])
    """
    col_samples = {name: [] for name in names}
    return _build_schema(col_samples, source_name)


# Backwards-compatible aliases
def ingest_csv(
    path: Path | str,
    source_name: str | None = None,
    sample_rows: int = 200,
    encoding: str = "utf-8-sig",
) -> dict[str, list[list[str]]]:
    """Ingest a CSV file (backwards-compatible wrapper around ingest_file)."""
    return ingest_file(path, source_name=source_name, sample_rows=sample_rows, encoding=encoding)


def ingest_columns(
    columns: dict[str, str | None],
    source_name: str = "data",
) -> dict[str, list[list[str]]]:
    """
    Ingest {col_name: role | None} — backwards-compatible.
    None roles are inferred from name tokens.
    """
    entries: list[list[str]] = [[k, v if v else _classify_role(k, [])] for k, v in columns.items()]
    return {source_name: entries}


def merge_schemas(*schemas: dict[str, list]) -> dict[str, list]:
    """Merge multiple schema dicts into one (dedup by column name per source)."""
    merged: dict[str, list] = {}
    for s in schemas:
        for source, entries in s.items():
            if source in merged:
                existing = {e[0] for e in merged[source]}
                merged[source].extend(e for e in entries if e[0] not in existing)
            else:
                merged[source] = list(entries)
    return merged


# ── Alias suggestion ──────────────────────────────────────────────────────────

_KNOWN_ABBREVS = {
    "ppa",
    "apc",
    "aov",
    "qty",
    "ext",
    "net",
    "avg",
    "max",
    "min",
    "num",
    "id",
    "sku",
    "cpm",
    "cpc",
    "ctr",
    "rpm",
}

_AUTO_EXPANSIONS: dict[str, list[str]] = {
    "ppa": ["per", "person", "average"],
    "apc": ["average", "per", "cover"],
    "aov": ["average", "order", "value"],
    "ext": ["extended"],
    "qty": ["quantity"],
    "num": ["number"],
    "avg": ["average"],
    "rev": ["revenue"],
    "sal": ["sales"],
    "cst": ["cost"],
    "prc": ["price"],
    "amt": ["amount"],
    "cnt": ["count"],
    "val": ["value"],
    "arr": ["annual", "recurring", "revenue"],
    "mrr": ["monthly", "recurring", "revenue"],
    "ltv": ["lifetime", "value"],
    "cac": ["customer", "acquisition", "cost"],
    "arpu": ["average", "revenue", "per", "user"],
    "nps": ["net", "promoter", "score"],
}


def suggest_aliases(
    schema: dict[str, list],
    min_expansion_tokens: int = 1,
) -> dict[str, list[str]]:
    """
    Suggest domain alias expansions for opaque abbreviations in the schema.

    Only returns aliases with known expansions.  Tokens that look like
    abbreviations but have no known expansion are silently skipped — call
    suggest_unknown_abbrevs() to get those for manual review.
    """
    aliases: dict[str, list[str]] = {}
    for _src, entries in schema.items():
        for entry in entries:
            col_name = entry[0] if isinstance(entry, list | tuple) else entry
            for tok in _tokenize_col(col_name):
                if tok in aliases:
                    continue
                if tok in _AUTO_EXPANSIONS:
                    exp = _AUTO_EXPANSIONS[tok]
                    if len(exp) >= min_expansion_tokens:
                        aliases[tok] = exp
    return aliases


def suggest_unknown_abbrevs(schema: dict[str, list]) -> list[str]:
    """
    Return short tokens (≤4 chars) that look like abbreviations but have no
    known expansion.  These are candidates for manual alias entries.
    """
    found: list[str] = []
    seen: set[str] = set()
    for _src, entries in schema.items():
        for entry in entries:
            col_name = entry[0] if isinstance(entry, list | tuple) else entry
            for tok in _tokenize_col(col_name):
                if (
                    len(tok) <= 4
                    and tok not in _AUTO_EXPANSIONS
                    and tok not in _KNOWN_ABBREVS
                    and tok not in seen
                ):
                    found.append(tok)
                    seen.add(tok)
    return sorted(found)


# ── Describe ──────────────────────────────────────────────────────────────────


def describe_schema(schema: dict[str, list]) -> str:
    """Return a human-readable summary of a schema."""
    lines = []
    for source, entries in schema.items():
        lines.append(f"[{source}]  {len(entries)} columns")
        by_role: dict[str, list[str]] = {}
        for e in entries:
            col = e[0] if isinstance(e, list | tuple) else e
            role = e[1] if isinstance(e, list | tuple) and len(e) > 1 else "other"
            by_role.setdefault(role, []).append(col)
        for role, cols in sorted(by_role.items()):
            preview = ", ".join(cols[:8]) + (f" … +{len(cols) - 8}" if len(cols) > 8 else "")
            lines.append(f"  {role:<18} {preview}")
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Ingest any data source as schema")
    parser.add_argument(
        "source", nargs="?", default=None, help="File to ingest (CSV/TSV/JSON/JSONL/Excel/Parquet)"
    )
    parser.add_argument("--source-name", type=str, default=None)
    parser.add_argument("--out", type=Path, default=None, help="Write schema JSON")
    parser.add_argument("--aliases-out", type=Path, default=None, help="Write aliases JSON")
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    if not args.source:
        parser.error("source file required (or --self-test)")

    schema = ingest(args.source, source_name=args.source_name, sample_rows=args.sample)
    aliases = suggest_aliases(schema)
    unknown = suggest_unknown_abbrevs(schema)

    print(describe_schema(schema))

    if aliases:
        print("\nSuggested aliases (auto):")
        for k, v in aliases.items():
            print(f"  {k!r:12} → {v}")
    if unknown:
        print(f"\nUnknown abbreviations (manual review needed): {unknown}")

    if args.out:
        args.out.write_text(json.dumps(schema, indent=2))
        print(f"\nSchema → {args.out}")
    if args.aliases_out and aliases:
        args.aliases_out.write_text(json.dumps(aliases, indent=2))
        print(f"Aliases → {args.aliases_out}")


def _run_self_test():
    import tempfile

    # ── Test 1: ingest() from column names list ───────────────────────────────
    print("── Test 1: ingest(list[str])")
    schema = ingest(
        ["NET_SALES", "UNIT_PRICE", "QTY", "ORDER_DATE", "CUSTOMER_NAME"], source_name="POS"
    )
    entries = {e[0]: e[1] for e in schema["POS"]}
    assert entries["NET_SALES"] == "derived_measure", entries["NET_SALES"]
    assert entries["UNIT_PRICE"] == "unit_measure", entries["UNIT_PRICE"]
    assert entries["QTY"] == "base_measure", entries["QTY"]
    assert entries["ORDER_DATE"] == "other", entries["ORDER_DATE"]
    assert entries["CUSTOMER_NAME"] == "other", entries["CUSTOMER_NAME"]
    print("   PASSED")

    # ── Test 2: ingest() from dict of column data ─────────────────────────────
    print("── Test 2: ingest(dict[str, list])")
    schema2 = ingest(
        {
            "net_sales": [100.0, 200.0, 150.0],
            "order_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "customer": ["Alice", "Bob", "Carol"],
        },
        source_name="Orders",
    )
    e2 = {e[0]: e[1] for e in schema2["Orders"]}
    assert e2["net_sales"] in ("derived_measure", "base_measure"), e2["net_sales"]
    assert e2["order_date"] == "other", e2["order_date"]
    assert e2["customer"] == "other", e2["customer"]
    print("   PASSED")

    # ── Test 3: ingest() from list[dict] records ──────────────────────────────
    print("── Test 3: ingest(list[dict])")
    records = [
        {"product": "Widget", "quantity": 5, "unit_price": 9.99, "date": "2024-01-01"},
        {"product": "Gadget", "quantity": 2, "unit_price": 19.99, "date": "2024-01-02"},
    ]
    schema3 = ingest(records, source_name="Sales")
    e3 = {e[0]: e[1] for e in schema3["Sales"]}
    assert e3["unit_price"] == "unit_measure", e3["unit_price"]
    assert e3["date"] == "other", e3["date"]
    print("   PASSED")

    # ── Test 4: ingest() CSV file ─────────────────────────────────────────────
    print("── Test 4: ingest(csv path)")
    csv_content = "order_date,unit_price,quantity,net_sales,customer_name\n"
    csv_content += "2024-01-01,12.50,3,37.50,Alice\n2024-01-02,9.99,1,9.99,Bob\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        tmp_csv = Path(f.name)
    try:
        schema4 = ingest(tmp_csv, source_name="CSV")
        e4 = {e[0]: e[1] for e in schema4["CSV"]}
        assert e4["order_date"] == "other", e4["order_date"]
        assert e4["unit_price"] == "unit_measure", e4["unit_price"]
        print("   PASSED")
    finally:
        tmp_csv.unlink()

    # ── Test 5: ingest() JSON file ────────────────────────────────────────────
    print("── Test 5: ingest(json path)")
    json_records = [{"revenue": 100, "region": "West", "date": "2024-01"} for _ in range(5)]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(json_records, f)
        tmp_json = Path(f.name)
    try:
        schema5 = ingest(tmp_json, source_name="JSON")
        e5 = {e[0]: e[1] for e in schema5["JSON"]}
        assert e5["revenue"] in ("derived_measure", "base_measure"), e5["revenue"]
        assert e5["region"] == "other", e5["region"]
        print("   PASSED")
    finally:
        tmp_json.unlink()

    # ── Test 6: ingest() JSONL file ───────────────────────────────────────────
    print("── Test 6: ingest(jsonl path)")
    jsonl_lines = "\n".join(json.dumps({"qty": i, "name": f"item{i}"}) for i in range(5))
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(jsonl_lines)
        tmp_jsonl = Path(f.name)
    try:
        schema6 = ingest(tmp_jsonl, source_name="JSONL")
        e6 = {e[0]: e[1] for e in schema6["JSONL"]}
        assert e6["qty"] in ("base_measure", "unit_measure"), e6["qty"]
        assert e6["name"] == "other", e6["name"]
        print("   PASSED")
    finally:
        tmp_jsonl.unlink()

    # ── Test 7: suggest_aliases ───────────────────────────────────────────────
    print("── Test 7: suggest_aliases + suggest_unknown_abbrevs")
    schema7 = ingest(["PPA", "NET_SALES", "QTY", "EXT_PRICE"], source_name="T")
    aliases = suggest_aliases(schema7)
    unknown = suggest_unknown_abbrevs(schema7)
    assert "ppa" in aliases, f"ppa not in aliases: {aliases}"
    assert "qty" in aliases, f"qty not in aliases: {aliases}"
    assert aliases["ppa"] == ["per", "person", "average"]
    print(f"   PASSED  aliases={list(aliases.keys())}  unknown={unknown}")

    # ── Test 8: pandas DataFrame (skip if not installed) ─────────────────────
    print("── Test 8: ingest(DataFrame)")
    try:
        import pandas as pd

        df = pd.DataFrame(
            {
                "revenue": [100.0, 200.0],
                "order_date": ["2024-01-01", "2024-01-02"],
                "status": ["open", "closed"],
            }
        )
        schema8 = ingest(df, source_name="DF")
        e8 = {e[0]: e[1] for e in schema8["DF"]}
        assert e8["revenue"] in ("derived_measure", "base_measure"), e8["revenue"]
        assert e8["order_date"] == "other", e8["order_date"]
        print("   PASSED")
    except ImportError:
        print("   SKIPPED (pandas not installed)")

    # ── Test 9: merge_schemas ─────────────────────────────────────────────────
    print("── Test 9: merge_schemas")
    s1 = ingest(["NET_SALES", "ORDER_DATE"], source_name="POS")
    s2 = ingest(["GUESTS", "PPA"], source_name="Totals")
    merged = merge_schemas(s1, s2)
    assert "POS" in merged and "Totals" in merged
    print("   PASSED")

    print("\nSelf-test PASSED  (9/9 subtests)")


if __name__ == "__main__":
    main()
