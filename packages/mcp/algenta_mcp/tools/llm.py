"""MCP tools for deterministic Algenta utility-model routes."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_MODELS_SPEC: dict[str, Any] = {
    "name": "list_models",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the current Algenta model catalog, including deterministic utility models and "
        "any provider-backed routed entries with their routing, failover, timeout, and auth "
        "metadata, including capability-specific chat and embedding auth/header readiness. "
        "Use this before calling tokenize, count_tokens, chat_completions, responses, "
        "embeddings, embedding_similarity, or rerank. Read-only and non-destructive; "
        "calls share the plan's per-minute rate limit with the other LLM utility routes."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

RESOLVE_ARTIFACT_BRIDGE_SPEC: dict[str, Any] = {
    "name": "resolve_artifact_bridge",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
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
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Tokenize UTF-8 text into individual tokens with a supported deterministic Algenta "
        "tokenizer model (default text.tokenizer; call list_models for every supported model "
        "id). Use this when you need the token strings themselves; call count_tokens when you "
        "only need the number. Read-only and deterministic: the same input and model always "
        "return the same tokens, and nothing is stored. Returns the resolved model id, its "
        "tokenizer_kind, the tokens array, and token_count. An unsupported model id fails "
        "with model_not_supported."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {
                "type": "string",
                "default": "text.tokenizer",
                "description": "Tokenizer model id from list_models.",
            },
            "input": {
                "type": "string",
                "description": "UTF-8 text to tokenize.",
            },
        },
        "additionalProperties": False,
    },
}

COUNT_TOKENS_SPEC: dict[str, Any] = {
    "name": "count_tokens",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Count how many tokens a supported deterministic Algenta tokenizer model produces "
        "for UTF-8 text (default text.tokenizer; call list_models for every supported model "
        "id). Use this for prompt-size checks and token budgeting; call tokenize when you "
        "also need the token strings. Read-only and deterministic: the same input and model "
        "always return the same count, and nothing is stored. Returns the resolved model "
        "id, its tokenizer_kind, and token_count. An unsupported model id fails with "
        "model_not_supported."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {
                "type": "string",
                "default": "text.tokenizer",
                "description": "Tokenizer model id from list_models.",
            },
            "input": {
                "type": "string",
                "description": "UTF-8 text whose tokens are counted.",
            },
        },
        "additionalProperties": False,
    },
}

CHAT_COMPLETIONS_SPEC: dict[str, Any] = {
    "name": "chat_completions",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Run one ordered chat transcript through an Algenta model and return the assistant "
        "message plus token usage. The default text.tokenizer model is a deterministic "
        "tokenizer-backed utility route whose assistant message is a JSON tokenization "
        "summary of the user messages — not a generative LLM; provider-backed chat models "
        "advertised by list_models are routed through the configured provider service. Use "
        "responses for independent single-string utility calls. This tool does not stream "
        "and does not expose function/tool calling, and nothing is persisted. An "
        "unsupported model id fails with model_not_supported."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["messages"],
        "properties": {
            "model": {
                "type": "string",
                "default": "text.tokenizer",
                "description": "Chat-capable model id from list_models.",
            },
            "messages": {
                "type": "array",
                "minItems": 1,
                "description": (
                    "Ordered conversation transcript; the last user message is the prompt."
                ),
                "items": {
                    "type": "object",
                    "required": ["role", "content"],
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["system", "user", "assistant", "developer"],
                            "description": "Speaker role for this transcript turn.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Text content of this transcript turn.",
                        },
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
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Run the unified Algenta response envelope over one string or a list of independent "
        "strings, each processed as its own single-turn request. The output item per input "
        "depends on the model: tokenization models (default text.tokenizer) return the "
        "input's tokens and token_count; embedding models return a deterministic vector of "
        "dimensions length; provider-backed chat models advertised by list_models return "
        "generated text. Use chat_completions for an ordered multi-role transcript and "
        "embeddings when you specifically need vectors. Stateless and non-destructive: no "
        "conversation state is created, continued, or stored by this tool. An unsupported "
        "model id fails with model_not_supported."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {
                "type": "string",
                "default": "text.tokenizer",
                "description": "Model id from list_models; selects the output item type.",
            },
            "input": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": (
                    "One string, or a list of independent strings each processed as its own "
                    "single-turn request."
                ),
            },
            "dimensions": {
                "type": "integer",
                "default": 64,
                "minimum": 1,
                "maximum": 4096,
                "description": (
                    "Embedding vector length when the selected model produces embeddings."
                ),
            },
        },
        "additionalProperties": False,
    },
}

EMBEDDINGS_SPEC: dict[str, Any] = {
    "name": "embeddings",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Generate one embedding vector per input string (a single string or a list of "
        "strings). The default text.hash_embedding_v1 model produces deterministic lexical "
        "hash embeddings — identical input always yields the identical vector; "
        "provider-backed embedding models advertised by list_models are routed through the "
        "configured provider service. Use embedding_similarity to score two vectors or "
        "rerank to order documents against a query vector. Read-only; nothing is stored. "
        "Returns one {index, embedding, token_count} item per input plus total token usage. "
        "An unsupported model id fails with model_not_supported."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "model": {
                "type": "string",
                "default": "text.hash_embedding_v1",
                "description": "Embedding model id from list_models.",
            },
            "input": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Text to embed: one string, or a list embedded item by item.",
            },
            "dimensions": {
                "type": "integer",
                "default": 64,
                "minimum": 1,
                "maximum": 4096,
                "description": "Length of each returned embedding vector.",
            },
        },
        "additionalProperties": False,
    },
}

EMBEDDING_SIMILARITY_SPEC: dict[str, Any] = {
    "name": "embedding_similarity",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Score the similarity between two caller-supplied embedding vectors with a "
        "supported deterministic metric (default embeddings.cosine_similarity). This tool "
        "does not generate embeddings from text — call embeddings first to produce the "
        "vectors. left and right must have equal length or the call fails with "
        "invalid_embedding_dimensions. Read-only and deterministic. Returns the resolved "
        "model id, similarity_metric, the score, and the shared vector dimension."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["left", "right"],
        "properties": {
            "model": {
                "type": "string",
                "default": "embeddings.cosine_similarity",
                "description": "Similarity model id from list_models; selects the metric.",
            },
            "left": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "number"},
                "description": "First embedding vector; length must equal right's.",
            },
            "right": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "number"},
                "description": "Second embedding vector; length must equal left's.",
            },
        },
        "additionalProperties": False,
    },
}

RERANK_SPEC: dict[str, Any] = {
    "name": "rerank",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Rank caller-supplied document embeddings against a query embedding with a "
        "supported deterministic similarity metric (default embeddings.cosine_similarity), "
        "most relevant first. This tool does not embed text — call embeddings first to "
        "produce the query and document vectors. Every document embedding must share the "
        "query's dimension or the call fails with invalid_embedding_dimensions. Read-only "
        "and deterministic. Returns ranked items with rank (starting at 1) and score, plus "
        "total_documents and returned_documents counts."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["query_embedding", "documents"],
        "properties": {
            "model": {
                "type": "string",
                "default": "embeddings.cosine_similarity",
                "description": "Similarity model id from list_models; selects the metric.",
            },
            "query_embedding": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "number"},
                "description": "Query vector every document embedding is scored against.",
            },
            "documents": {
                "type": "array",
                "minItems": 1,
                "description": "Candidate documents to rank against the query vector.",
                "items": {
                    "type": "object",
                    "required": ["id", "embedding"],
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Caller-assigned document identifier, echoed back.",
                        },
                        "embedding": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "number"},
                            "description": (
                                "Document vector; length must equal query_embedding's."
                            ),
                        },
                        "text": {
                            "type": "string",
                            "description": "Optional document text echoed back in the ranking.",
                        },
                        "metadata": {
                            "type": "object",
                            "description": (
                                "Optional document metadata echoed back in the ranking."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "top_n": {
                "type": "integer",
                "minimum": 1,
                "description": (
                    "Optional cap on how many top-ranked documents are returned; omit to "
                    "return all documents ranked."
                ),
            },
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
