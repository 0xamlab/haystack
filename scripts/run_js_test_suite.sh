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

pnpm --dir packages/ts-sdk test -- --run src/libraries.test.ts src/runtime_daemon_client.test.ts src/index.test.ts
pnpm --dir apps/gateway test
pnpm --dir apps/gateway exec tsx --test ../../examples/shared/privacyProfile.test.ts

# agent-core (sidecar) overlay tests now live in escrypto-labs/codna (its CI builds + tests the
# vendored Cline SDK). decision-engine consumes the published sidecar image over HTTP.
