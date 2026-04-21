"""
routers/datasets.py — Dataset onboarding and lifecycle.

POST /v1/datasets/onboard          — profile + register any inline data
POST /v1/datasets/onboard/file     — file upload (CSV/JSON/JSONL/Excel/Parquet)
GET  /v1/datasets                  — list all datasets for this org
GET  /v1/datasets/{dataset_id}/status — live status + model tier
POST /v1/datasets/{dataset_id}/retrain — re-trigger semantic training

Design:
    Queries work immediately via deterministic / base-model fallback.
    Background semantic training automatically improves accuracy once complete.
    No user action required after onboarding.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services import dataset_service as ds
from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Datasets"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class OnboardRequest(BaseModel):
    """
    Register any data source for semantic querying.

    Provide data via ONE of:
      records  — list of row dicts (JSON records)
      csv      — raw CSV text (headers in first row)
      columns  — list of column name strings (schema-only, no samples)

    For file uploads use POST /v1/datasets/onboard/file.
    """
    name: str = Field("dataset", description="Human-readable dataset name")
    source_name: str | None = Field(None, description="Table name used in the schema")
    records: list[dict[str, Any]] | None = Field(
        None,
        description="JSON records (list of row dicts)",
    )
    csv: str | None = Field(None, description="Raw CSV text with header row")
    columns: list[str] | None = Field(
        None,
        description="Column names only — no data required",
    )
    domain_aliases: dict[str, list[str]] | None = Field(
        None,
        description="Manual alias map. Auto-suggested from column names when omitted.",
    )
    async_train: bool = Field(True, description="Fire background semantic training immediately")
    epochs: int = Field(80, ge=5, le=500)
    batch_size: int = Field(32, ge=8, le=256)


class DatasetStatusResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    dataset_id:     str
    name:           str
    schema_hash:    str
    status:         str           # "untrained" | "training" | "ready" | "failed"
    model_tier:     str           # "schema" | "base" | "none"
    decision_mode:  str
    source_names:   list[str]
    column_count:   int
    domain_aliases: dict[str, list[str]] | None
    registered_at:  str | None
    updated_at:     str | None


class OnboardResponse(DatasetStatusResponse):
    dataset_schema:    dict[str, Any] = Field(alias="schema")
    suggested_aliases: dict[str, list[str]]
    latency_ms:        float

    model_config = {"populate_by_name": True}


# ── JSON-body onboarding ──────────────────────────────────────────────────────

@router.post(
    "/v1/datasets/onboard",
    response_model=OnboardResponse,
    summary="Onboard a dataset — zero-config schema profiling + auto-training",
    description=(
        "**Drop in data → instantly queryable.**\n\n"
        "- Accepts JSON records, inline CSV, or column names only\n"
        "- Profiles schema and role-classifies every column automatically\n"
        "- Auto-suggests domain aliases (PPA → per/person/average, etc.)\n"
        "- Fires background semantic training immediately\n"
        "- Returns model tier — queries work immediately via base/deterministic fallback\n\n"
        "For file uploads (CSV, Excel, Parquet, JSON) use `POST /v1/datasets/onboard/file`."
    ),
)
async def onboard_dataset(
    payload: OnboardRequest,
    auth:    AuthContext = Depends(get_current_org),
) -> OnboardResponse:
    t0     = time.monotonic()
    org_id = str(auth["org_id"])

    # Resolve source from request fields
    if payload.records is not None:
        source: Any = payload.records
    elif payload.csv is not None:
        source = _parse_csv_text(payload.csv)
    elif payload.columns is not None:
        source = payload.columns
    else:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "no_data",
                              "message": "Provide one of: records, csv, or columns"}},
        )

    return await _run_onboard(
        org_id=org_id,
        source=source,
        name=payload.name,
        source_name=payload.source_name,
        domain_aliases=payload.domain_aliases,
        async_train=payload.async_train,
        epochs=payload.epochs,
        batch_size=payload.batch_size,
        t0=t0,
        log_extra={},
    )


# ── File-upload onboarding ────────────────────────────────────────────────────

@router.post(
    "/v1/datasets/onboard/file",
    response_model=OnboardResponse,
    summary="Onboard from file upload — CSV, Excel, Parquet, JSON, JSONL",
)
async def onboard_file(
    file:               UploadFile = File(...),
    name:               str        = Form("dataset"),
    source_name:        str | None = Form(None),
    domain_aliases_json: str | None = Form(None, alias="domain_aliases"),
    async_train:        bool = Form(True),
    epochs:             int  = Form(80),
    batch_size:         int  = Form(32),
    auth: AuthContext = Depends(get_current_org),
) -> OnboardResponse:
    t0     = time.monotonic()
    org_id = str(auth["org_id"])

    # Parse optional JSON-encoded domain_aliases form field
    domain_aliases: dict[str, list[str]] | None = None
    if domain_aliases_json:
        import json as _json
        try:
            domain_aliases = _json.loads(domain_aliases_json)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "invalid_aliases",
                                  "message": "domain_aliases must be valid JSON"}},
            ) from exc

    # Write upload to a temp file with the original extension
    suffix  = Path(file.filename or "upload.csv").suffix or ".csv"
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        return await _run_onboard(
            org_id=org_id,
            source=tmp_path,
            name=name,
            source_name=source_name or Path(file.filename or name).stem,
            domain_aliases=domain_aliases,
            async_train=async_train,
            epochs=epochs,
            batch_size=batch_size,
            t0=t0,
            log_extra={"filename": file.filename},
        )
    finally:
        os.unlink(tmp_path)


# ── Status ────────────────────────────────────────────────────────────────────

@router.get(
    "/v1/datasets/{dataset_id}/status",
    response_model=DatasetStatusResponse,
    summary="Live status and model tier for a dataset",
)
async def get_dataset_status(
    dataset_id: str,
    auth:       AuthContext = Depends(get_current_org),
) -> DatasetStatusResponse:
    org_id   = str(auth["org_id"])
    manifest = ds.get_status(org_id, dataset_id)
    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found",
                              "message": f"Dataset '{dataset_id}' not found"}},
        )
    return DatasetStatusResponse(
        dataset_id    = manifest["dataset_id"],
        name          = manifest["name"],
        schema_hash   = manifest["schema_hash"],
        status        = manifest["status"],
        model_tier    = manifest["model_tier"],
        decision_mode = ds.decision_mode_for_tier(manifest["model_tier"]),
        source_names  = manifest.get("source_names", []),
        column_count  = manifest.get("column_count", 0),
        domain_aliases = manifest.get("domain_aliases"),
        registered_at = manifest.get("registered_at"),
        updated_at    = manifest.get("updated_at"),
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get(
    "/v1/datasets",
    summary="List all datasets registered for this org",
)
async def list_datasets(
    auth: AuthContext = Depends(get_current_org),
    page: int = Query(default=1, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> dict:
    org_id   = str(auth["org_id"])
    datasets = ds.list_datasets(org_id)
    paged = paginate_sequence(datasets, page=page, limit=limit)
    return {
        "datasets": [
            {
                "dataset_id":    d["dataset_id"],
                "name":          d["name"],
                "schema_hash":   d["schema_hash"],
                "status":        d["status"],
                "model_tier":    d["model_tier"],
                "decision_mode": ds.decision_mode_for_tier(d["model_tier"]),
                "column_count":  d.get("column_count", 0),
                "source_names":  d.get("source_names", []),
                "registered_at": d.get("registered_at"),
            }
            for d in paged.items
        ],
        "count": len(paged.items),
        "total": paged.total,
        "page": paged.page,
        "limit": paged.limit,
        "pages": paged.pages,
    }


# ── Retrain ───────────────────────────────────────────────────────────────────

@router.post(
    "/v1/datasets/{dataset_id}/retrain",
    summary="Re-trigger semantic training for a dataset",
)
async def retrain_dataset(
    dataset_id: str,
    epochs:     int = 80,
    batch_size: int = 32,
    auth:       AuthContext = Depends(get_current_org),
) -> dict:
    org_id   = str(auth["org_id"])
    manifest = ds.retrain(org_id, dataset_id, epochs=epochs, batch_size=batch_size)
    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found",
                              "message": f"Dataset '{dataset_id}' not found"}},
        )
    return {
        "dataset_id":  manifest["dataset_id"],
        "schema_hash": manifest["schema_hash"],
        "status":      manifest["status"],
        "message":     "Retraining triggered in background",
    }


# ── Shared onboard runner ─────────────────────────────────────────────────────

async def _run_onboard(
    *,
    org_id:         str,
    source:         Any,
    name:           str,
    source_name:    str | None,
    domain_aliases: dict[str, list[str]] | None,
    async_train:    bool,
    epochs:         int,
    batch_size:     int,
    t0:             float,
    log_extra:      dict,
) -> OnboardResponse:
    from training.semantic.schema_ingestor import suggest_aliases as _suggest

    try:
        manifest = ds.onboard(
            org_id=org_id,
            source=source,
            name=name,
            source_name=source_name,
            domain_aliases=domain_aliases,
            async_train=async_train,
            epochs=epochs,
            batch_size=batch_size,
        )
    except Exception as exc:
        logger.warning("dataset_onboard_failed", org=org_id, error=str(exc), **log_extra)
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "onboard_failed", "message": str(exc)}},
        ) from exc

    suggested  = _suggest(manifest["schema"])
    elapsed    = round((time.monotonic() - t0) * 1000, 1)

    logger.info(
        "dataset_onboarded",
        org=org_id,
        dataset_id=manifest["dataset_id"],
        schema_hash=manifest["schema_hash"],
        status=manifest["status"],
        tier=manifest["model_tier"],
        latency_ms=elapsed,
        **log_extra,
    )

    return OnboardResponse(
        dataset_id    = manifest["dataset_id"],
        name          = manifest["name"],
        schema_hash   = manifest["schema_hash"],
        status        = manifest["status"],
        model_tier    = manifest["model_tier"],
        decision_mode = ds.decision_mode_for_tier(manifest["model_tier"]),
        source_names  = manifest.get("source_names", []),
        column_count  = manifest.get("column_count", 0),
        domain_aliases = manifest.get("domain_aliases"),
        registered_at = manifest.get("registered_at"),
        updated_at    = manifest.get("updated_at"),
        dataset_schema = manifest["schema"],
        suggested_aliases = suggested,
        latency_ms    = elapsed,
    )


# ── CSV helper ────────────────────────────────────────────────────────────────

def _parse_csv_text(csv_text: str) -> list[dict[str, Any]]:
    """Parse raw CSV text into a list of record dicts with numeric coercion."""
    reader  = csv.DictReader(io.StringIO(csv_text.strip()))
    records: list[dict[str, Any]] = []
    for row in reader:
        record: dict[str, Any] = {}
        for k, v in row.items():
            v_s = (v or "").strip()
            try:
                record[k] = int(v_s)
            except ValueError:
                try:
                    record[k] = float(v_s.replace(",", "").lstrip("$£€¥"))
                except ValueError:
                    record[k] = v_s
        records.append(record)
    return records
