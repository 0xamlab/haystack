Mission Algenta SDK Parity Plan

Scope

- Repo audited: `/Users/angel/Developer/mission`
- Upstream contract source: `/Users/angel/Developer/decision-engine/packages/ts-sdk`
- Goal: bring Mission's vendored `algenta-sdk` and Mission wrapper/config layer into parity with the current private-profile and self-hosted SDK contract.

What is already good

- Mission centralizes most direct SDK usage through `lib/algenta-sdk-client.ts`.
- Mission has source guards preventing broad direct imports and raw endpoint drift.
- Mission's local Mojo/library path is isolated separately from the HTTP client path.

Main drift

- Mission's vendored SDK does not currently include the upstream `privacy_profile.ts` fail-closed layer.
- Mission's vendored client still defaults to `https://api.algenta.ai` without private-profile rejection.
- Mission's app-level config only reads `ALGENTA_BASE_URL` and `ALGENTA_API_KEY`, not the full alias set now supported upstream.

Recommended patch set

1. `/Users/angel/Developer/mission/packages/algenta-sdk/src/contract.ts`

- Regenerate or port the current upstream generated contract constants from:
  - `/Users/angel/Developer/decision-engine/packages/ts-sdk/src/contract.ts`
- Minimum fields Mission needs to add:
  - `ALGENTA_OWNED_HOSTS`
  - `ALGENTA_OWNED_SUFFIXES`
  - `PRIVATE_HOST_SUFFIXES`
  - `VENDOR_TELEMETRY_HOSTS`
- Keep existing `DEFAULT_BASE_URL`, `LEGACY_ENV_VARS`, and other generated contract constants aligned.

Why

- The upstream privacy helper depends on those constants to reject Algenta-owned cloud URLs in `self_hosted` and `air_gapped`.

2. `/Users/angel/Developer/mission/packages/algenta-sdk/src/privacy_profile.ts`

- Add the upstream file, or port it nearly verbatim, from:
  - `/Users/angel/Developer/decision-engine/packages/ts-sdk/src/privacy_profile.ts`
- Preserve these exported helpers:
  - `cloudDisabled()`
  - `privateProfileEnabled()`
  - `normalizeBaseUrl()`
  - `isAlgentaOwnedBaseUrl()`
  - `resolveClientBaseUrl()`
  - `resolveConsoleBaseUrl()`
  - `resolveApiKeysUrl()`
  - `apiKeyHelpText()`

Why

- This is the current upstream TS SDK contract for private-profile and self-hosted fail-closed behavior.

3. `/Users/angel/Developer/mission/packages/algenta-sdk/src/client.ts`

- Replace direct `DEFAULT_BASE_URL` fallback in the constructor with `resolveClientBaseUrl(...)`.
- Import from the new `privacy_profile.ts`:
  - `resolveClientBaseUrl`
  - `apiKeyHelpText`
- Keep the current env API key lookup if desired, but base URL resolution should become:
  - explicit `config.baseUrl`
  - env aliases `ALGENTA_BASE_URL`, `DE_BASE_URL`, `ALGENTA_API_URL`
  - reject Algenta-owned cloud URLs when `ALGENTA_DEPLOYMENT_MODE` is `self_hosted` or `air_gapped`, or when `ALGENTA_DISABLE_CLOUD=1`
- Update the top-of-file examples/comments to match the upstream wording:
  - Cloud Managed is explicit
  - `self_hosted` and `air_gapped` must use self-hosted `baseUrl`
  - private profiles fail closed and do not silently fall back to Algenta cloud

Why

- This is the most important correctness fix. Today Mission's vendored client can still silently point at cloud defaults if the caller forgets to inject the right base URL.

4. `/Users/angel/Developer/mission/packages/algenta-sdk/src/runtime.ts`

