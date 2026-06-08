from apps.api_server.services.connectors import preview_cache_distributed as wrapper
from apps.api_server.services.connectors import (
    preview_cache_distributed_runner as runner,
)
from apps.api_server.services.connectors import (
    preview_cache_distributed_state as state,
)


def test_preview_cache_distributed_wrapper_reexports_runner_and_state() -> None:
    assert (
        wrapper.run_distributed_inline_preview_test_once
        is runner.run_distributed_inline_preview_test_once
    )
    assert (
        wrapper.run_distributed_inline_preview_browse_once
        is runner.run_distributed_inline_preview_browse_once
    )
    assert (
        wrapper.run_distributed_saved_connector_test_once
        is runner.run_distributed_saved_connector_test_once
    )
    assert (
        wrapper.run_distributed_saved_connector_browse_once
        is runner.run_distributed_saved_connector_browse_once
    )
    assert (
        wrapper._DISTRIBUTED_INLINE_PREVIEW_LOCK_TTL_SECONDS
        == state._DISTRIBUTED_INLINE_PREVIEW_LOCK_TTL_SECONDS
    )
