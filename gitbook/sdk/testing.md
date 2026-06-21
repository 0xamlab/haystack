---
icon: vial
description: Test Algenta-backed code with the engine's determinism — assert stable decision_hash values, replay recorded runs, mock the HTTP transport, and gate live tests on an API key.
---

# Testing with Algenta

Algenta is a deterministic engine: the same inputs against the same policy and schema snapshots produce the same answer, anchored by a `request_hash` (the canonicalized input) and a `decision_hash` (the resulting decision). That determinism is what makes Algenta-backed code testable. Instead of asserting on a fuzzy LLM string, you assert on hashes that do not move between identical calls, and you replay recorded runs to prove they still reproduce.

This page shows four layers of testing, from fast unit tests that never touch the network up to integration tests that exercise a real engine:

1. **Deterministic assertions** — two identical calls return the same `decision_hash` / `request_hash`.
2. **Replay** — re-execute a recorded agent run and confirm it still matches.
3. **Isolating the network** — mock the HTTP transport so unit tests are fast and offline.
4. **Integration tests** — run against a local or self-hosted engine with a real key, skipped when the key is unset.

{% hint style="info" %}
The hashes are the contract. A changing `request_hash` means your inputs changed (often an unintended serialization difference); a changing `decision_hash` for the same `request_hash` means the policy or schema snapshot moved. Both are exactly what you want a test to catch. See [Governed data & query](../concepts/governed-data.md) for the deterministic, hash-anchored contract.
{% endhint %}

## Deterministic assertions

The core test pattern is: call the engine twice with identical inputs and assert the decision identifiers are stable. A `query` returns a `plan_hash`; a `simulate` returns a `request_hash` and `result_hash`; an agent run returns a `request_hash` and `decision_hash`.

{% tabs %}
{% tab title="Python" %}
```python
import os

from decision_engine import AlgentaClient


def test_agent_run_is_deterministic() -> None:
    client = AlgentaClient(
        api_key=os.environ["ALGENTA_API_KEY"],
        base_url=os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai"),
    )

    payload = {
        "task": "Recommend the lowest-risk rollout for the staging cohort",
        "context": {"cohort": "staging", "risk_budget": 0.2},
        "max_steps": 5,
    }

    first = client.create_agent_run(**payload)
    second = client.create_agent_run(**payload)

    # Same inputs -> same canonicalized request -> same decision.
    assert first.request_hash == second.request_hash
    assert first.decision_hash == second.decision_hash
    assert first.decision_hash is not None
```

`create_agent_run` returns an `AgentRunResult`; the `request_hash` and `decision_hash` fields are the stable anchors. The same shape works for `client.simulate(...)` (assert on `request_hash` / `result_hash`) and `client.query(...)` (assert on `plan_hash`).
{% endtab %}

{% tab title="TypeScript" %}
```typescript
import { describe, expect, it } from "vitest";
import { AlgentaClient } from "algenta-sdk";

describe("agent run determinism", () => {
  it("returns a stable decision_hash for identical inputs", async () => {
    const client = new AlgentaClient({
      apiKey: process.env.ALGENTA_API_KEY,
      baseUrl: process.env.ALGENTA_API_URL ?? "https://api.algenta.ai",
    });

    const request = {
      task: "Recommend the lowest-risk rollout for the staging cohort",
      context: { cohort: "staging", risk_budget: 0.2 },
      max_steps: 5,
    };

    const first = await client.createAgentRun(request);
    const second = await client.createAgentRun(request);

    expect(first.request_hash).toBe(second.request_hash);
    expect(first.decision_hash).toBe(second.decision_hash);
    expect(first.decision_hash).toBeTruthy();
  });
});
```

`createAgentRun` resolves to an `AgentRunResponse` carrying `request_hash` and `decision_hash`. Use the same approach with `client.simulate(...)` and `client.query(...)`.
{% endtab %}
{% endtabs %}

