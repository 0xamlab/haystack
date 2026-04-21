from __future__ import annotations

import base64
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apps.cli.support import prompt_text

ApiRequest = Callable[[str, str, Any | None], tuple[int, dict[str, Any]]]


def maybe_read_file_payload(path: str) -> tuple[str, str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(path)
    suffix = file_path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        return "csv", file_path.read_text()
    if suffix in {".json", ".jsonl"}:
        return "json_str", file_path.read_text()
    if suffix == ".parquet":
        return "parquet_b64", base64.b64encode(file_path.read_bytes()).decode()
    if suffix in {".xlsx", ".xls"}:
        return "excel_b64", base64.b64encode(file_path.read_bytes()).decode()
    raise ValueError(f"Unsupported file type: {suffix}")


def build_connect_request_interactive() -> dict[str, Any]:
    connection_type = prompt_text(
        "Connection type (database/api/object_storage/file_upload)",
        "file_upload",
    ).lower().replace("-", "_")
    dataset_name = prompt_text("Dataset name")
    visibility = prompt_text("Visibility (private/shared)", "private").lower()
    description = prompt_text("Description", "")

    payload: dict[str, Any] = {
        "connection_type": connection_type,
        "dataset_name": dataset_name,
        "visibility": visibility,
    }
    if description:
        payload["description"] = description

    if connection_type == "file_upload":
        source_mode = prompt_text("File source (path/url/inline_csv/inline_json)", "path").lower()
        if source_mode == "url":
            payload["url"] = prompt_text("Data URL")
        elif source_mode == "inline_csv":
            payload["csv"] = prompt_text("CSV text")
        elif source_mode == "inline_json":
            payload["json_str"] = prompt_text("JSON text")
        else:
            file_path = prompt_text("File path")
            field, value = maybe_read_file_payload(file_path)
            payload[field] = value
        return payload

    provider_default = (
        "rest"
        if connection_type == "api"
        else ("s3" if connection_type == "object_storage" else "sqlite")
    )
    provider = prompt_text("Provider", provider_default).lower().replace("-", "_")
    payload["provider"] = provider
    payload["connection_name"] = prompt_text("Connection name", f"{dataset_name} connection")
    config: dict[str, Any] = {}

    if connection_type == "database":
        connection_string = prompt_text("Connection string", "")
        if connection_string:
            config["connection_string"] = connection_string
        elif provider == "sqlite":
            config["path"] = prompt_text("SQLite path")
        else:
            config["host"] = prompt_text("Host", "localhost")
            config["port"] = int(prompt_text("Port", "5432"))
            config["database"] = prompt_text("Database")
            config["user"] = prompt_text("User")
            config["password"] = prompt_text("Password", secret=True)
        selection_mode = prompt_text("Select table or sql_query?", "table")
        if selection_mode == "sql_query":
            payload["selection"] = {"sql_query": prompt_text("SQL query")}
        else:
            payload["selection"] = {"table": prompt_text("Table")}
    elif connection_type == "api":
        config["url"] = prompt_text("API URL")
        auth_type = prompt_text("Auth type (none/bearer/api_key)", "none")
        if auth_type != "none":
            config["auth_type"] = auth_type
            config["api_key"] = prompt_text("API token/key", secret=True)
            if auth_type == "api_key":
                config["api_key_header"] = prompt_text("API key header", "X-API-Key")
        data_path = prompt_text("Data path", "")
        if data_path:
            payload["selection"] = {"url": config["url"], "data_path": data_path}
    elif connection_type == "object_storage":
        if provider == "s3":
            config["bucket"] = prompt_text("Bucket")
            config["region"] = prompt_text("Region", "us-east-1")
            config["access_key_id"] = prompt_text("Access key ID")
            config["secret_access_key"] = prompt_text("Secret access key", secret=True)
        elif provider == "gcs":
            config["bucket"] = prompt_text("Bucket")
            config["project_id"] = prompt_text("Project ID", "")
        else:
            config["connection_string"] = prompt_text("Azure connection string", secret=True)
            config["container"] = prompt_text("Container")
        payload["selection"] = {"object_path": prompt_text("Object path")}
    else:
        raise ValueError(f"Unsupported connection type: {connection_type}")

    payload["connection_config"] = config
    return payload


def print_data_connect_result(
    data: dict[str, Any],
    format: str = "table",
    *,
    rich_enabled: bool,
) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return

    status = data.get("status", "unknown")
    print(f"\nDataset connect status: {status}")
    if status == "needs_selection":
        print(f"Connection ID: {data.get('connection_id')}")
        for idx, choice in enumerate(data.get("choices", []), start=1):
            print(f"  [{idx}] {choice.get('label') or choice.get('id')}")
        return

    print(f"Dataset ID:     {data.get('dataset_id')}")
    print(f"Dataset name:   {data.get('dataset_name')}")
    print(f"Connection ID:  {data.get('connection_id')}")
    print(f"Type/provider:  {data.get('connection_type')} / {data.get('provider')}")
    print(f"Visibility:     {data.get('visibility')}")
    summary = data.get("schema_summary") or {}
    if summary:
        print(f"Rows/columns:   {summary.get('row_count')} / {summary.get('columns')}")
        if summary.get("roles_summary"):
            print(f"Roles:          {summary.get('roles_summary')}")


def cmd_data_connect(
    request_path: str | None = None,
    format: str = "table",
    *,
    api_request: ApiRequest,
    rich_enabled: bool,
) -> None:
    payload = (
        json.loads(Path(request_path).read_text())
        if request_path
        else build_connect_request_interactive()
    )
    status, data = api_request("POST", "/v1/data/connect", payload)
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)

    if data.get("status") == "needs_selection" and not request_path:
        choices = data.get("choices", [])
        if not choices:
            print_data_connect_result(data, format, rich_enabled=rich_enabled)
            return
        choice_raw = prompt_text("Select item number", "1")
        try:
            selected = choices[max(int(choice_raw) - 1, 0)]
        except Exception:
            selected = choices[0]
        payload["connection_id"] = data.get("connection_id")
        payload["selection"] = selected.get("selection")
        payload.pop("connection_config", None)
        status, data = api_request("POST", "/v1/data/connect", payload)
        if status != 200:
            print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
            sys.exit(1)

    print_data_connect_result(data, format, rich_enabled=rich_enabled)


