"""
services/dataset_service.py — Dataset lifecycle manager.

Bridges the onboarding flow (schema_ingestor → schema_registry) to the API layer.

Per-org dataset manifests are persisted at:
    ~/.decision-engine/datasets/<org_id>/<dataset_id>.json

Each manifest holds:
    dataset_id, schema_hash, name, schema, domain_aliases, status, model_tier

The semantic model lifecycle (training, 3-tier resolution) is fully delegated
to SchemaRegistry — this layer only handles dataset identity and metadata.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure project root is importable when running outside the API server context
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from training.semantic.schema_ingestor import ingest, suggest_aliases

_LOCK = threading.Lock()


def _schema_registry():
    from training.semantic.schema_registry import SchemaRegistry

    return SchemaRegistry()


def decision_mode_for_tier(model_tier: str) -> str:
    mapping = {
        "none": "deterministic_only",
        "base": "base_model_assisted",
        "schema": "schema_model_assisted",
    }
    return mapping.get(str(model_tier or "").strip().lower(), "deterministic_only")


def _raw_hash(source: Any) -> str | None:
    """
    Compute a cheap hash of the raw input BEFORE ingestion.
    Used to short-circuit re-ingestion of identical data.
    Returns None if the source type can't be cheaply hashed (e.g. file path).
    """
    try:
        if isinstance(source, list):
            raw = json.dumps(source, sort_keys=True, default=str)
        elif isinstance(source, dict):
            raw = json.dumps(source, sort_keys=True, default=str)
        elif isinstance(source, str) and not Path(source).exists():
            # treat as column-names list serialized
            raw = source
        else:
            return None  # file paths — skip (would require reading the file)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    except Exception:
        return None


def _find_by_raw_hash(org_id: str, raw_hash: str) -> str | None:
    """Return existing dataset_id for a raw-input hash, or None."""
    for m in _list_manifests(org_id):
        if m.get("raw_hash") == raw_hash:
            return m["dataset_id"]
    return None


# ── Filesystem helpers ────────────────────────────────────────────────────────

def _datasets_dir(org_id: str) -> Path:
    p = Path.home() / ".decision-engine" / "datasets" / org_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _manifest_path(org_id: str, dataset_id: str) -> Path:
    return _datasets_dir(org_id) / f"{dataset_id}.json"


def _load_manifest(org_id: str, dataset_id: str) -> dict[str, Any] | None:
    p = _manifest_path(org_id, dataset_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _save_manifest(org_id: str, dataset_id: str, manifest: dict[str, Any]) -> None:
    _manifest_path(org_id, dataset_id).write_text(
        json.dumps(manifest, indent=2, default=str)
    )


def _list_manifests(org_id: str) -> list[dict[str, Any]]:
    d = _datasets_dir(org_id)
    result = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            result.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return result


def _find_by_hash(org_id: str, schema_hash: str) -> str | None:
    """Return existing dataset_id for a schema hash, or None."""
    for m in _list_manifests(org_id):
        if m.get("schema_hash") == schema_hash:
            return m["dataset_id"]
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def onboard(
    org_id:         str,
    source:         Any,
    *,
    name:           str | None = None,
    source_name:    str | None = None,
    domain_aliases: dict[str, list[str]] | None = None,
    async_train:    bool = True,
    epochs:         int = 80,
    batch_size:     int = 32,
) -> dict[str, Any]:
    """
    Profile a data source, register schema, and optionally fire async training.

    Returns the dataset manifest dict with keys:
        dataset_id, name, schema_hash, status, model_tier,
        schema, domain_aliases, source_names, column_count,
        registered_at, updated_at
    """
    # ── Fast path: raw-hash dedup (skip ingestion for identical data) ─────────
    rh = _raw_hash(source)
    if rh is not None:
        with _LOCK:
            existing_id = _find_by_raw_hash(org_id, rh)
            if existing_id is not None:
                manifest = _load_manifest(org_id, existing_id)
                if manifest is not None:
                    # Still probe live model tier — training may have completed
                    reg = _schema_registry()
                    schema = manifest.get("schema", {})
                    da = manifest.get("domain_aliases")
                    manifest["status"] = reg.status(schema, da)
                    _art_dir, tier = reg.resolve(schema, da)
                    manifest["model_tier"] = tier
                    return manifest

    reg = _schema_registry()

    # ── Full ingestion path ────────────────────────────────────────────────────
    effective_source_name = source_name or name or "dataset"
    schema = ingest(source, source_name=effective_source_name)

    # Auto-suggest aliases when caller doesn't override
    if domain_aliases is None:
        auto = suggest_aliases(schema)
        domain_aliases = auto if auto else None

    # Register with SchemaRegistry — fires async training if needed
    entry = reg.register(
        schema,
        domain_aliases=domain_aliases,
        epochs=epochs,
        batch_size=batch_size,
        train=async_train,
    )
    schema_hash = entry["schema_hash"]

    # Resolve current model tier (non-blocking — uses whatever is ready)
    _art_dir, tier = reg.resolve(schema, domain_aliases)

    with _LOCK:
        # Reuse existing dataset_id if this org already has this schema
        dataset_id = _find_by_hash(org_id, schema_hash)
        if dataset_id is None:
            dataset_id = f"ds_{uuid.uuid4().hex[:12]}"

        manifest: dict[str, Any] = {
            "dataset_id":    dataset_id,
            "org_id":        org_id,
            "name":          name or effective_source_name,
            "schema_hash":   schema_hash,
            "raw_hash":      rh,              # stored for future fast-path lookups
            "status":        entry["status"],
            "model_tier":    tier,
            "schema":        schema,
            "domain_aliases": domain_aliases,
            "source_names":  entry.get("source_names", []),
            "column_count":  entry.get("column_count", 0),
            "registered_at": entry.get("registered_at"),
            "updated_at":    datetime.now(UTC).isoformat(),
        }
        _save_manifest(org_id, dataset_id, manifest)

    return manifest


def get_status(org_id: str, dataset_id: str) -> dict[str, Any] | None:
    """
    Return current status for a dataset with live-probed model tier.

    Returns None if dataset_id is not found for this org.
    """
    manifest = _load_manifest(org_id, dataset_id)
    if manifest is None:
        return None

    reg = _schema_registry()
    schema         = manifest.get("schema", {})
    domain_aliases = manifest.get("domain_aliases")

    manifest["status"]     = reg.status(schema, domain_aliases)
    _art_dir, tier         = reg.resolve(schema, domain_aliases)
    manifest["model_tier"] = tier
    return manifest


def retrain(
    org_id:     str,
    dataset_id: str,
    epochs:     int = 80,
    batch_size: int = 32,
) -> dict[str, Any] | None:
    """
    Re-trigger semantic training for an existing dataset.

    Returns the updated manifest, or None if dataset_id not found.
    """
    manifest = _load_manifest(org_id, dataset_id)
    if manifest is None:
        return None

    reg            = _schema_registry()
    schema         = manifest.get("schema", {})
    domain_aliases = manifest.get("domain_aliases")

    entry = reg.register(
        schema,
        domain_aliases=domain_aliases,
        epochs=epochs,
        batch_size=batch_size,
        train=True,
    )

    with _LOCK:
        manifest["status"]     = entry["status"]
        manifest["updated_at"] = datetime.now(UTC).isoformat()
        _save_manifest(org_id, dataset_id, manifest)

    return manifest


def list_datasets(org_id: str) -> list[dict[str, Any]]:
    """Return all datasets for an org with live-probed status and tier."""
    reg = _schema_registry()
    result = []
    for manifest in _list_manifests(org_id):
        schema         = manifest.get("schema", {})
        domain_aliases = manifest.get("domain_aliases")
        m              = dict(manifest)
        m["status"]     = reg.status(schema, domain_aliases)
        _art_dir, tier  = reg.resolve(schema, domain_aliases)
        m["model_tier"] = tier
        result.append(m)
    return result