**Expected result:** both calls return the same `decision_hash` (and the same `request_hash`), so the assertion passes. Your test is reproducible: a future code or policy change that perturbs the decision flips a hash and fails the test loudly, instead of drifting silently.

## Replay a recorded run

Determinism also lets you verify a run *after the fact*. `replay_agent_run` / `replayAgentRun` re-executes a recorded run from a checkpoint and compares the new execution against what was stored. The result reports `replay_status` of either `"matched"` (the run reproduced byte-for-byte) or `"mismatch"`, along with the `request_hash` and `decision_hash` it recomputed.

This is the strongest reproducibility check: it proves the recorded inputs, the snapshots, and the engine still produce the same decision.

{% tabs %}
{% tab title="Python" %}
```python
import os

from decision_engine import AlgentaClient


def test_recorded_run_replays_identically() -> None:
    client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

    run = client.create_agent_run(
        task="Recommend the lowest-risk rollout for the staging cohort",
        context={"cohort": "staging", "risk_budget": 0.2},
        max_steps=5,
    )
    assert run.replayable

    replay = client.replay_agent_run(run.run_id)

    assert replay.replay_status == "matched"
    assert replay.decision_hash == run.decision_hash
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
import { describe, expect, it } from "vitest";
import { AlgentaClient } from "algenta-sdk";

describe("agent run replay", () => {
  it("replays a recorded run to a matching decision", async () => {
    const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });

    const run = await client.createAgentRun({
      task: "Recommend the lowest-risk rollout for the staging cohort",
      context: { cohort: "staging", risk_budget: 0.2 },
      max_steps: 5,
    });
    expect(run.replayable).toBe(true);

    const replay = await client.replayAgentRun(run.run_id);

    expect(replay.replay_status).toBe("matched");
    expect(replay.decision_hash).toBe(run.decision_hash);
  });
});
```
{% endtab %}
{% endtabs %}

**Expected result:** `replay_status` is `"matched"` and the replayed `decision_hash` equals the original, confirming the run reproduces. A `"mismatch"` means something the run depended on changed — a snapshot bump, a non-deterministic tool, or altered stored state — and your test catches it. Pass `checkpoint_id` to replay from a specific point in the run.

## Isolate the network in unit tests

Unit tests should be fast and offline. The HTTP transport is the seam to stub. The clients are built so you can replace the network without monkeypatching internals.

In Python, the client constructs a lazy `httpx` transport once, exposed as the `_client` attribute (`AlgentaClient(...)._client`); every method routes requests through it. In TypeScript, the client calls the global `fetch`, so you stub `fetch`. In both cases, prefer pinning `base_url` / `baseUrl` to a local test server, or stub the transport directly for pure unit tests.

{% tabs %}
{% tab title="Python (pytest)" %}
```python
from types import SimpleNamespace

import httpx
import pytest

from decision_engine import AlgentaClient


class _FakeTransport:
    """Stand-in for the client's httpx transport seam (client._client)."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        return httpx.Response(200, json=self._payload)

    def close(self) -> None:  # called by client.close()
        pass


@pytest.fixture()
def stubbed_client() -> AlgentaClient:
    client = AlgentaClient(api_key="de_test_unit", base_url="http://test.local")
    client._client = _FakeTransport(
        {
            "run_id": "run_test_1",
            "status": "completed",
            "task": "demo",
            "output_format": "text",
            "approval_mode": "auto",
            "request_hash": "req_abc",
            "decision_hash": "dec_xyz",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    return client


def test_decision_hash_surfaced_without_network(stubbed_client: AlgentaClient) -> None:
    run = stubbed_client.create_agent_run(task="demo", max_steps=1)
    assert run.decision_hash == "dec_xyz"
    assert run.request_hash == "req_abc"
```

Assigning to `client._client` replaces the real `httpx.Client` with a fake that returns a canned `httpx.Response`, so no socket is opened. For a higher-fidelity test, run a local stub server and pass its address as `base_url=` instead.
{% endtab %}

