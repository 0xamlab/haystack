# Algenta MCP Server

**Model Context Protocol (MCP)** bridge for the Algenta decision engine. Connects any AI chatbot or agent framework to Monte Carlo simulations, decision analytics, and your data connectors.

## Tools Available

| Tool | Description |
|------|-------------|
| `simulate` | Run a Monte Carlo simulation (auto or expert mode). Returns PROCEED/DELAY/REJECT/HEDGE with confidence + rationale. |
| `list_runs` | List recent simulation runs with status/mode filters. |
| `get_run` | Fetch the full decision envelope for a specific run by ID. |
| `get_analytics` | Daily volume, P95 latency, action distribution, mode breakdown. |
| `get_usage` | Current billing period usage vs quota, rate limits. |
| `submit_job` | Submit a large async simulation (100K+ scenarios) with optional webhook. |
| `get_job_status` | Poll an async job; returns full result when complete. |
| `list_connectors` | List configured data connectors and their health status. |
| `recommend` | Quick decision recommendation from business context. |

---

## Prerequisites

```bash
pip install mcp httpx structlog
```

Set your API key:
```bash
export ALGENTA_API_KEY="de_live_your_key_here"
export ALGENTA_BASE_URL="https://api.algenta.ai"   # default
```

Get your API key: **https://app.algenta.ai/dashboard/api-keys**

---

## Connection Guide by Platform

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
          "ALGENTA_API_KEY": "de_live_your_key_here",
          "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see "algenta" in the tools panel. Try:
> *"Run a simulation: revenue $500K, cost $300K, growth rate 15%"*

---

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
        "ALGENTA_API_KEY": "de_live_your_key_here"
      }
    }
  }
}
```

Then in Cursor chat: *"@algenta simulate this business case..."*

---

### Zed Editor

Add to `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "algenta": {
      "command": {
        "path": "python",
        "args": ["-m", "apps.mcp_server.server"],
        "env": {
          "ALGENTA_API_KEY": "de_live_your_key_here"
        }
      }
    }
  }
}
```

---

### HTTP/SSE Transport (Remote Agents)

Start the HTTP server:

```bash
python -m apps.mcp_server.server --transport http --port 8001

# Or via environment variable:
ALGENTA_MCP_PORT=8001 python -m apps.mcp_server.server --transport http
```

Or if you have the Algenta API server running, the MCP is already mounted at:
- **`GET  /mcp/sse`** — SSE connection endpoint
- **`POST /mcp/messages`** — Message handler
- **`GET  /mcp/tools`** — List tools (JSON, no auth needed)

---

### n8n

1. Add an **MCP Client** node
2. Set **Transport**: `SSE`
3. Set **URL**: `https://api.algenta.ai/mcp/sse`
4. Set **Header**: `Authorization: Bearer de_live_your_key_here`

Example workflow: *Trigger → Algenta Simulate → Send Slack notification with recommendation*

---

### LangChain / LangGraph

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "algenta": {
        "url": "http://localhost:8001/mcp/sse",
        "transport": "sse",
    }
})

tools = await client.get_tools()

# Use with any LangChain agent
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(model="claude-3-5-sonnet", tools=tools)

result = await agent.ainvoke({
    "messages": [{
        "role": "user",
        "content": "Run a simulation with revenue=500000, cost=300000, growth_rate=0.15"
    }]
})
```

---

### LlamaIndex

```python
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

client = BasicMCPClient("http://localhost:8001/mcp/sse")
spec = McpToolSpec(client=client)
tools = spec.to_tool_list()

from llama_index.agent.openai import OpenAIAgent
agent = OpenAIAgent.from_tools(tools, verbose=True)
response = agent.chat("Should we proceed with the EMEA expansion? Revenue projection $800K.")
```

---

### OpenAI Assistants (Custom GPT / Function Calling)

The `/mcp/tools` endpoint returns tools in OpenAI-compatible format. You can also use any MCP→OpenAI bridge:

```python
import httpx, json

# Get tools list
tools = httpx.get("https://api.algenta.ai/mcp/tools").json()["tools"]

# Call a tool directly via HTTP
result = httpx.post(
    "https://api.algenta.ai/v1/simulate",
    headers={"Authorization": "Bearer de_live_your_key_here"},
    json={"mode": "auto", "trials": 10000, "inputs": {"revenue": 500000, "cost": 300000}}
)
```

---

### AutoGen / Microsoft Autogen

```python
import autogen
from autogen.agentchat.contrib.mcp_agent import MCPAgent

config = {
    "mcp_server_url": "http://localhost:8001/mcp/sse",
}

algenta_agent = MCPAgent(
    name="AlgentaDecisionAgent",
    system_message="You help make data-driven decisions using Monte Carlo simulations.",
    mcp_config=config,
)
```

---

### Direct Python (no MCP client)

```python
import httpx

API_KEY = "de_live_your_key_here"
BASE = "https://api.algenta.ai"

# Run a simulation
resp = httpx.post(
    f"{BASE}/v1/simulate",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "mode": "auto",
        "trials": 10000,
        "inputs": {
            "revenue": 500000,
            "cost": 300000,
            "growth_rate": 0.15,
            "churn_rate": 0.05,
        }
    }
)
result = resp.json()
print(f"Recommendation: {result['recommended_action']} ({result['confidence']:.0%})")
print(f"Rationale: {result['rationale']}")
```

---

## Example Prompts for AI Assistants

Once connected, you can ask natural language questions:

> *"Run a simulation for a SaaS business: revenue $1.2M, costs $800K, monthly growth 12%, churn 3%"*

> *"What does our decision analytics look like for the past 30 days?"*

> *"Submit a large job with 500K trials for our Q3 financial planning model"*

> *"Check my API usage — how many simulations do I have left this month?"*

> *"List my recent simulation runs and show me the ones that recommended REJECT"*

> *"Get the full details of run abc-123 and explain the rationale"*

---

## Deployment (Docker)

Add to your `docker-compose.yml`:

```yaml
mcp-server:
  build:
    context: .
    dockerfile: infra/docker/Dockerfile.api.prod
  command: python -m apps.mcp_server.server --transport http --port 8001
  environment:
    ALGENTA_API_KEY: ${ALGENTA_API_KEY}
    ALGENTA_BASE_URL: http://api-server:8000
  ports:
    - "8001:8001"
  depends_on:
    - api-server
```

---

## Security Notes

- The stdio transport runs locally — API key is only in your environment
- The HTTP transport authenticates downstream to the Algenta API with your key
- Add your own authentication layer (API gateway / Nginx) in front of the MCP HTTP port in production
- The `/mcp/tools` list endpoint on the FastAPI server is public (no sensitive data)
- All actual tool calls require `ALGENTA_API_KEY` to be set

---

## Troubleshooting

**`ALGENTA_API_KEY environment variable is not set`**
→ Set `export ALGENTA_API_KEY=de_live_...` before running

**`mcp package not installed`**
→ Run `pip install mcp`

**`API error 401: Unauthorized`**
→ Check your API key is valid at https://app.algenta.io/dashboard/api-keys

**`API error 429: Rate limit exceeded`**
→ You're over your plan's requests/minute limit. Upgrade or space out calls.

**Tool not showing in Claude Desktop**
→ Check the JSON config syntax, restart Claude Desktop, look for errors in `~/Library/Logs/Claude/`
