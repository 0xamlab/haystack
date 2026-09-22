---
title: Algenta Governed Tool Calls
emoji: 🛡️
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: 6.28.0
app_file: app.py
pinned: false
fullWidth: true
header: mini
thumbnail: https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls/resolve/main/social.png
license: apache-2.0
tags:
  - mcp
  - agents
  - governance
  - smolagents
short_description: Governed tool calls with execution receipts
---

# Algenta — governed tool calls for AI agents

Interactive demo of the governance semantics of the [Algenta](https://github.com/thyn-ai/algenta-sdk)
decision engine SDK (Apache-2.0), built by [thyn-ai](https://github.com/thyn-ai).

- Tool profiles `observe` / `govern` / `execute` / `full` control which tools a model ever sees.
- `execute_decision` either returns a signed-shape **execution receipt** or is blocked
  synchronously on one of three named policy gates — `idempotency`, `confidence`, `risk_floor` —
  with a structured denial body.
- Every outcome is appended to a visible audit log.

This Space runs a deterministic, simulated engine using the real API's wire shapes, so it needs
no API key. The production paths:

- [`algenta-mcp`](https://pypi.org/project/algenta-mcp/) — MCP server (PyPI), also on the
  official MCP Registry as `io.github.thyn-ai/algenta`; consumable from smolagents via
  `ToolCollection.from_mcp(...)` (see the "Use from smolagents" tab).
- [`algenta-sdk`](https://pypi.org/project/algenta-sdk/) — Python SDK; `algenta-sdk` on npm for TypeScript.
- [`thyn-ai/algenta-integrations`](https://github.com/thyn-ai/algenta-integrations) — LangChain,
  LlamaIndex, pydantic-ai, Microsoft Agent Framework, Haystack, LiteLLM, Ray Serve, vLLM,
  Vercel AI SDK, n8n.

Affiliation: this Space is published and maintained by thyn-ai, the author of the Algenta SDK.
