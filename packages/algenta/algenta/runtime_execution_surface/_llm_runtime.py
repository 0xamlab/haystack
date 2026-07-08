"""llm models/tokenize/chat/responses/embeddings/rerank runtime requests.

Extracted from packages/algenta-core/algenta/runtime_execution_surface.py during modularization.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError
from algenta.runtime_model_common import coerce_payload_mapping

if TYPE_CHECKING:
    from types import ModuleType


@cache
def _runtime_api_exact_module() -> ModuleType:
    return import_module("algenta.runtime_api_exact")


@cache
def _runtime_api_payloads_module() -> ModuleType:
    return import_module("algenta.runtime_api_payloads")


@cache
def _runtime_intent_module() -> ModuleType:
    return import_module("algenta.runtime_intent")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_local_query_module() -> ModuleType:
    return import_module("algenta.runtime_local_query")


@cache
def _runtime_local_resolve_module() -> ModuleType:
    return import_module("algenta.runtime_local_resolve")


@cache
def _runtime_model_query_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_output")


@cache
def _runtime_model_query_metadata_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_metadata")


@cache
def _runtime_model_resolve_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_resolve_output")


@cache
def _runtime_model_verify_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_verify_output")


@cache
def _runtime_model_decision_plan_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_plan")


@cache
def _runtime_model_decision_envelope_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_envelope")


@cache
def _runtime_model_decision_memory_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_memory")


@cache
def _runtime_model_repository_intelligence_module() -> ModuleType:
    return import_module("algenta.runtime_model_repository_intelligence")


@cache
def _runtime_model_products_module() -> ModuleType:
    return import_module("algenta.runtime_model_products")


@cache
def _runtime_model_llm_module() -> ModuleType:
    return import_module("algenta.runtime_model_llm")


@cache
def _runtime_model_agent_runs_module() -> ModuleType:
    return import_module("algenta.runtime_model_agent_runs")


@cache
def _runtime_model_account_module() -> ModuleType:
    return import_module("algenta.runtime_model_account")


@cache
def _runtime_model_deployments_module() -> ModuleType:
    return import_module("algenta.runtime_model_deployments")


@cache
def _runtime_model_control_plane_module() -> ModuleType:
    return import_module("algenta.runtime_model_control_plane")


from algenta.runtime_execution_surface._api_client_local import *  # noqa: F401, F403
from algenta.runtime_execution_surface._api_client_local import (
    _run_sync,
)
from algenta.runtime_execution_surface._validation import *  # noqa: F401, F403
from algenta.runtime_execution_surface._validation import (
    _validate_contract_payload,
    _build_runtime_validation_error_details,
    _validate_runtime_proof_payload,
    _validate_runtime_api_payload,
    _validate_runtime_api_mapping_payload,
    _validate_runtime_api_structured_mapping_payload,
    _validate_runtime_api_mapping_list_payload,
    _validate_runtime_api_stream,
    _validate_runtime_api_payload_list,
    _request_runtime_contract_payload,
)
from algenta.runtime_execution_surface._query_jobs_triggers import *  # noqa: F401, F403
from algenta.runtime_execution_surface._decision_repo_product_deploy import *  # noqa: F401, F403
from algenta.runtime_execution_surface._account_team_billing import *  # noqa: F401, F403


def llm_models_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("list_models")
    return _validate_runtime_api_payload(
        "list_models",
        runtime._client().list_models(),
        _runtime_model_llm_module().LLMModelListOutput,
    )


def resolve_artifact_bridge_runtime_request(
    runtime: Any,
    *,
    repo_id: str,
    filename: str,
    revision: str | None,
    local_files_only: bool,
) -> Any:
    runtime._require_api_transport("resolve_artifact_bridge")
    return _validate_runtime_api_payload(
        "resolve_artifact_bridge",
        runtime._client().resolve_artifact_bridge(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        ),
        _runtime_model_llm_module().ArtifactBridgeResolveOutput,
    )


def tokenize_runtime_request(runtime: Any, text: str, *, model: str) -> Any:
    runtime._require_api_transport("tokenize")
    return _validate_runtime_api_payload(
        "tokenize",
        runtime._client().tokenize(text, model=model),
        _runtime_model_llm_module().TokenizeOutput,
    )


def count_tokens_runtime_request(runtime: Any, text: str, *, model: str) -> Any:
    runtime._require_api_transport("count_tokens")
    return _validate_runtime_api_payload(
        "count_tokens",
        runtime._client().count_tokens(text, model=model),
        _runtime_model_llm_module().CountTokensOutput,
    )


def chat_completions_runtime_request(
    runtime: Any,
    messages: list[dict[str, str]],
    *,
    model: str,
) -> Any:
    runtime._require_api_transport("chat_completions")
    return _validate_runtime_api_payload(
        "chat_completions",
        runtime._client().chat_completions(messages, model=model),
        _runtime_model_llm_module().ChatCompletionsOutput,
    )


def stream_chat_completions_runtime_request(
    runtime: Any,
    messages: list[dict[str, str]],
    *,
    model: str,
) -> Any:
    runtime._require_api_transport("stream_chat_completions")
    return _validate_runtime_api_stream(
        "stream_chat_completions",
        runtime._client().stream_chat_completions(messages, model=model),
        _runtime_model_llm_module().ChatCompletionsStreamChunkOutput,
    )


def responses_runtime_request(
    runtime: Any,
    input_value: str | list[str],
    *,
    model: str,
    dimensions: int,
) -> Any:
    runtime._require_api_transport("responses")
    return _validate_runtime_api_payload(
        "responses",
        runtime._client().responses(input_value, model=model, dimensions=dimensions),
        _runtime_model_llm_module().ResponsesOutput,
    )


def stream_responses_runtime_request(
    runtime: Any,
    input_value: str | list[str],
    *,
    model: str,
    dimensions: int,
) -> Any:
    runtime._require_api_transport("stream_responses")
    return _validate_runtime_api_stream(
        "stream_responses",
        runtime._client().stream_responses(input_value, model=model, dimensions=dimensions),
        _runtime_model_llm_module().ResponseStreamEventOutput,
    )


def embeddings_runtime_request(
    runtime: Any,
    input_value: str | list[str],
    *,
    model: str,
    dimensions: int,
) -> Any:
    runtime._require_api_transport("embeddings")
    return _validate_runtime_api_payload(
        "embeddings",
        runtime._client().embeddings(input_value, model=model, dimensions=dimensions),
        _runtime_model_llm_module().EmbeddingsOutput,
    )


def embedding_similarity_runtime_request(
    runtime: Any,
    left: list[float],
    right: list[float],
    *,
    model: str,
) -> Any:
    runtime._require_api_transport("embedding_similarity")
    return _validate_runtime_api_payload(
        "embedding_similarity",
        runtime._client().embedding_similarity(left, right, model=model),
        _runtime_model_llm_module().EmbeddingSimilarityOutput,
    )


def rerank_runtime_request(
    runtime: Any,
    query_embedding: list[float],
    documents: list[dict[str, Any]],
    *,
    model: str,
    top_n: int | None,
) -> Any:
    runtime._require_api_transport("rerank")
    return _validate_runtime_api_payload(
        "rerank",
        runtime._client().rerank(
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        ),
        _runtime_model_llm_module().RerankResponseOutput,
    )

