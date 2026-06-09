"""Shared imports + helpers for test_llm_api_router_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-4/tests/test_llm_api_router.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

from types import SimpleNamespace

from apps.api_server.main import app

from apps.api_server.db.session import get_db

from apps.api_server.middleware.auth import get_current_org, get_redis

from apps.api_server.routers import llm as llm_router

from apps.api_server.services.llm_api_service import LLMAPIError, LLMModelDescriptor

from apps.runtime.mojo_library_runner import MojoLibraryError

from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]

async def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_llm_api",
        "key_id": "key_llm_api",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }

def _tokenizer_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="text.tokenizer",
        runtime_module="text.tokenizer",
        description="Deterministic word tokenizer backed by the runtime library catalog.",
        capabilities=("tokenize", "count_tokens", "chat_completions"),
        supported_endpoints=(
            "/v1/models",
            "/v1/tokenize",
            "/v1/count_tokens",
            "/v1/chat/completions",
            "/v1/responses",
        ),
        tokenizer_kind="word",
        similarity_metric=None,
        runtime_functions=("word_tokenize", "sentence_tokenize"),
        bridge_cache_root="/tmp/algenta-hf-cache",
        bridge_auth_env_vars=("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
        bridge_auth_configured=True,
        bridge_tokenizer_backends=("tiktoken", "sentencepiece"),
        bridge_artifact_backends=("safetensors", "huggingface_hub"),
        available=available,
    )

def _embedding_generation_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="text.hash_embedding_v1",
        runtime_module="text.tokenizer",
        description="Deterministic lexical hash embeddings generated from runtime tokenization and stable feature hashing.",
        capabilities=("embeddings",),
        supported_endpoints=("/v1/models", "/v1/embeddings", "/v1/responses"),
        tokenizer_kind="word",
        similarity_metric=None,
        runtime_functions=("word_tokenize",),
        bridge_cache_root="/tmp/algenta-hf-cache",
        bridge_auth_env_vars=("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
        bridge_auth_configured=True,
        bridge_tokenizer_backends=("tiktoken", "sentencepiece"),
        bridge_artifact_backends=("safetensors", "huggingface_hub"),
        available=available,
    )

def _embedding_similarity_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="embeddings.cosine_similarity",
        runtime_module="embeddings",
        description="Cosine similarity over caller-supplied embedding vectors.",
        capabilities=("embedding_similarity", "rerank"),
        supported_endpoints=("/v1/models", "/v1/embeddings/similarity", "/v1/rerank"),
        tokenizer_kind=None,
        similarity_metric="cosine",
        runtime_functions=("cosine_similarity",),
        bridge_cache_root=None,
        bridge_auth_env_vars=(),
        bridge_auth_configured=False,
        bridge_tokenizer_backends=(),
        bridge_artifact_backends=(),
        available=available,
    )

def _provider_chat_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="provider.gpt-4o-mini",
        runtime_module="provider.openai_compatible",
        description="Provider-backed OpenAI-compatible chat model.",
        capabilities=("chat_completions", "embeddings"),
        supported_endpoints=(
            "/v1/models",
            "/v1/chat/completions",
            "/v1/embeddings",
            "/v1/responses",
        ),
        tokenizer_kind=None,
        similarity_metric=None,
        runtime_functions=(),
        provider_backend="openai_compatible",
        bridge_cache_root=None,
        bridge_auth_env_vars=(),
        bridge_auth_configured=False,
        bridge_tokenizer_backends=(),
        bridge_artifact_backends=(),
        available=available,
    )

async def _noop_rate_limit(*, request: object, auth: object, redis_client: object) -> None:
    del request, auth, redis_client



__all__ = [
    "annotations",
    "SimpleNamespace",
    "app",
    "get_db",
    "get_current_org",
    "get_redis",
    "llm_router",
    "LLMAPIError",
    "LLMModelDescriptor",
    "MojoLibraryError",
    "SyncASGIClient",
    "PROTECTED_OPENAPI_SECURITY",
    "_fake_auth",
    "_tokenizer_model_descriptor",
    "_embedding_generation_model_descriptor",
    "_embedding_similarity_model_descriptor",
    "_provider_chat_model_descriptor",
    "_noop_rate_limit",
]