{% tab title="TypeScript (vitest)" %}
```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import { AlgentaClient } from "algenta-sdk";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createAgentRun without network", () => {
  it("surfaces the decision_hash from a stubbed fetch", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          run_id: "run_test_1",
          status: "completed",
          task: "demo",
          output_format: "text",
          approval_mode: "auto",
          request_hash: "req_abc",
          decision_hash: "dec_xyz",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new AlgentaClient({
      apiKey: "de_test_unit",
      baseUrl: "https://test.local",
      maxRetries: 0,
    });

    const run = await client.createAgentRun({ task: "demo", max_steps: 1 });

    expect(run.decision_hash).toBe("dec_xyz");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://test.local/v1/agent/runs",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
```

`vi.stubGlobal("fetch", ...)` replaces the global `fetch` the client calls, so the request never leaves the process. Setting `maxRetries: 0` keeps a failing test from waiting on the retry backoff.
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
Use a clearly fake `base_url` (for example `http://test.local`) in unit tests so a misconfigured stub can never accidentally reach a real endpoint. Keep the default `https://api.algenta.ai` only for integration tests with a real key.
{% endhint %}

## Integration tests against a real engine

Unit tests with a stubbed transport prove your code wires the SDK correctly; integration tests prove the engine actually returns what you expect. Point the client at a local or self-hosted engine, read the key from `ALGENTA_API_KEY`, and **gate the test so it skips when the key is unset** — that keeps the suite green on machines without credentials.

{% tabs %}
{% tab title="Python (pytest)" %}
```python
import os

import pytest

from decision_engine import AlgentaClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("ALGENTA_API_KEY"),
    reason="ALGENTA_API_KEY not set; skipping live engine integration test",
)


def test_live_engine_round_trip() -> None:
    client = AlgentaClient(
        api_key=os.environ["ALGENTA_API_KEY"],
        base_url=os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai"),
    )

    run = client.create_agent_run(task="health check", max_steps=1)

    assert run.decision_hash is not None
    assert run.request_hash is not None
```
{% endtab %}

{% tab title="TypeScript (vitest)" %}
```typescript
import { describe, expect, it } from "vitest";
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY;

// skip() the whole block when no key is present.
describe.skipIf(!apiKey)("live engine integration", () => {
  it("returns hashes from a real engine", async () => {
    const client = new AlgentaClient({
      apiKey,
      baseUrl: process.env.ALGENTA_API_URL ?? "https://api.algenta.ai",
    });

    const run = await client.createAgentRun({ task: "health check", max_steps: 1 });

    expect(run.decision_hash).toBeTruthy();
    expect(run.request_hash).toBeTruthy();
  });
});
```
{% endtab %}
{% endtabs %}

**Expected result:** with `ALGENTA_API_KEY` exported, the test runs against the engine and the run returns non-null `request_hash` and `decision_hash`; without it, the test is reported as skipped rather than failed. Set `ALGENTA_API_URL` to your self-hosted engine to keep the test fully on your own infrastructure.

{% hint style="info" %}
For self-hosted and air-gapped deployments, use the API key your operator deployment provisions and pin `ALGENTA_API_URL` to the in-network engine. Private profiles fail closed and never fall back to Algenta cloud. See [Run Algenta air-gapped](../guides/air-gapped.md).
{% endhint %}

## Next steps

* [Python SDK](../sdk/python.md) — full method surface and configuration for the synchronous and async clients.
* [TypeScript SDK](../sdk/typescript.md) — the fetch-based client, types, and streaming helpers.
* [Agent runs](../guides/agent-runs.md) — create, replay, fork, and checkpoint agentic runs in depth.
* [Decision memory](../concepts/decision-memory.md) — how recorded decisions, hashes, and receipts anchor reproducibility.
* [Governed data & query](../concepts/governed-data.md) — the deterministic, hash-anchored contract behind every query and decision.
