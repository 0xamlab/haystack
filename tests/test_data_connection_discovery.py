from apps.api_server.services import data_connection_discovery as discovery
from apps.api_server.services import data_connection_specs as specs


def test_data_connection_discovery_leaf_builds_redis_metadata() -> None:
    metadata = discovery.build_discovery_metadata(
        "redis",
        config={"limit": 2},
        items=[{"id": "orders:1"}, {"id": "orders:2"}],
        provider_metadata={
            "keyspace_total_count": 10,
            "scan_exhausted": False,
        },
    )

    assert metadata == {
        "scope_noun": "keyspace",
        "returned_count": 2,
        "count_kind": "sample",
        "matching_total_count": None,
        "scope_total_count": 10,
        "more_available": True,
        "sampling_reason": "keyspace_scan_limit",
    }


def test_data_connection_specs_reexports_discovery_helpers() -> None:
    assert specs.build_discovery_labels is discovery.build_discovery_labels
    assert specs.build_discovery_metadata is discovery.build_discovery_metadata
