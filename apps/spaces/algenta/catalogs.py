"""Static catalogs for the flagship Space — SDK Hub, kernels, MCP surface.

Every entry here is verified against the published artifacts (PyPI/npm pages,
the public GitHub repos, the published `algenta-mcp` wheel, and the
mojo-kernels repo READMEs whose benchmark numbers are reproduced by the
repo's own harness). Live counts (140 tools, 643 runtime modules) are
computed at boot from the real packages — never hardcoded into hero metrics.
"""

from __future__ import annotations

REPOS = {
    "sdk": "https://github.com/thyn-ai/algenta-sdk",
    "integrations": "https://github.com/thyn-ai/algenta-integrations",
    "kernels": "https://github.com/thyn-ai/mojo-kernels",
    "docs": "https://docs.algenta.ai",
    "pypi_sdk": "https://pypi.org/project/algenta-sdk/",
    "npm_sdk": "https://www.npmjs.com/package/algenta-sdk",
    "pypi_mcp": "https://pypi.org/project/algenta-mcp/",
    "pypi_runtime": "https://pypi.org/project/algenta-runtime-native/",
    "pypi_wrapper": "https://pypi.org/project/algenta/",
    "mcp_registry": "https://registry.modelcontextprotocol.io",
    "wheels_release": "https://github.com/thyn-ai/mojo-kernels/releases/tag/arena-wheels-v0.1.0",
    "app": "https://algenta.ai",
}

SPACES = {
    "arena": "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena",
    "modules": "https://huggingface.co/spaces/thyn-ai/algenta-llm-modules",
    "agents": "https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents",
    "governed": "https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls",
}

# ---------------------------------------------------------------------------
# Core packages (SDK Hub cards)
# ---------------------------------------------------------------------------

CORE_PACKAGES = [
    {
        "name": "algenta-sdk",
        "kind": "Python · PyPI",
        "install": "pip install algenta-sdk",
        "what": "Typed client for the whole engine: governed queries, simulations, decision "
        "memory with execution receipts, agent runs, connectors, audit trail. Import name "
        "`decision_engine`; reads ALGENTA_API_KEY.",
        "number": "240 paths on the public OpenAPI contract",
        "url": REPOS["sdk"],
    },
    {
        "name": "algenta-sdk (TypeScript)",
        "kind": "TypeScript · npm",
        "install": "npm install algenta-sdk",
        "what": "The same typed client for Node.js 18+: identical exception taxonomy, retries "
        "and timeouts, plus the local `Runtime` facade.",
        "number": "same 90-day deprecation-window guarantee as Python",
        "url": REPOS["npm_sdk"],
    },
    {
        "name": "algenta-mcp",
        "kind": "Python · PyPI",
        "install": "pip install algenta-mcp  # or: uvx algenta-mcp",
        "what": "MCP server exposing the engine's governed tool surface to Cursor, Claude "
        "Desktop, Codex, n8n and any MCP client — stdio and streamable HTTP.",
        "number": "140 tools · on the official MCP Registry as io.github.thyn-ai/algenta",
        "url": REPOS["pypi_mcp"],
    },
    {
        "name": "algenta + algenta-runtime-native",
        "kind": "Python · PyPI",
        "install": "pip install algenta algenta-runtime-native",
        "what": "The signed local Mojo runtime and its wrapper facade: 643 compute modules "
        "executing in-process (bundled worker over a local socket), manifest signature "
        "verified before first execution. No daemon, no key.",
        "number": "643 modules · 22 of them LLM kernels — all live in the LLM Modules tab",
        "url": REPOS["pypi_runtime"],
    },
]

# ---------------------------------------------------------------------------
# The 10 framework integrations (8 PyPI + 2 npm)
# ---------------------------------------------------------------------------

