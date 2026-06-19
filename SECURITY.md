# Security Policy

Algenta is a self-hosted decision engine. We take the security of the engine,
its SDKs, and its API/MCP surface seriously and appreciate responsible
disclosure from the community.

## Supported versions

Algenta is distributed as a rolling, source-available engine rather than as
long-lived numbered branches. Security fixes land on `main` and in the latest
published release of each artifact (the API/worker images, the Python and
TypeScript SDKs, and the `algenta-mcp` package).

| Channel | Supported |
| --- | --- |
| Latest release / `main` | :white_check_mark: |
| Older tagged releases | Best-effort; please upgrade to the latest |

If you self-host, run the latest release to receive security fixes.

## Reporting a vulnerability

**Please do not open a public issue, pull request, or discussion for security
problems.** Public disclosure before a fix is available puts other users at
risk.

Report privately through either channel:

1. **GitHub Security Advisories** (preferred) — open a private report from the
   repository's **Security → Report a vulnerability** tab. This keeps the
   discussion private and lets us collaborate on a fix and a coordinated
   release.
2. **Email** — `security@algenta.ai`. Encrypt sensitive details if you can; we
   will provide a secure channel if needed.

Please include, where possible:

- A description of the issue and its impact.
- The affected component (API server, worker, Python/TypeScript SDK, MCP
  server, or a specific endpoint/tool).
- Steps to reproduce or a proof of concept.
- The version, commit, or release you tested, and your deployment mode
  (Cloud Managed, self-hosted, or air-gapped).

## What to expect

- **Acknowledgement** within 3 business days.
- An initial assessment and severity triage within 7 business days.
- Regular updates as we work on a fix, and credit in the published advisory
  (unless you prefer to remain anonymous).
- Coordinated disclosure: we agree on a timeline with you and publish a GitHub
  Security Advisory once a fix is available.

## Scope

In scope: the Algenta engine and its first-party surfaces in this repository —
the API server, worker, Python SDK, TypeScript SDK, MCP server, and the
governed-execution / decision pipeline.

Out of scope: third-party dependencies (report those upstream; we still want to
hear how they affect Algenta), and social-engineering, physical, or
denial-of-service testing against any hosted environment.

Thank you for helping keep Algenta and its users safe.
