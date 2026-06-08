"""
apps/api_server/services/auto_planner.py — Fully-autonomous query planner.

Given only natural-language hints ("revenue", "product line") the planner:
  1. Discovers local tabular sources in a directory (CSV / Parquet)
  2. Profiles each source with the Mojo column_profile + relation_detect engines
  3. Resolves the best metric column using field_map → column_match Mojo pipeline
  4. Resolves the best dimension column using resolve_group_column_graph
  5. Discovers join keys using the Mojo join_detect engine
  6. Returns a QueryPlan with zero hardcoded column / source names

No human intervention required — the planner is fully data-driven.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

import structlog

from apps.api_server.compute.mojo_adapter import invoke_engine_sync
from apps.api_server.services.auto_planner_artifacts import (
    _REGISTRY_SOURCE_ARTIFACT_CACHE,
    _CachedRegistrySourceArtifacts,
    _discover_local_source_map,
    _load_records,
    _profile_records,
    _profiles_from_registry_meta,
)
from apps.api_server.services.auto_planner_artifacts import (
    _registry_source_artifacts_from_meta as _registry_source_artifacts_from_meta_impl,
)
from apps.api_server.services.auto_planner_knowledge import _build_registry_join_cache
from apps.api_server.services.auto_planner_knowledge import (
    refresh_registry_source as _refresh_registry_source_impl,
)
from apps.api_server.services.auto_planner_knowledge_mixin import (
    AutoPlannerKnowledgeMixin,
)
from apps.api_server.services.auto_planner_mojo import (
    call_planner_mojo as _call_planner_mojo_impl,
)
from apps.api_server.services.auto_planner_mojo import (
    find_mojo_binary as _find_mojo_binary_impl,
)
from apps.api_server.services.auto_planner_mojo import (
    should_use_resident_planner_mojo as _should_use_resident_planner_mojo_impl,
)
from apps.api_server.services.auto_planner_plan_mixin import AutoPlannerPlanMixin
from apps.api_server.services.auto_planner_resolution_mixin import (
    AutoPlannerResolutionMixin,
)
from apps.api_server.services.auto_planner_types import (
    AdaptiveSourceContext,
    JoinHop,
    QueryPlan,
)
from apps.api_server.services.mojo_column_rank_resolver import invoke_planner_mojo

logger = structlog.get_logger(__name__)

__all__ = (
    "AdaptiveSourceContext",
    "AutoPlanner",
    "JoinHop",
    "QueryPlan",
    "_profile_records",
    "_registry_source_artifacts_from_meta",
    "_should_use_resident_planner_mojo",
)

_CACHE_VERSION = 2
_MOJO_COLUMN_RANK_MODE = os.environ.get("ALGENTA_MOJO_COLUMN_RANK_MODE", "auto").lower()
_PLANNER_MOJO_TRANSPORT = os.environ.get("ALGENTA_PLANNER_MOJO_TRANSPORT", "auto").lower()
_PLANNER_MOJO_RESIDENT_ENGINES = frozenset({"field_map", "relation_detect", "string_similarity"})
_PLANNER_MOJO_SHARED_ENGINES = frozenset(
    {
        "column_profile",
        "relation_detect",
        "field_map",
        "column_match",
        "join_detect",
        "string_similarity",
        "monte_carlo",
    }
)
_PLANNER_MOJO_MAX_RESIDENT_PAYLOAD_BYTES = int(
    os.environ.get("ALGENTA_PLANNER_MOJO_MAX_RESIDENT_PAYLOAD_BYTES", "8192"),
)
_COMPAT_TEST_EXPORTS = (
    _REGISTRY_SOURCE_ARTIFACT_CACHE,
    _discover_local_source_map,
    _load_records,
    _profile_records,
)


def _should_use_resident_planner_mojo(engine_type: str, payload: dict[str, Any]) -> bool:
    return _should_use_resident_planner_mojo_impl(
        engine_type=engine_type,
        payload=payload,
        resident_engines=_PLANNER_MOJO_RESIDENT_ENGINES,
        max_payload_bytes=_PLANNER_MOJO_MAX_RESIDENT_PAYLOAD_BYTES,
    )


def _registry_source_artifacts_from_meta(
    *,
    org_id: str,
    source_id: str,
    schema_revision: str,
    meta: dict[str, Any],
) -> _CachedRegistrySourceArtifacts:
    return _registry_source_artifacts_from_meta_impl(
        org_id=org_id,
        source_id=source_id,
        schema_revision=schema_revision,
        meta=meta,
        profiles_from_registry_meta_fn=_profiles_from_registry_meta,
    )


# ── AutoPlanner ────────────────────────────────────────────────────────────────


class AutoPlanner(
    AutoPlannerKnowledgeMixin,
    AutoPlannerResolutionMixin,
    AutoPlannerPlanMixin,
):
    """
    Zero-config autonomous query planner.

    Usage:
        planner = AutoPlanner(data_dir=Path("test_files"))
        planner.build_knowledge()
        plan = planner.plan("revenue", "product line", agg="sum")
        result, row_count, trace = planner.execute_plan(plan)
    """

    def __init__(
        self,
        data_dir: Path,
        max_rows: int = 3000,
        mojo_binary: Path | None = None,
        join_min_confidence: float = 0.40,
        llm_policy: str = "never",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.max_rows = max_rows
        self._mojo_binary = mojo_binary or self._find_mojo()
        self._join_min_conf = join_min_confidence
        self._llm_policy = llm_policy
        self._cache_version = _CACHE_VERSION
        self._mojo_column_rank_mode = _MOJO_COLUMN_RANK_MODE
        self._planner_logger = logger

        # Populated by build_knowledge() / from_registry()
        self.tables: dict[str, list[dict[str, Any]]] = {}  # source → records (lazy-loaded)
        self.profiles: dict[str, dict[str, dict[str, Any]]] = {}  # source → col → stats
        self.graph: Any = {}  # SchemaGraph (imported lazily)
        self._mojo_profiles: dict[str, dict[str, Any]] = {}
        self._relations: dict[str, list[dict[str, Any]]] = {}
        self._join_cache: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        self._join_probe_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._join_evidence_cache: dict[tuple[str, str, str, str], dict[str, float]] = {}
        self._group_join_evidence_cache: dict[tuple[str, str, str, str, str], dict[str, float]] = {}
        self._adaptive_source_context: dict[str, AdaptiveSourceContext] = {}
        self.mojo_engines: list[str] = []
        self._field_map_cache: dict[str, dict[str, Any]] = {}  # hint → Mojo field_analysis entry
        # Lazy record loading — Parquet paths for sources not yet loaded into memory
        self._parquet_paths: dict[str, Path] = {}  # source → .parquet cache path
        # query_hints from Arrow Parquet metadata — same data the LLM reads
        self._query_hints_by_src: dict[str, list[dict[str, Any]]] = {}
        # connections from source registry
        self._connections: list[dict[str, Any]] = []
        self._plan_cache: dict[
            tuple[str, str | None, str, str | None, int],
            QueryPlan,
        ] = {}
        self._join_candidate_columns: dict[str, dict[str, dict[str, Any]]] = {}
        self._metric_resolution_cache: dict[
            tuple[str, str | None, str],
            tuple[str, str, float, str, list[str]],
        ] = {}
        self._dimension_resolution_cache: dict[
            tuple[str, str | None],
            tuple[str, str, float, list[str]],
        ] = {}
        # Cached planners are shared across requests, so public execution
        # entrypoints must serialize mutation of internal caches and tables.
        self._state_lock = threading.RLock()
        # Vector resolver — built once after graph is populated, used in resolve_metric/dimension
        self._vector_resolver: Any = None
        self._vector_resolver_dirty = False

    def _llm_confirm_plan(self, **_kwargs: Any) -> dict[str, Any] | None:
        """Optional LLM review hook. Tests monkeypatch this when they want review behavior."""
        return None

    # ── Binary detection ──────────────────────────────────────────────────────

    @staticmethod
    def _find_mojo() -> Path | None:
        """Search standard paths for the compiled Mojo simulate binary."""
        root = Path(__file__).parent.parent.parent.parent
        return _find_mojo_binary_impl(root)

    def _call_mojo(
        self,
        payload: dict[str, Any],
        timeout: int = 30,
    ) -> dict[str, Any] | None:
        return _call_planner_mojo_impl(
            mojo_binary=self._mojo_binary,
            payload=payload,
            timeout=timeout,
            transport=_PLANNER_MOJO_TRANSPORT,
            shared_engines=_PLANNER_MOJO_SHARED_ENGINES,
            should_use_resident_fn=_should_use_resident_planner_mojo,
            invoke_engine_sync_fn=invoke_engine_sync,
            invoke_planner_mojo_fn=invoke_planner_mojo,
            subprocess_run_fn=subprocess.run,
            logger=logger,
        )

    def _probe_engines(self) -> list[str]:
        """Return list of confirmed Mojo engine names.

        Result cached to .algenta_cache/engines.json and only re-probed
        when the Mojo binary mtime changes (saves ~1.4s per warm startup).
        """
        cd = self._cache_dir()
        engines_cache = cd / "engines.json"

        # Cache hit: binary unchanged
        if self._mojo_binary and engines_cache.exists():
            try:
                binary_mtime = self._mojo_binary.stat().st_mtime
                cache_mtime = engines_cache.stat().st_mtime
                if cache_mtime > binary_mtime:
                    cached_raw = json.loads(engines_cache.read_text()).get("engines", [])
                    cached = (
                        [str(engine) for engine in cached_raw]
                        if isinstance(cached_raw, list)
                        else []
                    )
                    logger.debug("auto_planner_engines_cache_hit", engines=cached)
                    return cached
            except Exception as exc:
                logger.debug(
                    "auto_planner_engines_cache_read_error",
                    error=str(exc),
                )

        probes: dict[str, dict[str, Any]] = {
            "column_profile": {
                "engine_type": "column_profile",
                "columns": {"x": {"values": ["1", "2", "3"], "strings": [], "sample_size": 3}},
            },
            "relation_detect": {
                "engine_type": "relation_detect",
                "source": "_probe",
                "min_confidence": 0.70,
                "columns": {"a": [1.0, 2.0, 3.0], "b": [2.0, 4.0, 6.0], "c": [2.0, 8.0, 18.0]},
            },
            "field_map": {
                "engine_type": "field_map",
                "data": {"revenue": [100.0, 200.0, 150.0], "cost": [60.0, 90.0, 70.0]},
            },
            "column_match": {
                "engine_type": "column_match",
                "source_a": "_q",
                "source_b": "_s",
                "columns_a": [
                    {
                        "name": "revenue",
                        "semantic_type": "currency",
                        "polarity": 1,
                        "distribution": "lognormal",
                        "mean": 150.0,
                        "std": 50.0,
                    }
                ],
                "columns_b": [
                    {
                        "name": "EXT_PRICE",
                        "semantic_type": "currency",
                        "polarity": 1,
                        "distribution": "lognormal",
                        "mean": 5000.0,
                        "std": 2000.0,
                    }
                ],
                "min_confidence": 0.10,
            },
            "join_detect": {
                "engine_type": "join_detect",
                "source_a": "A",
                "source_b": "B",
                "min_confidence": 0.30,
                "columns": {
                    "A.id": {"values": ["X1", "X2", "X3"], "unique_ratio": 0.99, "sample_size": 3},
                    "B.id": {"values": ["X1", "X2", "X4"], "unique_ratio": 0.99, "sample_size": 3},
                },
            },
            "string_similarity": {
                "engine_type": "string_similarity",
                "hint_words": ["business", "unit"],
                "columns": ["LEACH_BU", "PRODUCT_LINE"],
                "threshold": 0.0,
            },
            "column_rank": {
                "engine_type": "column_rank",
                "hint_words": ["unit", "price"],
                "candidates": [
                    {
                        "source": "POS",
                        "column": "UNIT_PRICE",
                        "role": "unit_measure",
                        "fill_rate": 1.0,
                    },
                    {
                        "source": "POS",
                        "column": "EXT_PRICE",
                        "role": "derived_measure",
                        "fill_rate": 1.0,
                    },
                ],
                "context": {
                    "source_type": "POS",
                    "query_role": "unit_measure",
                },
                "top_k": 2,
            },
            "monte_carlo": {
                "engine_type": "monte_carlo",
                "runs": 10,
                "variables": [{"name": "x", "distribution": "normal", "mean": 0, "std": 1}],
                "objective": "x",
            },
        }
        supported = []
        for name, payload in probes.items():
            result = self._call_mojo(payload, timeout=5)
            if result is not None:
                supported.append(name)

        # Persist so next startup skips probing
        try:
            cd.mkdir(parents=True, exist_ok=True)
            engines_cache.write_text(json.dumps({"engines": supported}))
        except Exception as exc:
            logger.debug(
                "auto_planner_engines_cache_write_error",
                error=str(exc),
            )

        return supported

    # ── Registry-backed knowledge building ───────────────────────────────────

    @classmethod
    def from_registry(
        cls,
        org_id: str,
        data_dir: Path | None = None,
        mojo_binary: Path | None = None,
        join_min_confidence: float = 0.40,
        llm_policy: str = "never",
        allowed_source_ids: set[str] | None = None,
    ) -> AutoPlanner:
        """
        Build an AutoPlanner from pre-registered sources in the source registry.

        Sources registered via POST /v1/ingest (or /v1/map) have pre-built:
          - Arrow Parquet files with embedded algenta_schema metadata
          - .meta.json files with columns, roles, formulas, query_hints
          - connections.json with detected join keys

        This path is much faster than CSV profiling because the schema work
        was already done at registration time.  The LLM uses the same
        query_hints metadata to decide which columns to pick.

        Example:
            planner = AutoPlanner.from_registry("my-org-id")
            plan = planner.plan("revenue", "product line")
        """
        from apps.api_server.services import source_registry as _reg

        instance = cls(
            data_dir=data_dir or Path("."),
            mojo_binary=mojo_binary,
            join_min_confidence=join_min_confidence,
            llm_policy=llm_policy,
        )

        if instance._mojo_binary:
            instance.mojo_engines = instance._probe_engines()

        # Load all sources for this org from the registry
        sources = _reg.list_sources(org_id)
        if allowed_source_ids is not None:
            sources = [entry for entry in sources if entry.get("id") in allowed_source_ids]
        graph: dict[str, Any] = {}
        query_hints_by_src: dict[str, list[dict[str, Any]]] = {}
        connections = _reg.get_connections(org_id)
        if allowed_source_ids is not None:
            connections = [
                conn
                for conn in connections
                if conn.get("source_a") in allowed_source_ids
                and conn.get("source_b") in allowed_source_ids
            ]

        for src_entry in sources:
            src_id = src_entry["id"]
            src_name = src_entry["name"]
            meta = _reg.get_source_meta(org_id, src_id)
            if not meta:
                continue
            source_schema_revision = str(
                src_entry.get("schema_revision") or _reg.source_schema_revision(org_id, src_id)
            )
            artifacts = _registry_source_artifacts_from_meta(
                org_id=org_id,
                source_id=src_id,
                schema_revision=source_schema_revision,
                meta=meta,
            )

            # Reconstruct ColumnNode graph from persisted metadata
            nodes = artifacts.nodes
            if nodes:
                graph[src_name] = nodes

            # Store query_hints for metric resolution
            hints = artifacts.query_hints
            if hints:
                query_hints_by_src[src_name] = hints

            # Reuse persisted planner stats and lazy-load records only on execution.
            instance.profiles[src_name] = artifacts.profile
            parquet_path = _reg.get_source_parquet_path(org_id, src_id)
            if parquet_path is not None:
                instance._parquet_paths[src_name] = parquet_path

        instance.graph = graph
        instance._query_hints_by_src = query_hints_by_src
        instance._connections = connections
        instance._rebuild_adaptive_context()
        instance._build_vector_resolver()

        # Pre-populate join cache from registry connections.
        instance._join_cache = _build_registry_join_cache(connections)

        logger.debug(
            "auto_planner_from_registry",
            org_id=org_id,
            sources=list(graph.keys()),
            connections=len(connections),
        )
        return instance

    def refresh_registry_source(
        self,
        *,
        org_id: str,
        source_id: str,
        source_name: str,
        schema_meta: dict[str, Any],
        source_schema_revision: str,
        parquet_path: Path | None,
        new_connections: list[dict[str, Any]],
    ) -> None:
        """
        Incrementally apply one newly registered source to an existing registry planner.

        This avoids reconstructing the full planner graph from source-registry
        metadata on every registration when a warm planner for the same
        org/visibility already exists.
        """
        _refresh_registry_source_impl(
            self,
            org_id=org_id,
            source_id=source_id,
            source_name=source_name,
            schema_meta=schema_meta,
            source_schema_revision=source_schema_revision,
            parquet_path=parquet_path,
            new_connections=new_connections,
            registry_source_artifacts_from_meta_fn=_registry_source_artifacts_from_meta,
        )
