"""Algenta for LLM Agents — interactive demo handlers.

Every tab runs locally in the Space with zero API keys:

* RAG retrieval duel: rank_bm25 vs bm25-mojo over a vendored synthetic corpus.
* LLM output scorer: sacrebleu-mojo vs the reference sacrebleu package.
* Prompt-injection governance duel + MCP playground: a deterministic,
  simulated engine replicating the real API's wire shapes (same field names
  as the receipts returned by `algenta-mcp` and the hosted API).

Native Mojo kernels are imported lazily; when a native kernel is unavailable
the affected measurement is *held* with an explanation rather than silently
benchmarking a fallback as "mojo" (same rule as the Algenta Speed Arena).
"""
