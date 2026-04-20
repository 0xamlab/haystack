---
sidebar_position: 3
---

# CLI Reference

The Decision Engine CLI provides a command-line interface for all API operations.

## Installation

```bash
pip install decision-engine-sdk
# or run directly
python apps/cli/main.py
```

## Authentication

Set your API key as an environment variable:

```bash
export DECISION_ENGINE_API_KEY=de_live_...
```

Or pass it per-command:

```bash
de simulate --api-key de_live_... --mode auto ...
```

## Commands

### `simulate`

Run a Monte Carlo simulation.

```bash
# Auto mode
de simulate \
  --mode auto \
  --var revenue 80000 200000 \
  --var cost 30000 90000 \
  --objective maximize_net_value \
  --runs 10000 \
  --seed 42

# Expert mode (from JSON file)
de simulate --file scenario.json
```

**Options:**
| Option | Description |
|--------|-------------|
| `--mode` | `auto` or `expert` |
| `--var NAME LOW HIGH` | Add a variable (auto mode) |
| `--objective` | `maximize_net_value`, `maximize_revenue`, `minimize_cost` |
| `--runs` | Number of simulations (default: 10,000) |
| `--seed` | Random seed for reproducibility |
| `--file` | JSON file with full request payload |
| `--output` | Output format: `table` (default), `json`, `raw` |

### `recommend`

Pick the best action from multiple options.

```bash
de recommend \
  --action "low_risk:80000:120000" \
  --action "high_risk:50000:300000" \
  --objective maximize_net_value
```

### `score`

Score a single scenario (returns 0.0–1.0).

```bash
de score \
  --var revenue 80000 200000 \
  --var cost 30000 90000
```

### `batch`

Run multiple simulations in one call.

```bash
de batch --file batch_scenarios.json
```

### `compare`

Compare named scenarios head-to-head.

```bash
de compare --file compare_scenarios.json
```

### `jobs`

Manage async jobs.

```bash
# Submit a job
de jobs submit --file scenario.json

# Poll status
de jobs status JOB_ID

# Get result
de jobs result JOB_ID

# Cancel
de jobs cancel JOB_ID

# List recent jobs
de jobs list
```

### `keys`

Manage API keys.

```bash
de keys list
de keys create --label production
de keys revoke KEY_ID
```

## Output formats

```bash
# Pretty table (default)
de simulate --mode auto --var revenue 80000 200000

# JSON for scripting
de simulate --mode auto --var revenue 80000 200000 --output json | jq .recommended_action

# Raw API response
de simulate --mode auto --var revenue 80000 200000 --output raw
```
