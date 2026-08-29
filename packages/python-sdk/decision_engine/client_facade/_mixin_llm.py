"""_LLMMixin for the DecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/client_facade.py during modularization.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

# Lazy facade-routed wrappers for the @cache surface-module loaders.
# Tests monkey-patch these on the facade module; each call here re-reads
# the attribute from the facade so the patch propagates into mixin bodies.
def _connector_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._connector_surface_module()


def _repository_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._repository_surface_module()


def _query_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._query_surface_module()


def _contract_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._contract_surface_module()


def _simulation_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._simulation_surface_module()


def _source_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._source_surface_module()


def _job_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._job_surface_module()


def _product_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._product_surface_module()


def _deployment_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._deployment_surface_module()


def _account_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._account_surface_module()


def _control_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._control_plane_surface_module()


def _llm_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._llm_surface_module()


def _agent_run_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._agent_run_surface_module()


def _decision_plan_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_plan_surface_module()


def _decision_memory_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_memory_surface_module()


def _trigger_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._trigger_surface_module()


def _capability_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._capability_plane_surface_module()



class _LLMMixin:
    def list_models(self) -> LLMModelListResult:
        return _llm_surface_module().list_models(self)

    def tokenize(self, text: str, *, model: str = "text.tokenizer") -> TokenizeResult:
        return _llm_surface_module().tokenize(self, text, model=model)

    def count_tokens(
        self,
        text: str,
        *,
        model: str = "text.tokenizer",
    ) -> CountTokensResult:
        return _llm_surface_module().count_tokens(self, text, model=model)

    def resolve_artifact_bridge(
        self,
        *,
        repo_id: str,
        filename: str,
        revision: str | None = None,
        local_files_only: bool = True,
    ) -> ArtifactBridgeResolveResult:
        return _llm_surface_module().resolve_artifact_bridge(
            self,
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        )

    def chat_completions(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "text.tokenizer",
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
    ) -> ChatCompletionsResult:
        return _llm_surface_module().chat_completions(
            self,
            messages,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
        )

    def stream_chat_completions(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "text.tokenizer",
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
    ) -> Iterator[ChatCompletionsStreamChunkResult]:
        return _llm_surface_module().stream_chat_completions(
            self,
            messages,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
        )

    def responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> ResponsesResult:
        return _llm_surface_module().responses(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def stream_responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> Iterator[ResponseStreamEventResult]:
        return _llm_surface_module().stream_responses(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def embeddings(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.hash_embedding_v1",
        dimensions: int = 64,
    ) -> EmbeddingsResult:
        return _llm_surface_module().embeddings(
            self,
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def embedding_similarity(
        self,
        left: list[float],
        right: list[float],
        *,
        model: str = "embeddings.cosine_similarity",
    ) -> EmbeddingSimilarityResult:
        return _llm_surface_module().embedding_similarity(
            self,
            left,
            right,
            model=model,
        )

    def rerank(
        self,
        query_embedding: list[float],
        documents: list[dict[str, Any]],
        *,
        model: str = "embeddings.cosine_similarity",
        top_n: int | None = None,
    ) -> RerankResponseResult:
        return _llm_surface_module().rerank(
            self,
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        )

