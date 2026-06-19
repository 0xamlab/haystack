"""MCP tools for deterministic Algenta utility-model routes."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_MODELS_SPEC: dict[str, Any] = {
    "name": "list_models",
    "description": (
        "List the current Algenta model catalog, including deterministic utility models and "
        "any provider-backed routed entries with their routing, failover, timeout, and auth "
        "metadata, including capability-specific chat and embedding auth/header readiness. "
        "Use this before calling tokenize, count_tokens, chat_completions, responses, "
        "embeddings, embedding_similarity, or rerank."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

RESOLVE_ARTIFACT_BRIDGE_SPEC: dict[str, Any] = {
    "name": "resolve_artifact_bridge",
    "description": (
        "Resolve a Hugging Face artifact path through the Algenta compatibility-ring artifact "
        "bridge. Defaults to cache-only lookup and never downloads unless local_files_only=false."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repo_id", "filename"],
        "properties": {
            "repo_id": {"type": "string"},
            "filename": {"type": "string"},
            "revision": {"type": "string"},
            "local_files_only": {"type": "boolean", "default": True},
        },
        "additionalProperties": False,
    },
}

TOKENIZE_SPEC: dict[str, Any] = {
    "name": "tokenize",
    "description": "Tokenize UTF-8 text with a supported deterministic Algenta tokenizer model.",
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {"type": "string", "default": "text.tokenizer"},
            "input": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

COUNT_TOKENS_SPEC: dict[str, Any] = {
    "name": "count_tokens",
    "description": "Count tokens with a supported deterministic Algenta tokenizer model.",
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {"type": "string", "default": "text.tokenizer"},
            "input": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

CHAT_COMPLETIONS_SPEC: dict[str, Any] = {
    "name": "chat_completions",
    "description": (
        "Run the deterministic Algenta utility chat surface. This is a tokenizer-backed "
        "utility route, not a provider-backed generative model."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["messages"],
        "properties": {
            "model": {"type": "string", "default": "text.tokenizer"},
            "messages": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["role", "content"],
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["system", "user", "assistant", "developer"],
                        },
                        "content": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
}

RESPONSES_SPEC: dict[str, Any] = {
    "name": "responses",
    "description": (
        "Run the unified Algenta utility response surface over deterministic tokenization "
        "or lexical embeddings."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {"type": "string", "default": "text.tokenizer"},
            "input": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
            "dimensions": {"type": "integer", "default": 64, "minimum": 1, "maximum": 4096},
        },
        "additionalProperties": False,
    },
}

EMBEDDINGS_SPEC: dict[str, Any] = {
    "name": "embeddings",
    "description": "Generate deterministic lexical embeddings with the supported Algenta model.",
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {"type": "string", "default": "text.hash_embedding_v1"},
            "input": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
            "dimensions": {"type": "integer", "default": 64, "minimum": 1, "maximum": 4096},
        },
        "additionalProperties": False,
    },
}

EMBEDDING_SIMILARITY_SPEC: dict[str, Any] = {
    "name": "embedding_similarity",
    "description": "Score two caller-supplied embedding vectors with a supported similarity model.",
    "inputSchema": {
        "type": "object",
        "required": ["left", "right"],
        "properties": {
            "model": {"type": "string", "default": "embeddings.cosine_similarity"},
            "left": {"type": "array", "minItems": 1, "items": {"type": "number"}},
            "right": {"type": "array", "minItems": 1, "items": {"type": "number"}},
        },
        "additionalProperties": False,
    },
}

RERANK_SPEC: dict[str, Any] = {
    "name": "rerank",
    "description": "Rerank caller-supplied document embeddings deterministically.",
    "inputSchema": {
        "type": "object",
        "required": ["query_embedding", "documents"],
        "properties": {
            "model": {"type": "string", "default": "embeddings.cosine_similarity"},
            "query_embedding": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "number"},
            },
            "documents": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "embedding"],
                    "properties": {
                        "id": {"type": "string"},
                        "embedding": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "number"},
                        },
                        "text": {"type": "string"},
                        "metadata": {"type": "object"},
                    },
                    "additionalProperties": False,
                },
            },
            "top_n": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
}


async def list_models_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_models does not accept arguments.")
    result = await api("GET", "/v1/models")
    return json.dumps(result, indent=2)


async def resolve_artifact_bridge_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "POST",
        "/v1/artifacts/resolve",
        json={
            "repo_id": arguments["repo_id"],
            "filename": arguments["filename"],
            "revision": arguments.get("revision"),
            "local_files_only": bool(arguments.get("local_files_only", True)),
        },
    )
    return json.dumps(result, indent=2)


async def tokenize_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "POST",
        "/v1/tokenize",
        json={"input": arguments["input"], "model": arguments.get("model", "text.tokenizer")},
    )
    return json.dumps(result, indent=2)


async def count_tokens_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "POST",
        "/v1/count_tokens",
        json={"input": arguments["input"], "model": arguments.get("model", "text.tokenizer")},
    )
    return json.dumps(result, indent=2)


async def chat_completions_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "POST",
        "/v1/chat/completions",
        json={
            "messages": arguments["messages"],
            "model": arguments.get("model", "text.tokenizer"),
        },
    )
    return json.dumps(result, indent=2)


async def responses_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "POST",
        "/v1/responses",
        json={
            "input": arguments["input"],
            "model": arguments.get("model", "text.tokenizer"),
            "dimensions": int(arguments.get("dimensions", 64)),
        },
    )
    return json.dumps(result, indent=2)


async def embeddings_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "POST",
        "/v1/embeddings",
        json={
            "input": arguments["input"],
            "model": arguments.get("model", "text.hash_embedding_v1"),
            "dimensions": int(arguments.get("dimensions", 64)),
        },
    )
    return json.dumps(result, indent=2)


async def embedding_similarity_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "POST",
        "/v1/embeddings/similarity",
        json={
            "left": arguments["left"],
            "right": arguments["right"],
            "model": arguments.get("model", "embeddings.cosine_similarity"),
        },
    )
    return json.dumps(result, indent=2)


async def rerank_handler(arguments: dict[str, Any]) -> str:
    body: dict[str, Any] = {
        "query_embedding": arguments["query_embedding"],
        "documents": arguments["documents"],
        "model": arguments.get("model", "embeddings.cosine_similarity"),
    }
    if "top_n" in arguments:
        body["top_n"] = int(arguments["top_n"])
    result = await api("POST", "/v1/rerank", json=body)
    return json.dumps(result, indent=2)
