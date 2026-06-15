"""_LLMMixin for the CodnaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _LLMMixin:
    def tokenize(self, text: str, *, model: str = "text.tokenizer") -> Any:
        return self._sdk_client().tokenize(text, model=model)

    def count_tokens(self, text: str, *, model: str = "text.tokenizer") -> Any:
        return self._sdk_client().count_tokens(text, model=model)

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> Any:
        return self._sdk_client().chat_completions(messages, model=model)

    def stream_chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> Any:
        return self._sdk_client().stream_chat_completions(messages, model=model)

    def responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> Any:
        return self._sdk_client().responses(
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
    ) -> Any:
        return self._sdk_client().stream_responses(
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
    ) -> Any:
        return self._sdk_client().embeddings(
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
    ) -> Any:
        return self._sdk_client().embedding_similarity(left, right, model=model)

    def rerank(
        self,
        query_embedding: list[float],
        documents: list[dict[str, Any]],
        *,
        model: str = "embeddings.cosine_similarity",
        top_n: int | None = None,
    ) -> Any:
        return self._sdk_client().rerank(
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        )

