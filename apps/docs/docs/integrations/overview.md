---
sidebar_position: 1
---

# Integrations Overview

Algenta connects to your existing tools with one canonical API contract.

## Supported integrations

| Integration | Type | Use case |
|-------------|------|----------|
| [ChatGPT Actions](/integrations/chatgpt-actions) | AI | Import the Algenta OpenAPI contract into a GPT |
| [Claude and Codex](/integrations/claude-codex) | AI / MCP | Connect via hosted MCP or local stdio bridge |
| [Azure AI Foundry and Studio](/integrations/azure-ai-studio) | AI | Use OpenAPI or function-tool flows from Azure-hosted agents |
| [LangGraph](/integrations/langgraph) | AI | Add decision nodes to your AI agent graphs |
| [n8n](/integrations/n8n) | Automation | No-code workflow automation |
| [Local Runtime](/integrations/local-runtime) | Local | Hosted license, local execution, offline task history |
| [Power Automate](/integrations/power-automate) | Automation | Microsoft 365 / Teams workflows |
| [Zapier](/integrations/zapier) | Automation | Connect 5,000+ apps |
| [Make](/integrations/make) | Automation | Visual scenario builder |

## Base URL

All integrations use: `https://api.algenta.ai`

## Authentication

Add your API key as:
- Header: `Authorization: Bearer de_live_...`
- `X-API-Key: de_live_...` remains available only for legacy `v1` clients

## Recommended starting points

- [ChatGPT Actions](/integrations/chatgpt-actions) for fastest hosted onboarding
- [Claude and Codex](/integrations/claude-codex) for MCP-native agent use
- [n8n](/integrations/n8n) for workflow automation
- [Azure AI Foundry and Studio](/integrations/azure-ai-studio) for Azure-hosted copilots
- [Local Runtime](/integrations/local-runtime) for local execution plus offline history
