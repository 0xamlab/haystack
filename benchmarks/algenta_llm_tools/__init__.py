"""LLM tool-calling wrapper over the real, public Algenta Python SDK.

See ``tools.py`` for the three OpenAI-function-calling-compatible tools
(``list_capabilities``, ``execute``, ``explain``) and ``smoke_test.py`` for a real,
end-to-end proof that runs against a compiled Mojo kernel and cross-checks the
answer against pandas.
"""
