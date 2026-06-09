"""Tests for test_data_connections: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-3/tests/test_data_connections.py during modularization.
"""
from __future__ import annotations

from tests._test_data_connections_helpers import *  # noqa: F401,F403


def test_normalize_visibility_blocks_shared_for_member() -> None:
    with pytest.raises(HTTPException) as exc:
        dcs.normalize_visibility("shared", {"org_id": "org_a", "role": "member"})
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "access_scope_denied"


def test_normalize_connection_provider_maps_database_sqlite() -> None:
    broad, provider = dcs.normalize_connection_provider(
        "database",
        {"connection_string": "sqlite+pysqlite:////tmp/test.db"},
    )
    assert broad == "database"
    assert provider == "sqlite"


@pytest.mark.parametrize(
    ("provider", "config"),
    [
        ("elasticsearch", {"url": "https://elastic.example.com:443", "api_key": "secret"}),
        (
            "neo4j",
            {
                "uri": "neo4j+s://graph.example.com",
                "username": "neo4j",
                "password": "secret",
            },
        ),
        ("redis", {"url": "redis://default:pass@redis.example.com:6379/0"}),
    ],
)
def test_normalize_connection_provider_accepts_connector_backends(
    provider: str,
    config: dict[str, str],
) -> None:
    broad, normalized_provider = dcs.normalize_connection_provider(
        "database",
        {"provider": provider, **config},
    )

    assert broad == "database"
    assert normalized_provider == provider


@pytest.mark.anyio
async def test_browse_connector_real_sqlite_uses_explicit_provider(tmp_path: Path) -> None:
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("create table backlog(id integer primary key, amount real)")
        conn.commit()
    finally:
        conn.close()

    items, message = await dcs.browse_connector_real("sqlite", {"path": str(db_path)})
    assert len(items) == 1
    assert items[0]["selection"] == {"table": "backlog"}
    assert "Found 1" in message


def test_dataset_visibility_filters_private_and_shared() -> None:
    auth = {"org_id": "org_a", "role": "member", "user_id": "u1", "key_id": "k1"}
    entries = [
        {"id": "shared_ds", "visibility": "shared"},
        {"id": "private_owned", "visibility": "private", "owner_user_id": "u1"},
        {"id": "private_other", "visibility": "private", "owner_user_id": "u2"},
    ]
    visible = dcs.filter_visible_datasets(entries, auth)
    assert [entry["id"] for entry in visible] == ["shared_ds", "private_owned"]


def test_build_object_storage_connection_supports_public_azure_blob_url() -> None:
    connection = dcs._build_object_storage_connection(  # type: ignore[attr-defined]
        "azure",
        {
            "blob_url": "https://example.blob.core.windows.net/samplefiles/StormEvents.csv",
            "account_url": "https://example.blob.core.windows.net",
            "container": "samplefiles",
            "anonymous": True,
        },
        {},
    )

    assert connection["type"] == "azure_blob"
    assert connection["blob_url"].endswith("/StormEvents.csv")
    assert connection["blob"] == "StormEvents.csv"
    assert connection["anonymous"] is True


