---
icon: diagram-project
description: Every outbound network call the engine can make is classified into one of five categories and gated by deployment mode — plus what the SSRF guard blocks unconditionally.
---

# Data boundaries

For how to read, tighten, and audit this policy on a running deployment, see
[Audit and tighten egress](../operate/privacy-egress.md). This page states the control, not the
procedure.

## Every outbound call is classified before it is allowed

The engine does not have a single "outbound network on/off" switch. Every attempted egress is
classified into exactly one of five classes, and each class is gated independently:

| Class | What it is | Gated by |
| --- | --- | --- |
| `algenta_cloud` | Calls to Algenta-owned infrastructure | `disable_cloud` + outbound network allowed |
| `vendor_telemetry` | Opt-in usage telemetry | `disable_telemetry` + `telemetry_mode` + outbound network allowed |
| `customer_connector` | A connector or integration you explicitly configured | Your own configuration; not blanket-gated |
| `operator_service` | Infra you pointed the engine at (your own Postgres, Redis, S3-compatible store) | Not blanket-gated — this is traffic you asked for |
| `undeclared_public` | Anything else | The outbound-network switch alone |

A destination's class is derived from the destination itself (is it an Algenta-owned host? a
known vendor-telemetry host? explicitly configured?) — never from which code path is asking, so a
call cannot claim a more permissive class than its actual destination warrants.

## Deployment mode sets the defaults, not the ceiling

`self_hosted` and `air_gapped` deployments default every outbound-network-gated class to off.
`air_gapped` additionally refuses to start if telemetry or metering is configured for
control-plane sync — that combination is rejected at configuration time, not silently ignored.
`saas` and `vpc`/`hybrid_provider` modes carry different defaults appropriate to how Algenta
operates them. In every mode, the defaults are configuration, not a hard limit — see
[Audit and tighten egress](../operate/privacy-egress.md) for how to change them, and
`GET /v1/admin/privacy-report` for what is actually in effect on a running instance right now.

## The SSRF guard blocks a specific set of addresses unconditionally

Independent of egress class or deployment mode, an outbound call is refused outright — no
allowlist entry, no configuration, can override this — when its destination resolves to:

- Link-local space (`169.254.0.0/16`), including cloud metadata endpoints
  (`169.254.169.254`, and the IPv6 forms that smuggle it — an IPv4-mapped address, the NAT64
  embedding, and the explicit AWS IPv6 metadata address `fd00:ec2::254`)
- Multicast or unspecified addresses

Private and loopback addresses (an internal `10.x` sidecar, `::1`) are treated differently: they
are legitimate when explicitly allowlisted (your own Postgres is exactly this shape), so they stay
gated by your configuration rather than blocked unconditionally — the metadata-endpoint case above
is the one where even an allowlisted destination must not be reachable through it.

## Air-gapped means air-gapped

An `air_gapped` deployment that is also configured for `control_plane_sync` telemetry or metering
refuses to start. This is enforced at configuration validation, not left as a runtime toggle that
could be flipped without anyone noticing — the two settings are mutually exclusive by
construction.

## Next steps

- [Audit and tighten egress](../operate/privacy-egress.md)
- [Trust overview](overview.md)
