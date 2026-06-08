from apps.api_server.services.source_registration_scope import (
    resolve_registration_scopes,
)


def test_resolve_registration_scopes_uses_private_owner_marker() -> None:
    visibility, owner_user_id, owner_key_id, source_id = resolve_registration_scopes(
        cache_key="cache-key",
        visibility="private",
        auth_user_id="user-1",
        auth_key_id="key-1",
        owner_user_id=None,
        owner_key_id=None,
        source_id_for_fn=lambda value: f"sid:{value}",
    )

    assert (visibility, owner_user_id, owner_key_id, source_id) == (
        "private",
        "user-1",
        "key-1",
        "sid:cache-key:user-1",
    )


def test_resolve_registration_scopes_uses_global_cache_key_for_shared_sources() -> None:
    visibility, owner_user_id, owner_key_id, source_id = resolve_registration_scopes(
        cache_key="cache-key",
        visibility="shared",
        auth_user_id="user-1",
        auth_key_id="key-1",
        owner_user_id="override-user",
        owner_key_id="override-key",
        source_id_for_fn=lambda value: f"sid:{value}",
    )

    assert (visibility, owner_user_id, owner_key_id, source_id) == (
        "shared",
        "override-user",
        "override-key",
        "sid:cache-key",
    )
