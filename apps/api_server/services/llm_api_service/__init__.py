"""llm_api_service — public facade.

The implementation is split into _<name>.py submodules for
maintainability (each well under 1000 lines).
"""
from __future__ import annotations

import importlib
import importlib.util
import hashlib
import math
import json
import os
from functools import lru_cache
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from apps.api_server.services import llm_provider_service
from apps.api_server.services.runtime_library_service import (
    execute_public_runtime_library,
    get_public_runtime_library_health,
    list_public_runtime_library_descriptors,
)
from apps.runtime.mojo_library_runner import MojoLibraryError



from apps.api_server.services.llm_api_service._definitions import *  # noqa: E402, F401, F403
from apps.api_server.services.llm_api_service._definitions import (  # noqa: E402, F401
    _detect_bridge_backends,
    _resolve_artifact_bridge_cache_root,
    _resolve_artifact_bridge_auth_env_vars,
    _artifact_bridge_auth_configured,
    _artifact_bridge_auth_token,
    _artifact_bridge_backend_for_filename,
    _hf_hub_download,
    _require_model_capability,
    _validate_embedding_dimensions,
    _rerank_sort_order,
    _runtime_module_descriptors,
    _ARTIFACT_BRIDGE_SPECS,
    _HASH_EMBEDDING_PERSON,
    _HUGGINGFACE_LOCAL_MISS_EXCEPTIONS,
    _TEXT_TOKENIZER_MODEL_ID,
    _TEXT_TOKENIZER_TOKENIZE_FUNCTION,
    _TOKENIZER_BRIDGE_SPECS,
    _HUGGINGFACE_CACHE_ENV,
    _HF_HOME_ENV,
    _HUGGINGFACE_AUTH_ENV_VARS,
    _DISTANCE_METRICS,
    _EMBEDDINGS_MODULE_ID,
    _EMBEDDING_SIMILARITY_MODELS,
    _EMBEDDING_SIMILARITY_CAPABILITIES,
    _EMBEDDING_SIMILARITY_SUPPORTED_ENDPOINTS,
    _HASH_EMBEDDING_MODEL_ID,
    _HASH_EMBEDDING_CAPABILITIES,
    _HASH_EMBEDDING_SUPPORTED_ENDPOINTS,
    _TEXT_TOKENIZER_CAPABILITIES,
    _TEXT_TOKENIZER_SUPPORTED_ENDPOINTS,
)
from apps.api_server.services.llm_api_service._creation import *  # noqa: E402, F401, F403
from apps.api_server.services.llm_api_service._creation import (  # noqa: E402, F401
    _execute_word_tokenize,
    _stable_hash_embedding,
    _deterministic_response_id,
    _response_id_from_chat_completion_ids,
    _unique_provider_metadata,
    _deterministic_chat_completion_id,
)
