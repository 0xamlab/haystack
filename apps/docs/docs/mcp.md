---
sidebar_position: 7
---

# MCP

Algenta already exposes a broad MCP surface.

## Current truth

The MCP server in this repo covers more than just queries. It includes tools across:

- source/data operations
- deterministic query operations
- simulation workflows
- memory
- triggers and automation-related operations

## Product guidance

MCP is a first-class supported integration surface, but it is not the top-level product narrative. The primary published contract is still `resolve -> query`.

## When to use MCP

Use MCP when:

- you are integrating Algenta into an agent workflow
- you want structured tool calling
- you want the runtime surfaces available to agent systems without inventing ad hoc wrappers