INTEGRATIONS = [
    (
        "pydantic-ai-algenta",
        "pydantic-ai",
        "pip install pydantic-ai-algenta",
        "Governed WrapperToolset over pydantic-ai's own MCPToolset; denials surface as native ToolDenied.",
    ),
    (
        "langchain-algenta",
        "LangChain / LangGraph",
        "pip install langchain-algenta",
        "Governed tool list on langchain-mcp-adapters; typed receipts; catchable AlgentaExecutionBlocked.",
    ),
    (
        "litellm-algenta",
        "LiteLLM (MCP Gateway)",
        "pip install litellm-algenta",
        "Config generator + linter mapping the contract onto LiteLLM's allowed_tools / allowed_params.",
    ),
    (
        "maf-algenta",
        "Microsoft Agent Framework",
        "pip install maf-algenta",
        "Governed FunctionTool list, two-layer safety-field scrubbing, denials via MAF MiddlewareFailure.",
    ),
    (
        "haystack-algenta",
        "Haystack",
        "pip install haystack-algenta",
        "Governed toolset on Haystack's MCPToolset plus an Agent after_tool governance hook.",
    ),
    (
        "llamaindex-algenta",
        "LlamaIndex",
        "pip install llamaindex-algenta",
        "Governed FunctionTools with typed ExecutionReceipt outputs and named-gate denials.",
    ),
    (
        "ray-serve-algenta",
        "Ray Serve / KubeRay",
        "pip install ray-serve-algenta",
        "Byte-transparent multi-replica reverse proxy for the engine's /mcp surface + RayService manifest.",
    ),
    (
        "vllm-algenta",
        "vLLM / OpenAI-compatible",
        "pip install vllm-algenta",
        "Helpers pointing the standard openai client at the engine's /v1/chat/completions and /v1/responses.",
    ),
    (
        "algenta-tools",
        "Vercel AI SDK (npm)",
        "npm install algenta-tools",
        "Governed ToolSet factory with typed ExecutionReceipt results and ExecutionBlockedError denials.",
    ),
    (
        "n8n-nodes-algenta",
        "n8n (npm)",
        "npm install n8n-nodes-algenta",
        "Community node exposing the governed tools as typed n8n operations, profile-enforced client-side.",
    ),
]

# ---------------------------------------------------------------------------
# Kernel catalog — all 44 Mojo kernel accelerators.
# status: "live"    — wheels on the arena-wheels release / PyPI, raced in the Arena
#         "repo"    — published in thyn-ai/mojo-kernels (35 packages)
#         "wave-3"  — landing on main now; wheels release pending (9 packages)
# Speedups are each package README's own measured claim (Apple M4 Max,
# median-of-5, correctness-gated — reproduce with the repo's benchmarks/).
# ---------------------------------------------------------------------------

