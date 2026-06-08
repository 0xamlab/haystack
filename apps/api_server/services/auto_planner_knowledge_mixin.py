from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.api_server.services.auto_planner_knowledge import (
    append_vector_resolver_source as _append_vector_resolver_source_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    build_knowledge as _build_knowledge_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    build_vector_resolver as _build_vector_resolver_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    cache_dir as _cache_dir_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    cache_fresh as _cache_fresh_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    discover_sources as _discover_sources_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    ensure_records as _ensure_records_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    ensure_vector_resolver_ready as _ensure_vector_resolver_ready_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    load_from_cache as _load_from_cache_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    mojo_profile_source as _mojo_profile_source_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    mojo_relations_source as _mojo_relations_source_impl,
)
from apps.api_server.services.auto_planner_knowledge import (
    write_cache as _write_cache_impl,
)


class AutoPlannerKnowledgeMixin:
    _cache_version: int
    _vector_resolver: Any | None
    _mojo_column_rank_mode: str
    tables: dict[str, list[dict[str, Any]]]
    _parquet_paths: dict[str, Path]

    def discover_sources(self) -> list[str]:
        """Scan data_dir for supported local tabular files and return source names."""
        return _discover_sources_impl(self)

    def _cache_dir(self) -> Path:
        return _cache_dir_impl(self)

    def _cache_fresh(self, name: str, csv_path: Path) -> bool:
        """True if meta.json + Parquet exist and are newer than the CSV."""
        return _cache_fresh_impl(
            self,
            name,
            csv_path,
            cache_version=self._cache_version,
        )

    def _load_from_cache(
        self,
        name: str,
    ) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
        """
        Fast warm-path cache load — returns (profiles, mojo_profiles, relations)
        from the JSON meta file only. Raw records are NOT loaded here; they are
        lazy-loaded from Parquet only when execute_plan() actually needs them.
        """
        return _load_from_cache_impl(self, name)

    def _ensure_records(self, name: str) -> None:
        """
        Lazy-load raw records from the Parquet cache if not already in memory.
        Called by execute_plan() for each source it actually needs.
        """
        _ensure_records_impl(self, name)

    def _write_cache(
        self,
        name: str,
        recs: list[dict[str, Any]],
        mojo_profiles: dict[str, Any],
        relations: list[Any],
        profiles: dict[str, Any] | None = None,
    ) -> None:
        """Persist records as Parquet + all metadata as JSON."""
        _write_cache_impl(
            self,
            name,
            recs,
            mojo_profiles,
            relations,
            profiles=profiles,
            cache_version=self._cache_version,
        )

    def build_knowledge(self, source_map: dict[str, str] | None = None) -> None:
        """Load all sources, profile, run Mojo analysis, and build the schema graph."""
        _build_knowledge_impl(self, source_map)

    def resolve_fields_batch(
        self,
        *,
        metric: tuple[str, str | None, str | None] | None = None,
        group_by: tuple[str, str | None, str | None] | None = None,
        date: tuple[str, str | None, str | None] | None = None,
        filter_: tuple[str, str | None, str | None] | None = None,
    ) -> dict[str, object]:
        self._ensure_vector_resolver_ready()
        if self._vector_resolver is None:
            return {"metric": None, "group_by": None, "date": None, "filter": None}
        resolved = self._vector_resolver.resolve_plan_fields(
            metric=metric,
            group_by=group_by,
            date=date,
            filter_=filter_,
        )
        return resolved if isinstance(resolved, dict) else {}

    def _build_vector_resolver(self) -> None:
        _build_vector_resolver_impl(
            self,
            mojo_column_rank_mode=self._mojo_column_rank_mode,
        )

    def _ensure_vector_resolver_ready(self) -> None:
        _ensure_vector_resolver_ready_impl(self)

    def _append_vector_resolver_source(self, source_name: str) -> bool:
        return _append_vector_resolver_source_impl(self, source_name)

    def _mojo_profile_source(
        self,
        args: tuple[str, dict[str, Any]],
    ) -> tuple[str, dict[str, Any]]:
        return _mojo_profile_source_impl(self, args)

    def _mojo_relations_source(
        self,
        args: tuple[str, dict[str, Any]],
    ) -> tuple[str, list[Any]]:
        return _mojo_relations_source_impl(self, args)
