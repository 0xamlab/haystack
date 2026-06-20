# Capability Plane Examples

These files show the canonical customer-agnostic capability-plane surfaces that
Algenta now exposes for providers, bindings, discovery, routing, execution, and
outcome recording.

## Files

- `binding_create_request.json` - request body for `POST /v1/capability-bindings`
- `binding_discover_request.json` - preview request body for `POST /v1/capability-bindings/discover`
- `capability_route_request.json` - request body for `POST /v1/capabilities/route`
- `capability_execute_request.json` - request body for `POST /v1/capabilities/execute`
- `capability_outcome_request.json` - request body for `POST /v1/capabilities/outcomes`

## How to use them

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your own self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

1. Create or reuse one binding before discovery:

```bash
ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"
if [ -z "$ALGENTA_API_KEY" ]; then
  echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example." >&2
  exit 1
fi

ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.algenta.ai}}}"

curl -X POST "${ALGENTA_BASE_URL}/v1/capability-bindings" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/capability-plane/binding_create_request.json
```

The shell snippet above uses the Cloud Managed default when no base URL env var
is set. In `self_hosted` and `air_gapped`, set `ALGENTA_BASE_URL`,
`DE_BASE_URL`, or `ALGENTA_API_URL` explicitly to your self-hosted base URL
before running it.

2. Preview discovery from the same manifest-backed request body:

```bash
curl -X POST "${ALGENTA_BASE_URL}/v1/capability-bindings/discover" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/capability-plane/binding_discover_request.json
```

3. Route one objective through the unified capability plane:

```bash
de capabilities route examples/capability-plane/capability_route_request.json --format json
```

4. Execute one selected capability by canonical capability id:

```bash
de capabilities execute examples/capability-plane/capability_execute_request.json --format json
```

5. Record the observed outcome after the customer-owned execution node or
follow-up workflow completes:

```bash
curl -X POST "${ALGENTA_BASE_URL}/v1/capabilities/outcomes" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/capability-plane/capability_outcome_request.json
```

## Notes

- These checked-in examples intentionally use customer-agnostic provider ids,
  capability ids, and placeholder binding ids.
- For a full LangGraph routing pattern that calls `route_capabilities` before
  branching into specialist nodes, see `examples/langgraph/capability_router.py`.
- `binding_discover_request.json` uses a manifest-backed skill-pack preview so
  the request validates without assuming any app-owned registry.
- `capability_execute_request.json` targets a skill capability because that path
  is Algenta-managed and deterministic: execution returns the instruction
  artifact and instruction text for the selected capability.
- Replace placeholder ids such as `00000000-0000-0000-0000-000000000123` with
  real binding ids returned by your own environment before executing or
  recording outcomes.
