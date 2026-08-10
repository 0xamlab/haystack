"""llm_provider_service — public facade.

The implementation is split into _<name>.py submodules of this package for
maintainability (each well under 1000 lines). This __init__.py re-exports
the complete public API so existing imports continue to work unchanged.
"""
from __future__ import annotations

from apps.api_server.services.llm_provider_service._config import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._parsers import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._parsers import (  # noqa: F401
    _require_non_empty_string,
    _parse_capabilities,
    _validate_backend_capabilities,
    _resolve_upstream_model,
    _validate_embedding_input_type,
    _parse_provider_header_envs,
    _parse_router_targets,
    _parse_router_target_list,
    _parse_capability_router_targets,
    _parse_router_fallback_policy,
    _validate_capability_router_fallback_policies,
    _parse_router_fallback_on,
    _effective_router_fallback_policy,
    _validate_capability_router_fallback_on,
    _parse_router_max_attempts,
    _validate_capability_router_max_attempts,
    _parse_provider_timeout_seconds,
    _validate_capability_timeout_seconds,
    _validate_router_fields,
)
from apps.api_server.services.llm_provider_service._payload_builders import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._payload_builders import (  # noqa: F401
    _provider_chat_path,
    _provider_embeddings_path,
    _provider_embeddings_payload,
    _provider_model_resource,
    _provider_chat_payload,
)
from apps.api_server.services.llm_provider_service._response_parsing import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._response_parsing import (  # noqa: F401
    _parse_provider_chat_completion,
)
from apps.api_server.services.llm_provider_service._config_lookup import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._config_lookup import (  # noqa: F401
    _provider_config_map,
    _router_targets_for_capability,
    _router_fallback_policy_for_capability,
    _router_fallback_on_for_capability,
    _router_max_attempts_for_capability,
    _provider_timeout_seconds_for_capability,
    _provider_timeout_override_for_route,
    _provider_capabilities_for_query,
    _get_provider_required_header_names,
    _get_provider_required_auth_env_vars,
)
from apps.api_server.services.llm_provider_service._route_resolution import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._route_resolution import (  # noqa: F401
    _set_provider_attempts,
    _provider_attempt_records_from_error,
    _provider_failure_details_from_error,
    _merged_provider_attempts,
    _resolve_provider_route_targets_from_map,
    _resolve_provider_reachable_route_targets_via_resolver,
    _resolve_provider_reachable_route_targets_from_map,
    _router_all_declared_target_model_ids,
    _resolve_provider_leaf_targets_from_map,
)
from apps.api_server.services.llm_provider_service._loader import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._http_layer import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._http_layer import (  # noqa: F401
    _provider_auth_headers,
    _provider_post_json,
    _router_declared_target_model_ids_for_capability,
    _router_attempt_target_model_ids_for_capability,
    _router_reachable_target_model_ids_for_capability,
)
from apps.api_server.services.llm_provider_service._executors_chat import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._executors_chat import (  # noqa: F401
    _router_uses_nested_router_targets,
    _execute_router_chat_completion,
)
from apps.api_server.services.llm_provider_service._executors_embeddings import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._executors_embeddings import (  # noqa: F401
    _execute_router_embeddings,
)
from apps.api_server.services.llm_provider_service._executors_local import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._executors_local import (  # noqa: F401
    load_local_llm_checkpoint_map,
    execute_local_chat_completion,
)
from apps.api_server.services.llm_provider_service._chat_api import *  # noqa: F401, F403
from apps.api_server.services.llm_provider_service._embeddings_api import *  # noqa: F401, F403
