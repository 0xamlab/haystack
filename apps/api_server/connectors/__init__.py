"""
Universal Connector System — plugin-based data source integration.

Every connector normalizes its source to list[dict[str, Any]] — the same
internal table format used by the mapping and query engines.

Supported sources:
  file       → CSV, TSV, JSON (nested + flat), Excel, Parquet (base64 or path)
  sql        → PostgreSQL, MySQL, SQLite, any SQLAlchemy-compatible async DSN
  rest_api   → REST APIs with dot-path navigation + JSON auto-flattening
  s3         → AWS S3 / S3-compatible (MinIO, Wasabi, R2) via aiobotocore or boto3 fallback
  gcs        → Google Cloud Storage via google-cloud-storage
  azure_blob → Azure Blob Storage via azure-storage-blob

Each connector implements:
  fetch_data()          → list[dict] — all records
  validate_connection() → (bool, str) — connectivity test
  map_to_simulation()   → dict — simulation payload (inherited from BaseConnector)
"""
from .base import BaseConnector, ConnectorRegistry
from .cloud_connector import AzureBlobConnector, GCSConnector, S3Connector
from .file_connector import FileConnector, _flatten_dict
from .rest_connector import RESTConnector
from .sql_connector import SQLConnector

__all__ = [
    "BaseConnector",
    "ConnectorRegistry",
    "FileConnector",
    "SQLConnector",
    "RESTConnector",
    "S3Connector",
    "GCSConnector",
    "AzureBlobConnector",
    "_flatten_dict",
]