def cmd_data_list(format: str = "table", *, api_request: ApiRequest, rich_enabled: bool) -> None:
    status, data = api_request("GET", "/v1/data")
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    datasets = data.get("datasets", [])
    print(f"\nDatasets ({len(datasets)}):")
    for dataset in datasets:
        print(
            f"  {dataset.get('dataset_id')}  {dataset.get('dataset_name')}  "
            f"[{dataset.get('visibility')}] "
            f"rows={dataset.get('row_count')} cols={dataset.get('columns')}"
        )


def cmd_data_inspect(
    dataset_id: str,
    format: str = "table",
    *,
    api_request: ApiRequest,
    rich_enabled: bool,
) -> None:
    status, data = api_request("GET", f"/v1/data/{dataset_id}")
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    dataset = data.get("dataset", {})
    schema = data.get("schema", {})
    print(f"\nDataset: {dataset.get('dataset_name')} ({dataset.get('dataset_id')})")
    print(f"Visibility: {dataset.get('visibility')}  Refreshable: {dataset.get('refreshable')}")
    print(f"Rows: {schema.get('row_count', dataset.get('row_count'))}")
    columns = schema.get("columns", [])
    if isinstance(columns, list):
        print(f"Columns ({len(columns)}):")
        for col in columns[:30]:
            if isinstance(col, dict):
                print(f"  - {col.get('name')} [{col.get('role')}]")
            else:
                print(f"  - {col}")


def cmd_data_refresh(
    dataset_id: str,
    format: str = "table",
    *,
    api_request: ApiRequest,
    rich_enabled: bool,
) -> None:
    status, data = api_request("POST", f"/v1/data/{dataset_id}/refresh", {})
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    print_data_connect_result(data, format, rich_enabled=rich_enabled)


def cmd_data_disconnect(
    dataset_id: str,
    *,
    assume_yes: bool = False,
    format: str = "table",
    api_request: ApiRequest,
    rich_enabled: bool,
) -> None:
    if not assume_yes:
        confirm = prompt_text(f"Delete dataset {dataset_id}? [y/N]", "n").lower()
        if confirm not in {"y", "yes"}:
            print("Canceled.")
            return
    status, data = api_request("DELETE", f"/v1/data/{dataset_id}")
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(
        f"Deleted dataset {data.get('dataset_id')} "
        f"(connection_deleted={data.get('connection_deleted')})"
    )
