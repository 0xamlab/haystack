from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=8)
def _artifact_cache_dir(configured_dir: str | None = None) -> Path | None:
    env_cache_dir = os.environ.get("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR")
    is_default_path = configured_dir is None and env_cache_dir is None
    cache_dir = Path(configured_dir or env_cache_dir or Path.home() / ".algenta" / "artifact_cache")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        fallback_dir = Path(tempfile.gettempdir()) / "algenta-artifact-cache"
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning(
                "source_artifact_cache_unavailable",
                requested_path=str(cache_dir),
                fallback_path=str(fallback_dir),
                error=str(exc),
            )
            return None
        if is_default_path:
            logger.debug(
                "source_artifact_cache_default_fallback_dir",
                requested_path=str(cache_dir),
                fallback_path=str(fallback_dir),
                error=str(exc),
            )
        else:
            logger.warning(
                "source_artifact_cache_fallback_dir",
                requested_path=str(cache_dir),
                fallback_path=str(fallback_dir),
                error=str(exc),
            )
        return fallback_dir
    return cache_dir


def source_content_artifact_key(src: Any) -> str | None:
    payload_kind = ""
    payload_bytes: bytes | None = None

    if getattr(src, "csv", None):
        payload_kind = "csv"
        payload_bytes = str(src.csv).encode("utf-8")
    elif getattr(src, "json_str", None):
        payload_kind = "json"
        payload_bytes = str(src.json_str).encode("utf-8")
    elif getattr(src, "excel_b64", None):
        payload_kind = "excel"
        try:
            payload_bytes = base64.b64decode(src.excel_b64)
        except (binascii.Error, ValueError):
            return None
    elif getattr(src, "parquet_b64", None):
        payload_kind = "parquet"
        try:
            payload_bytes = base64.b64decode(src.parquet_b64)
        except (binascii.Error, ValueError):
            return None
    elif getattr(src, "records", None) is not None:
        payload_kind = "records"
        payload_bytes = json.dumps(
            src.records,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")

    if not payload_kind or payload_bytes is None:
        return None

    digest = hashlib.sha256()
    digest.update(payload_kind.encode("ascii"))
    digest.update(b"\0")
    digest.update(payload_bytes)
    return digest.hexdigest()[:32]


def _artifact_path(cache_key: str) -> Path | None:
    cache_dir = _artifact_cache_dir(os.environ.get("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR"))
    if cache_dir is None:
        return None
    return cache_dir / f"{cache_key}.parquet"


def load_cached_arrow_table(cache_key: str) -> Any | None:
    path = _artifact_path(cache_key)
    if path is None:
        return None
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq

        initialize_pyarrow_parquet_runtime()
        return pq.read_table(path)
    except Exception as exc:
        logger.warning(
            "source_artifact_cache_load_failed",
            cache_key=cache_key[:8],
            path=str(path),
            error=str(exc),
        )
        return None


def store_cached_arrow_table(cache_key: str, table: Any) -> None:
    path = _artifact_path(cache_key)
    if path is None:
        return
    tmp_path = path.with_suffix(".tmp")
    try:
        import pyarrow.parquet as pq

        initialize_pyarrow_parquet_runtime()
        with tmp_path.open("wb") as handle:
            pq.write_table(table, handle)
        tmp_path.replace(path)
    except Exception as exc:
        logger.warning(
            "source_artifact_cache_store_failed",
            cache_key=cache_key[:8],
            path=str(path),
            error=str(exc),
        )
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            logger.debug(
                "source_artifact_cache_cleanup_failed",
                cache_key=cache_key[:8],
                path=str(tmp_path),
            )
