#!/usr/bin/env bash
set -euo pipefail

# Keep SDK/client contract tests hermetic even when the parent shell loads a
# live `.env` for integration or proof collection. These tests intentionally
# assert missing-key and missing-self-hosted-baseUrl behavior.
unset ALGENTA_API_KEY
unset DE_API_KEY
unset ALGENTA_BASE_URL
unset DE_BASE_URL
unset ALGENTA_API_URL
unset ALGENTA_APP_BASE_URL
unset APP_BASE_URL
unset DE_APP_BASE_URL
unset ALGENTA_DEPLOYMENT_MODE
unset ALGENTA_DISABLE_CLOUD
unset ALGENTA_RUNTIME_DIR
unset ALGENTA_DEVICE_ID
unset DE_DEVICE_ID

# The ts-sdk `test` script is `tsc && vitest run`, so `pnpm test -- --run <files>` appended the
# filters AFTER `vitest run` had already been composed -- vitest never received them and ran the
# WHOLE suite: 46 files, not the 3 named here (confirmed in CI logs, "Test Files 4 failed | 42
# passed (46)"). That accident was providing real coverage, and the 4 failures were contention
# against vitest's default 5s timeout, not broken tests. So the full suite is kept DELIBERATELY
# and invoked via `exec` so arguments reach vitest directly if it is ever narrowed again.
# --testTimeout is passed on the COMMAND LINE, not via vitest.config.ts, on purpose: a config
# file has to `import { defineConfig } from "vitest/config"`, and if that ever fails to resolve
# vitest exits with a config error instead of running -- trading a flaky timeout for a hard
# failure. The flag has no resolution path to break.
#
# 30s is ~150x the ~180ms these tests actually take locally. It absorbs worker contention on
# cold ephemeral CI filesystems while still failing a genuine deadlock. Vitest's default is
# 5000ms, which silently assumes an unloaded developer machine: on the Azure workers the SAME
# commit produced 1 timeout at 14:15 and 4 at 15:22 -- non-deterministic, i.e. starvation.
pnpm --dir packages/ts-sdk exec tsc
pnpm --dir packages/ts-sdk exec vitest run --testTimeout=30000 --hookTimeout=30000
pnpm --dir apps/gateway test
pnpm --dir apps/gateway exec tsx --test ../../examples/shared/privacyProfile.test.ts

# agent-core (sidecar) overlay tests now live in thyn-ai/codna (its CI builds + tests the
# vendored Cline SDK). decision-engine consumes the published sidecar image over HTTP.
