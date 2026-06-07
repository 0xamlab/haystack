from __future__ import annotations

from collections.abc import Callable


def resolve_registration_scopes(
    *,
    cache_key: str,
    visibility: str | None,
    auth_user_id: str | None,
    auth_key_id: str | None,
    owner_user_id: str | None,
    owner_key_id: str | None,
    source_id_for_fn: Callable[[str], str],
    workspace_id: str | None = None,
) -> tuple[str, str | None, str | None, str]:
    visibility_value = (visibility or "private").strip().lower()
    owner_scope = owner_user_id or auth_user_id
    owner_key_scope = owner_key_id or auth_key_id
    if visibility_value == "private" and (owner_scope or owner_key_scope):
        owner_marker = owner_scope or owner_key_scope or ""
        # Fold workspace_id into the source_id so two workspaces of the SAME org (which
        # share one platform key → identical owner_marker) get DISTINCT source_ids for
        # byte-identical content, rather than colliding on one on-disk entry. A None
        # workspace (unscoped platform call) keeps the legacy owner-only id.
        ws_suffix = f":ws={workspace_id}" if workspace_id else ""
        source_id = source_id_for_fn(f"{cache_key}:{owner_marker}{ws_suffix}")
    else:
        source_id = source_id_for_fn(cache_key)
    return visibility_value, owner_scope, owner_key_scope, source_id
