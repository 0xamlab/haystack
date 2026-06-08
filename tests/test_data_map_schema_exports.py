from apps.api_server.routers import data_map as data_map_router
from apps.api_server.schemas.data_map import DataSource as SchemaDataSource
from apps.api_server.schemas.data_map import MapRequest as SchemaMapRequest
from apps.api_server.schemas.data_map import MapResponse as SchemaMapResponse


def test_data_map_router_reexports_schema_models() -> None:
    assert data_map_router.DataSource is SchemaDataSource
    assert data_map_router.MapRequest is SchemaMapRequest
    assert data_map_router.MapResponse is SchemaMapResponse


def test_data_source_syncs_registered_aliases() -> None:
    source = data_map_router.DataSource(name="Orders", dataset_id="dataset_123")

    assert source.dataset_id == "dataset_123"
    assert source.source_id == "dataset_123"
