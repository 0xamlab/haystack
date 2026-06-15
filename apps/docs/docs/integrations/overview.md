---
sidebar_position: 1
---

# Integrations Overview

Codna connects to your existing tools with one canonical API contract.

## Supported integrations

| Integration | Type | Use case |
|-------------|------|----------|
| [ChatGPT Actions](/integrations/chatgpt-actions) | AI | Import the Codna OpenAPI contract into a GPT for discovery, exact query, batch query, SQL reports, persisted runtime follow-up, and control-plane review |
| [Claude and Codex](/integrations/claude-codex) | AI / MCP | Connect via hosted MCP or local stdio bridge for governed data, persisted runtime review, and control-plane tooling |
| [Azure AI Foundry and Studio](/integrations/azure-ai-studio) | AI | Use OpenAPI or function tools for governed discovery, exact query, batch query, SQL reports, and simulation |
| [LangGraph](/integrations/langgraph) | AI | Add Codna discovery, exact-query, persisted runtime review, and simulation tools to your agent graphs |
| [n8n](/integrations/n8n) | Automation | No-code discovery, exact-query, batch-query, SQL-report, simulation, and persisted runtime follow-up workflows |
| [Local Runtime](/integrations/local-runtime) | Local | Hosted license, local execution, offline task history |
| [Power Automate](/integrations/power-automate) | Automation | Microsoft 365 / Teams flows for discovery, exact queries, batch queries, SQL reports, and simulation |
| [Zapier](/integrations/zapier) | Automation | Connect 5,000+ apps with discovery, exact queries, batch queries, SQL reports, simulation, and persisted runtime follow-up workflows |
| [Make](/integrations/make) | Automation | Visual scenario builder for discovery, exact queries, batch queries, SQL reports, simulation, and persisted runtime follow-up workflows |

## Base URL

- Cloud Managed: `https://api.codna.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Codna cloud.

## Live contract discovery

Every integration can start with the same machine-readable contract:

- `GET /v1/meta/contract`

That endpoint tells the caller which discovery, summary, batch, SQL-report,
CLI, and MCP surfaces are available on the running service.

## Unified capability-plane routing

When the integration needs one route-selection layer across governed data, MCP,
skills, native tools, and runtime libraries, start with:

- `POST /v1/capabilities/route`

That route plan can then hand the integration to the correct governed or
customer-managed execution path without app-specific routing headers.

## Authentication

Add your API key as:
- Header: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`
- `X-API-Key: <YOUR_ALGENTA_API_KEY>` remains available only for legacy `v1` clients

## Recommended starting points

- [ChatGPT Actions](/integrations/chatgpt-actions) for fastest hosted onboarding
- [Claude and Codex](/integrations/claude-codex) for MCP-native agent use
- [LangGraph](/integrations/langgraph) when you want a graph node to call `route_capabilities(...)` before branching
- [n8n](/integrations/n8n) for workflow automation
- [Azure AI Foundry and Studio](/integrations/azure-ai-studio) for Azure-hosted copilots
- [Local Runtime](/integrations/local-runtime) for local execution plus offline history
