# Algenta — Claude Desktop and Codex MCP

Use Algenta from Claude Desktop, Codex, and other MCP clients.

## Recommended split

- Codex and other remote-MCP clients: `https://api.algenta.ai/mcp/sse`
- Claude Desktop local-process hosts: use the bundled stdio bridge below

## Claude Desktop local bridge

Edit your Claude Desktop config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add the Algenta MCP server:

```json
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
        "ALGENTA_API_KEY": "de_live_YOUR_KEY_HERE",
        "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}
```

Then restart Claude Desktop fully.

## Codex and remote MCP clients

Use:

```text
URL: https://api.algenta.ai/mcp/sse
Header: Authorization: Bearer de_live_...
```

Start read-only if your client supports tool scoping.

## Available Tools in Claude

| Tool | Description |
|------|-------------|
| `simulate` | Run a Monte Carlo simulation with any variables and distributions |
| `list_runs` | List recent simulation runs with filters |
| `get_run` | Fetch full details of a specific run |
| `get_analytics` | Analytics: volume, latency, action distribution |
| `get_usage` | Current quota usage vs plan limits |
| `submit_job` | Submit large async simulation (100K+ scenarios) |
| `get_job_status` | Poll async job status |
| `list_connectors` | List configured data connectors |
| `recommend` | Quick recommendation from natural language context |

## Example Conversations

### Simple Business Decision
```
You: Should we invest in expanding our warehouse capacity?
     Current revenue: $800K-$1.5M, expansion cost: $200K-$400K,
     expected demand increase: 15-40%.

Claude: [Uses simulate tool → returns PROCEED/CAUTION/REJECT with confidence %]
```

### Portfolio Risk Analysis
```
You: Run a VaR analysis on a portfolio with 60% equities, 
     30% bonds, 10% alternatives. Use 100,000 scenarios.

Claude: [Uses simulate with expert mode + lhs model → returns VaR, CVaR, percentile distribution]
```

### Drug Development ROI
```
You: What's the expected NPV for our Phase 2 drug trial?
     Success probability: 40-60%, development cost: $50M-$80M,
     peak sales if successful: $300M-$800M.

Claude: [Uses simulate → returns expected NPV, probability of positive ROI, risk metrics]
```

### Check Your Usage
```
You: How many simulations have I run this month?

Claude: [Uses get_usage tool → returns quota consumption and plan details]
```

## Local development

If running the API server locally:

```json
{
  "mcpServers": {
    "algenta-local": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
        "ALGENTA_API_KEY": "de_test_YOUR_TEST_KEY",
        "ALGENTA_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Troubleshooting

**"ALGENTA_API_KEY not set"** — Check the env block in your claude_desktop_config.json has the correct key.

**"API error 401"** — Your API key is invalid or expired. Get a new one at https://app.algenta.ai/dashboard/api-keys

**Tools not appearing** — Restart Claude Desktop fully after editing the config file.

**Connection timeout** — Check your internet connection or try `ALGENTA_BASE_URL=http://localhost:8000` for local testing.