- Port the upstream privacy/base-url checks into the hosted/runtime path.
- Keep the existing Mission-specific local daemon behavior, but align these seams:
  - `Runtime({ mode: "self_hosted" })` requires explicit `baseUrl`
  - private profiles reject Algenta-owned control-plane URLs
  - control-plane URL resolution should honor:
    - `ALGENTA_CONTROL_PLANE_URL`
    - `ALGENTA_BASE_URL`
    - `DE_BASE_URL`
    - explicit `baseUrl`
  - when private-profile mode is active, do not silently fall back to `DEFAULT_BASE_URL`

Why

- Mission runtime already enforces some of this, but the vendored runtime still has weaker base URL defaults than current upstream.

5. `/Users/angel/Developer/mission/lib/algenta-config.ts`

- Expand env alias support at the wrapper/config layer:
  - `getAlgentaBaseUrl()` should check, in order:
    - `ALGENTA_BASE_URL`
    - `DE_BASE_URL`
    - `ALGENTA_API_URL`
    - then Mission's local default `http://localhost:8000`
  - `getAlgentaApiKey()` should check:
    - `ALGENTA_API_KEY`
    - `DE_API_KEY`
- Preserve Mission's local-dev default behavior for non-private/local flows.
- Do not silently force cloud defaults here.

Why

- Mission wrappers currently centralize SDK usage through this helper, so if it stays narrow, Mission will remain stricter than before in some paths and looser than upstream in others.

6. `/Users/angel/Developer/mission/lib/algenta-sdk-client.ts`

- Optional hardening:
  - keep the centralized wrapper
  - but consider failing before request dispatch when the API key is actually missing, instead of using `__mission_missing_algenta_api_key__`
- If keeping placeholder behavior intentionally, add a short code comment documenting the tradeoff so it is clearly deliberate.

Why

- This is not the highest-priority drift. It is an ergonomics and observability issue, not the main privacy contract gap.

Recommended tests to add or update

1. `/Users/angel/Developer/mission/tests/algenta-config.test.ts`

- Add coverage for:
  - `DE_API_KEY`
  - `DE_BASE_URL`
  - `ALGENTA_API_URL`
- Preserve current `.env.local` fallback assertions.

2. `/Users/angel/Developer/mission/packages/algenta-sdk/test/client.test.mjs`

- Port upstream privacy tests for:
  - `self_hosted` + `ALGENTA_DISABLE_CLOUD=1` rejects `https://api.algenta.ai`
  - private profile allows explicit self-hosted `baseUrl`
  - private profile help text points at self-hosted console/API origin

3. `/Users/angel/Developer/mission/packages/algenta-sdk/test/runtime.test.mjs`

- Add or port tests for:
  - `Runtime({ mode: "self_hosted" })` requires explicit `baseUrl`
  - private profiles reject Algenta-owned hosted URLs
  - hosted/runtime path honors explicit self-hosted base URL aliases

4. `/Users/angel/Developer/mission/tests/decision-engine-sdk-client.test.ts`

- Add a wrapper-level regression proving Mission config can resolve:
  - `ALGENTA_BASE_URL`
  - `DE_BASE_URL`
  - `ALGENTA_API_URL`
- Add a regression proving private-profile cloud URLs fail closed once the vendored SDK parity lands.

Recommended verification commands

- `node --import ./scripts/test-register.mjs --test tests/algenta-config.test.ts tests/decision-engine-sdk-client.test.ts`
- `pnpm --dir /Users/angel/Developer/mission/packages/algenta-sdk test`
- `node --import ./scripts/test-register.mjs --test tests/algenta-sdk-import-guard.test.ts tests/algenta-sdk-wrapper-imports.test.ts tests/decision-engine-sdk-transport-guard.test.ts`

Current audit verdict

- Mission is mostly disciplined in how it uses the SDK.
- The real gap is not widespread misuse across app code.
- The real gap is that Mission's vendored SDK and Mission config helpers are behind the current upstream private-profile contract.