KERNELS = [
    # (package, accelerates, README speedup claim, status, headline order)
    ("bm25-mojo", "rank_bm25 / bm25s", "149×–13,137× vs rank_bm25; 1.10×–1.95× vs bm25s", "live"),
    ("vol-mojo", "volatility3 hive walk + pool scan", "2,607× hive walk; 26× pool scan", "live"),
    ("pefile-mojo", "pefile checksum + imports", "300×–460×", "live"),
    ("pykalman-mojo", "pykalman Kalman filter", "182×–827×", "live"),
    ("croniter-mojo", "croniter", "15×–46×", "live"),
    ("ruptures-mojo", "ruptures", "2×–50×", "live"),
    ("oletools-mojo", "oletools VBA decompression", "up to 90× warm", "live"),
    ("cclib-mojo", "cclib electron-density grids", "72×–7,033×", "live"),
    ("pydicom-mojo", "pydicom RLE codec", "3.7×–16.3× decode; 12.2×–46.5× encode", "live"),
    ("motmetrics-mojo", "py-motmetrics", "37×–48×", "live"),
    (
        "nuscenes-eval-mojo",
        "nuscenes-devkit DetectionEval",
        "6.2×–7.0× warm; 13.8×–68.5× cold",
        "live",
    ),
    ("obspy-mojo", "ObsPy Konno-Ohmachi", "3.9×–6.7× steady-state; up to 45×", "live"),
    ("spatialmath-mojo", "spatialmath-python poses", "7.7×–843×", "live"),
    ("elephant-mojo", "elephant surrogates", "218×–342×", "repo"),
    ("uproot-branches-mojo", "uproot branch reads", "172.6× on the branch-read path", "repo"),
    ("metpy-mojo", "MetPy CAPE/CIN", "78× column; 156.6× on grids", "repo"),
    ("jsonpath-mojo", "jsonpath-ng", "28×–49×", "repo"),
    ("jsonschema-mojo", "jsonschema validation", "2.1×–23.6×", "repo"),
    ("sacrebleu-mojo", "sacrebleu BLEU", "~20× n-gram statistics", "repo"),
    ("dynesty-mojo", "dynesty nested sampling", "4.3×–4.5×", "repo"),
    ("langdetect-mojo", "langdetect", "~7×", "repo"),
    ("ta-mojo", "pandas-ta indicators", "1.8×–93×", "repo"),
    ("ase-mojo", "ASE neighbor lists", "~10×", "repo"),
    ("capa-mojo", "capa rule matching", "6×–8× match passes", "repo"),
    ("pymavlink-mojo", "pymavlink tlog decode", "3×–6×", "repo"),
    ("pypdf-filters-mojo", "pypdf image filters", "12×–15×", "repo"),
    ("vader-mojo", "vaderSentiment", "4.1×", "repo"),
    ("bio-mojo", "Biopython SeqIO", "1.4×–2.3×", "repo"),
    ("toml-mojo", "stdlib tomllib", "~1.8×", "repo"),
    ("nx-mojo", "networkx betweenness", "1.2×–2.1× per call (20×–40× kernel-side)", "repo"),
    ("jmespath-mojo", "jmespath", "up to 1.1× (parity-class workloads)", "repo"),
    (
        "fuse-mojo",
        "Fuse.js fuzzy search (TypeScript)",
        "8.8×–38.7× warm; 13× cold; bit-identical",
        "repo",
    ),
    ("natural-mojo", "natural string distance (TypeScript)", "3.7×–7.6×", "repo"),
    ("ckmeans-mojo", "ckmeans (TypeScript)", "1.6×–2.8×", "repo"),
    (
        "minisearch-fuzzy-mojo",
        "MiniSearch fuzzy (TypeScript)",
        "parity-class, profile-driven drop-in",
        "repo",
    ),
    # ---- wave 3: merged on the landing branch, wheels release pending ----
    (
        "ipaddress-mojo",
        "stdlib ipaddress bulk ops",
        "1,663.7× bulk contains (10k×10k); 12×–35× parse",
        "wave-3",
    ),
    (
        "difflib-mojo",
        "stdlib difflib",
        "53.7× ratio() on program text; 16.8× batch close-matches",
        "wave-3",
    ),
    ("msgpack-mojo", "msgpack packb/unpackb", "up to 13.8×", "wave-3"),
    ("jinja2-mojo", "Jinja2 template compilation", "up to 34.1× compile", "wave-3"),
    ("mistune-mojo", "mistune Markdown parse", "~5× single-pass parse", "wave-3"),
    ("slugify-mojo", "python-slugify", "up to 20×", "wave-3"),
    ("statistics-mojo", "stdlib statistics", "15×–53× warm (variance/stdev family)", "wave-3"),
    ("dateutil-mojo", "python-dateutil parse", "~2×–3× parse", "wave-3"),
    ("phonenumbers-mojo", "phonenumbers", "~1.4× parse/validate", "wave-3"),
]

# Top-10 by headline speedup (curated from the catalog above, for SDK Hub).
KERNEL_TOP10 = [
    ("bm25-mojo", "rank_bm25 / bm25s", "13,137×"),
    ("cclib-mojo", "cclib electron-density grids", "7,033×"),
    ("vol-mojo", "volatility3 hive walk", "2,607×"),
    ("ipaddress-mojo", "stdlib ipaddress bulk contains", "1,663.7×"),
    ("spatialmath-mojo", "spatialmath-python poses", "843×"),
    ("pykalman-mojo", "pykalman Kalman filter", "827×"),
    ("pefile-mojo", "pefile checksum", "460×"),
    ("elephant-mojo", "elephant surrogates", "342×"),
    ("uproot-branches-mojo", "uproot branch reads", "172.6×"),
    ("metpy-mojo", "MetPy CAPE/CIN", "156.6×"),
]

WAVE3_PREVIEW = [
    (
        "ipaddress-mojo",
        "stdlib ipaddress",
        "1,663.7×",
        "bulk membership: 10,000 addresses × 10,000 networks — stdlib any() scan 3.494 s → kernel 2.100 ms",
    ),
    (
        "difflib-mojo",
        "stdlib difflib",
        "53.7×",
        "ratio() on 12k-char program text — 127.0 ms → 2.4 ms; batch get_close_matches 16.8×",
    ),
]

# ---------------------------------------------------------------------------
# MCP surface — the categories of the published algenta-mcp registry.
# The tab counts tools live from the imported registry; tests assert the
# union of these lists equals the registry keys exactly (140 tools, 14
# categories — the package's own docstring still says 13; the registry dict
# is authoritative and includes the Repository intelligence group).
# ---------------------------------------------------------------------------

