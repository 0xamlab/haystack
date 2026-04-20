"""Generated from apps/docs/integration_manifest.v1.json by scripts/generate_platform_contract_artifacts.py."""

CONTRACT_VERSION = 'v1.2'
BRAND = 'Algenta'
API_BASE_URL = 'https://api.algenta.ai'
MCP_ENDPOINT = 'https://api.algenta.ai/mcp/sse'
MCP_TOOLS_ENDPOINT = 'https://api.algenta.ai/mcp/tools'
AUTH_SCHEME = 'bearer_api_key'
API_KEY_PREFIX_LIVE = 'de_live_'
API_KEY_PREFIX_TEST = 'de_test_'
LEGACY_HEADERS = ('X-API-Key',)
LEGACY_ENV_VARS = ('DE_API_KEY', 'DE_BASE_URL')
LEGACY_DOMAINS = ('api.algenta.io', 'api.decisionengine.io')
DEPRECATION_WINDOW_DAYS = 90
PLAN_LIMITS = {'free': {'requests_per_minute': 60, 'simulations_per_month': 500},
 'developer': {'requests_per_minute': 300, 'simulations_per_month': 10000},
 'pro': {'requests_per_minute': 1000, 'simulations_per_month': 100000},
 'enterprise': {'requests_per_minute': 10000, 'simulations_per_month': 'unlimited'}}
