---
sidebar_position: 12
---

# Competitor Compatibility

This page explains what Algenta intentionally matches, adapts, and rejects in the current developer and agent ecosystem.

## Operating rule

Algenta is not trying to copy competitor architecture.

Compatibility means:

- matching developer expectations where that improves adoption
- matching agent and MCP integration ergonomics where that improves interoperability
- rejecting architectures that conflict with deterministic execution

## Current comparison

| Layer | Vanna | Cube | LlamaIndex | Algenta (today) | Algenta (target) |
| --- | --- | --- | --- | --- | --- |
| SDK | Python-first | JS/API + semantic APIs | Python + TypeScript | Python strong, TypeScript runtime-first plus direct client | clean runtime-first across SDKs |
| MCP | limited | documented MCP server | strong tool/workflow posture | 30-tool MCP surface | first-class |
| Runtime model | LLM/SQL generation | governed semantic layer runtime | agent/workflow framework | hybrid system with deterministic core | deterministic local-first runtime |
| Local-first posture | weak | partial | partial | partial but real | core |
| Determinism | low | high | low | medium-high | high |

## Compatibility decisions

### Vanna

Must match:

- fast Python onboarding
- simple developer ergonomics

Intentional non-match:

- LLM-to-SQL as the primary execution path
- probabilistic query generation as the trust boundary

### Cube

Should match:

- API discipline
- MCP friendliness
- governance-aware integration language

Adapt:

- operational patterns around access and integration

Intentional non-match:

- semantic-model-first product core
- centralized semantic layer as the only execution model

### LlamaIndex

Must match:

- tool and MCP friendliness
- Python and TypeScript developer reach

Adapt:

- orchestration friendliness around external agents

Intentional non-match:

- probabilistic agent-centric execution
- LLM reasoning loops as the execution contract

## What this means for Algenta docs and SDKs

The primary published path stays:

```python
from algenta import Runtime

rt = Runtime()
plan = rt.resolve({...})
result = rt.query(plan)
```

That path should be:

- as easy to start as Vanna
- as disciplined to integrate as Cube
- as tool-friendly as LlamaIndex

without inheriting:

- LLM SQL generation
- semantic-model centralization
- probabilistic execution loops

## Current gaps

The biggest remaining compatibility gap is SDK symmetry:

- Python already has the clean `Runtime` facade
- TypeScript now has a matching `Runtime` surface
- richer ecosystem parity and higher-level examples still need expansion

## Direction

Compatibility work should focus on:

1. primary-path onboarding
2. MCP/tool integration quality
3. TypeScript and Python symmetry
4. local-first trust and deployment clarity

It should not focus on copying competitor execution models.
