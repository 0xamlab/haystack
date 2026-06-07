from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger("apps.api_server.routers.query")


def planner_auth_scope_key(auth: AuthContext | None) -> tuple[str, str, str]:
    if auth is None:
        return ("", "", "")
    return (
        str(auth.get("user_id") or ""),
        str(auth.get("key_id") or ""),
        # Workspace is folded into the 3rd (role) slot to keep the cache-key arity stable
        # while making the planner cache workspace-distinct. A platform key shares
        # user_id/key_id/role across all its workspaces, so without this a planner built
        # for workspace A could be served to workspace B (cross-tenant). The tuple is an
        # opaque cache key (only ==-compared, never decomposed), so folding is safe.
        f"{auth.get('role') or ''}|ws={auth.get('workspace_id') or ''}",
    )


def evict_planner_lru(
    *,
    planner_cache: dict[tuple[str, str, str], Any],
    planner_cache_max: int,
) -> None:
    if len(planner_cache) < planner_cache_max:
        return
    oldest_key = min(planner_cache.items(), key=lambda item: item[1].last_hit)[0]
    planner_cache.pop(oldest_key, None)


async def get_registry_planner(
    org_id: str,
    *,
    llm_policy: str = "never",
    auth: AuthContext | None = None,
    visible_entries: list[dict[str, Any]] | None = None,
    cache_lock: Any,
    planner_cache: dict[tuple[str, str, str], Any],
    planner_cache_max: int,
    cached_planner_cls: type[Any],
) -> tuple[Any, bool, str]:
    from apps.api_server.services import source_registry as _sreg
    from apps.api_server.services.auto_planner import AutoPlanner
    from apps.api_server.services.data_visibility import (
        filter_visible_datasets,
        visibility_hash,
    )

    schema_revision = _sreg.schema_revision(org_id)
    auth_scope = planner_auth_scope_key(auth)
    if visible_entries is None:
        async with cache_lock:
            scope_matches = [
                cached
                for key, cached in planner_cache.items()
                if key[0] == org_id
                and key[1] == llm_policy
                and cached.schema_revision == schema_revision
                and cached.auth_scope_key == auth_scope
            ]
            if len(scope_matches) == 1:
                scope_matches[0].touch()
                return scope_matches[0].planner, True, schema_revision

    if visible_entries is None:
        all_entries = _sreg.list_sources(org_id)
        visible_entries = (
            filter_visible_datasets(all_entries, auth) if auth is not None else all_entries
        )
    visible_ids = {str(entry.get("id")) for entry in visible_entries if entry.get("id")}
    visibility_fingerprint = visibility_hash(visible_entries)
    cache_key = (org_id, llm_policy, visibility_fingerprint)

    async with cache_lock:
        cached = planner_cache.get(cache_key)
        if cached and cached.schema_revision == schema_revision:
            cached.touch()
            return cached.planner, True, schema_revision

    planner = await asyncio.to_thread(
        AutoPlanner.from_registry,
        org_id,
        llm_policy=llm_policy,
        allowed_source_ids=visible_ids,
    )
    built = cached_planner_cls(
        planner=planner,
        schema_revision=schema_revision,
        llm_policy=llm_policy,
        auth_scope_key=auth_scope,
    )

    async with cache_lock:
        cached = planner_cache.get(cache_key)
        if cached and cached.schema_revision == schema_revision:
            cached.touch()
            return cached.planner, True, schema_revision
        evict_planner_lru(
            planner_cache=planner_cache,
            planner_cache_max=planner_cache_max,
        )
        planner_cache[cache_key] = built

    return planner, False, schema_revision


async def try_incremental_registry_planner_update(
    org_id: str,
    *,
    llm_policy: str,
    auth: AuthContext | None,
    source_id: str,
    source_name: str,
    schema_meta: dict[str, Any],
    source_schema_revision: str,
    parquet_path: Path | None,
    new_connections: list[dict[str, Any]],
    cache_lock: Any,
    planner_cache: dict[tuple[str, str, str], Any],
    planner_cache_max: int,
) -> tuple[bool, str]:
    from apps.api_server.services import source_registry as _sreg
    from apps.api_server.services.data_visibility import (
        filter_visible_datasets,
        visibility_hash,
    )

    schema_revision = _sreg.schema_revision(org_id)
    all_entries = _sreg.list_sources(org_id)
    visible_entries = (
        filter_visible_datasets(all_entries, auth) if auth is not None else all_entries
    )
    visibility_fingerprint = visibility_hash(visible_entries)
    visible_ids = {str(entry.get("id")) for entry in visible_entries if entry.get("id")}
    cache_key = (org_id, llm_policy, visibility_fingerprint)

    async with cache_lock:
        cached = planner_cache.get(cache_key)
        prior_cache_key = cache_key
        if cached is None:
            candidates = [
                (key, entry)
                for key, entry in planner_cache.items()
                if key[0] == org_id and key[1] == llm_policy
            ]
            if len(candidates) == 1:
                prior_cache_key, cached = candidates[0]

    if cached is None:
        return False, schema_revision

    if source_id not in visible_ids:
        async with cache_lock:
            live = planner_cache.get(prior_cache_key)
            if live is cached:
                live.schema_revision = schema_revision
                live.touch()
                if prior_cache_key != cache_key:
                    planner_cache.pop(prior_cache_key, None)
                    evict_planner_lru(
                        planner_cache=planner_cache,
                        planner_cache_max=planner_cache_max,
                    )
                    planner_cache[cache_key] = live
        return True, schema_revision

    planner = cached.planner
    refresh_registry_source = getattr(planner, "refresh_registry_source", None)
    if refresh_registry_source is None:
        return False, schema_revision

    try:
        await asyncio.to_thread(
            refresh_registry_source,
            org_id=org_id,
            source_id=source_id,
            source_name=source_name,
            schema_meta=schema_meta,
            source_schema_revision=source_schema_revision,
            parquet_path=parquet_path,
            new_connections=new_connections,
        )
    except Exception as exc:
        logger.debug(
            "registry_planner_incremental_update_failed",
            org_id=org_id,
            source_id=source_id,
            error=str(exc),
        )
        return False, schema_revision

    async with cache_lock:
        live = planner_cache.get(prior_cache_key)
        if live is cached:
            live.schema_revision = schema_revision
            live.touch()
            if prior_cache_key != cache_key:
                planner_cache.pop(prior_cache_key, None)
                evict_planner_lru(
                    planner_cache=planner_cache,
                    planner_cache_max=planner_cache_max,
                )
                planner_cache[cache_key] = live

    return True, schema_revision


async def run_cached_planner_method(
    planner: Any,
    method_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    def _invoke() -> Any:
        method = getattr(planner, method_name)
        state_lock = getattr(planner, "_state_lock", None)
        if state_lock is None:
            return method(*args, **kwargs)
        with state_lock:
            return method(*args, **kwargs)

    return await asyncio.to_thread(_invoke)


__all__ = [
    "evict_planner_lru",
    "get_registry_planner",
    "planner_auth_scope_key",
    "run_cached_planner_method",
    "try_incremental_registry_planner_update",
]
