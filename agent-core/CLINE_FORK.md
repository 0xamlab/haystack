# agent-core: forked-Cline vendoring + headless proof

The agent-core sidecar's `runAgent()` (in `run-server.mjs`) is currently a stub. It will be
backed by a **vendored, Apache-2.0 fork of `@cline/core`** running headless. This note records
the empirically-verified build recipe and the headless proof so the vendoring step is mechanical.

## Source & license (verified)
- Upstream: `https://github.com/cline/cline`, Bun monorepo. Spike used HEAD `3a3ea6e`
  (architecture cross-checked against pinned `1c1ea0bd`).
- **Root `LICENSE` = Apache-2.0.** BUT `sdk/packages/{core,shared,llms}/package.json` OMIT a
  `license` field (only `agents` + `sdk` declare `Apache-2.0`). This is why the *npm-published*
  `@cline/core` reads "Proprietary". **Rule: vendor from the GitHub source (covered by root
  Apache-2.0), add an explicit `"license": "Apache-2.0"` + header to each vendored package, and
  NEVER `npm i @cline/*`.** (Release-blocking CI guard = task #4.)

## Build recipe (verified working, Node ≥22 + Bun 1.3.x)
```sh
git clone --depth 1 https://github.com/cline/cline.git
cd cline
bun install                 # full root install — gets workspace links + tsc (vscode is excluded)
bun run build:sdk           # = bun --production -F './sdk/packages/*' build  (topological)
# => sdk/packages/{shared,llms,agents,core,sdk}/dist/index.js all build (exit 0)
```
Gotcha: a *filtered* install (`bun install --filter './sdk/packages/*'`) is NOT enough — it omits
`tsc` and the cross-package workspace links, so the build fails to resolve `@cline/shared`.

The built `core/dist/index.js` **externalizes** its `@cline/*` siblings, so a consumer must have
them resolvable. In a plain dir, symlink them:
```sh
mkdir -p node_modules/@cline
for p in shared llms agents core sdk; do ln -sfn <repo>/sdk/packages/$p node_modules/@cline/$p; done
```

## Headless instantiation — PROVEN
```js
import { ClineCore } from "@cline/core";
const cline = await ClineCore.create({ clientName: "algenta-spike", backendMode: "local" });
// backendMode "local" => in-process LocalRuntimeHost, NO hub daemon, no model, no network.
// instance API: start, subscribe, restore, disposeSessionBootstrap ; cleanup via dispose().
await cline.dispose();
```
`ClineCoreOptions` (`sdk/packages/core/src/cline-core/types.ts`): `clientName?`, `backendMode?:
RuntimeHostMode("auto"|"local"|"hub"|"remote")`, `hub?`, `remote?`, `capabilities?`, `prepare?`.

## Next (wire the real adapter — replaces the stub `runAgent`)
1. Vendor `sdk/packages/{shared,llms,agents,core}` into this fork at a pinned tag (+ Apache headers,
   strip `shared/src/runtime/cline-environment.ts` + `core/src/services/telemetry/core-events.ts`).
2. `cline-adapter.ts`: wrap `ClineCore.create({backendMode:"local", capabilities})` + `start()`.
   - Inject our evidence bundle / blast-radius via the **`capabilities`** option (the verified
     injection seam — NOT the dead `runtimePlaceholders` path).
   - Suppress exploration tools at the capability/tool-roster layer (SDK tool names are
     `bash/editor/read_files/apply_patch/search/fetch_web`, not the classic VS Code names).
   - Point `@cline/llms` at the loopback OpenAI-compatible model proxy.
3. Stream `start()` events to the NDJSON `/run` response; agent mutates files under `working_dir`;
   Python still recomputes the authoritative diff.