MCP_CATEGORIES: dict[str, list[str]] = {
    "Data onboarding": [
        "onboard_dataset",
        "list_datasets",
        "get_dataset_status",
        "retrain_dataset",
    ],
    "Data access": [
        "connect_data",
        "list_data",
        "get_data_summary",
        "get_data_schema",
        "refresh_data",
        "disconnect_data",
    ],
    "Schema discovery": [
        "register_source",
        "list_sources",
        "get_source_schema",
        "list_connectors",
        "create_connector",
        "get_connector",
        "update_connector",
        "test_connector",
        "browse_connector",
        "preview_test_connector",
        "preview_browse_connector",
        "delete_connector",
    ],
    "Repository intelligence": [
        "get_repository_intelligence_capabilities",
        "create_repository_snapshot",
        "get_repository_snapshot",
        "triage_repository",
        "create_repository_decision_plan",
        "query_repository_graph",
        "simulate_repository",
        "run_repository_pipeline",
        "simulate_repository_patch",
        "run_repository_fix",
        "apply_repository",
    ],
    "Query & ingest": ["query_data", "query_batch", "query_sql_report", "ingest_data"],
    "LLM utilities": [
        "list_models",
        "resolve_artifact_bridge",
        "tokenize",
        "count_tokens",
        "chat_completions",
        "responses",
        "embeddings",
        "embedding_similarity",
        "rerank",
    ],
    "Runtime libraries": ["list_runtime_libraries", "execute_runtime_library"],
    "Capability plane": [
        "list_capability_providers",
        "list_capability_bindings",
        "create_capability_binding",
        "test_capability_binding",
        "discover_capability_binding",
        "list_capabilities",
        "get_capability",
        "route_capabilities",
        "execute_capability",
        "list_skills",
        "enable_skill",
        "disable_skill",
    ],
    "Decisions": [
        "plan_decision",
        "product_decision",
        "product_agent_run",
        "product_optimize",
        "product_retrieve",
        "product_forecast",
        "simulate",
        "recommend",
        "score",
        "batch",
        "compare",
        "submit_job",
        "list_jobs",
        "get_job_status",
        "poll_job",
        "get_job_result",
        "cancel_job",
        "test_webhook_delivery",
    ],
    "Agent runtime": [
        "create_agent_run",
        "list_agent_runs",
        "get_agent_run",
        "get_agent_run_events",
        "get_agent_run_checkpoints",
        "query_agent_run_checkpoints",
        "get_agent_run_mission_events",
        "query_agent_run_mission_events",
        "get_agent_run_telemetry",
        "query_agent_run_telemetry",
        "resume_agent_run",
        "cancel_agent_run",
        "approve_agent_run",
    ],
    "Control plane": [
        "list_deployment_regions",
        "get_deployment",
        "create_deployment",
        "get_deployment_cost",
        "delete_deployment",
        "list_team_members",
        "invite_team_member",
        "update_team_member_role",
        "remove_team_member",
        "list_devices",
        "revoke_device",
        "get_audit_logs",
        "get_audit_log_artifacts",
        "get_execution_policy",
        "list_execution_policy_snapshots",
        "update_execution_policy",
        "get_billing_info",
        "create_billing_checkout",
        "create_billing_portal",
        "refresh_credits",
        "ingest_metering_events",
    ],
    "Observability": [
        "get_contract",
        "get_runtime_manifest",
        "get_runtime_modules",
        "get_runtime_benchmarks",
        "get_runtime_release_validation",
        "get_me",
        "get_limits",
        "list_distributions",
        "list_templates",
        "list_api_keys",
        "create_api_key",
        "update_me",
        "revoke_api_key",
        "list_runs",
        "get_run",
        "get_analytics",
        "get_usage",
    ],
    "Decision Memory": [
        "log_decision",
        "list_decisions",
        "get_decision",
        "execute_decision",
        "delete_decision",
        "record_outcome",
    ],
    "Triggers": [
        "register_trigger",
        "list_triggers",
        "fire_trigger",
        "pause_trigger",
        "delete_trigger",
    ],
}

MCP_CLIENT_CONFIG = """{
  "mcpServers": {
    "algenta": {
      "command": "uvx",
      "args": ["algenta-mcp"],
      "env": {
        "ALGENTA_API_KEY": "<your key>",
        "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}"""
