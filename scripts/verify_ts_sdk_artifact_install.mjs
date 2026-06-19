#!/usr/bin/env node
/**
 * Verify the public TypeScript SDK (`algenta-sdk`) installs + imports from the PACKED npm
 * ARTIFACT — the exact tarball `npm publish` would upload — not just from the source tree.
 *
 * GTM Wave 1, item 2b — the Node mirror of scripts/verify_sdk_artifact_install.py (the Python
 * wheel gate). There is no committed `dist/` (it is gitignored); the package's `prepack` hook
 * builds it. We pack from a COPY of the package with dist/ excluded, so `npm pack` MUST rebuild
 * via `prepack` — exercising the REAL publish path (a broken/removed build hook fails the smokes
 * below). Packing from a copy also means a LOCAL run never mutates the dev's dist/ or node_modules.
 * Then we install the `.tgz` into a FRESH project OUTSIDE the repo (no monorepo on the module path)
 * and exercise every consumer entry path:
 *   - CJS  `require('algenta-sdk')`               — the CommonJS consumer
 *   - ESM  `import { X } from 'algenta-sdk'`       — the Node ESM consumer (named re-exports must
 *                                                    survive cjs-module-lexer on the CJS build)
 *   - gRPC `@grpc/* + proto/runtime.proto`         — the lazy runtime transport's deps + proto must
 *                                                    resolve from the installed package
 *   - TS   strict type-consumption `tsc --noEmit`  — the published `.d.ts` must typecheck for a
 *                                                    consumer (skipLibCheck:false, real @types/node)
 * plus package-metadata assertions (version matches source, Apache-2.0, LICENSE/README/dist/proto shipped).
 *
 * Catches the classic "works from source but the published tarball is missing dist/, breaks ESM
 * named imports, drops a runtime dep, ships broken types, or has wrong metadata" failure.
 *
 * NOTE on toolchain parity: release (.github/workflows/release-sdks.yml) builds via `pnpm build`,
 * this gate via `npm`. The published *artifact* is governed by package.json `files` + the same
 * `prepack` tsc, so it is identical; the consumer typecheck is pinned to the SDK's lockfile
 * typescript so a green commit stays green. (If pnpm-lock and package-lock ever drift on the tsc
 * version, the gate would build with a different tsc than release — keep them in sync.)
 *
 * Run locally or in CI:  node scripts/verify_ts_sdk_artifact_install.mjs
 */
import { execFileSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PKG_DIR = join(ROOT, "packages", "ts-sdk");
const SRC_META = JSON.parse(readFileSync(join(PKG_DIR, "package.json"), "utf8"));
const EXPECTED_VERSION = SRC_META.version; // from source — self-updating, no hardcoded drift.
const EXPECTED_LICENSE = "Apache-2.0";

// Real runtime (non-type) exports a consumer would reach for — touched by both smokes so the
// gate fails if a re-export silently drops out of the published bundle.
const REQUIRED_VALUE_EXPORTS = [
  "AlgentaClient",
  "DecisionEngineClient",
  "Runtime",
  "MojoRuntime",
  "libraries",
  "CONTRACT_VERSION",
  "DEFAULT_BASE_URL",
];

function run(cmd, args, opts = {}) {
  execFileSync(cmd, args, { stdio: "inherit", ...opts });
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

// Pin the consumer typecheck to the SAME typescript the SDK builds with (its lockfile), so the
// check is reproducible across days rather than floating to the latest 5.x.
function lockedTypescriptSpec() {
  const lock = JSON.parse(readFileSync(join(PKG_DIR, "package-lock.json"), "utf8"));
  const version = lock.packages?.["node_modules/typescript"]?.version;
  return version ? `typescript@${version}` : "typescript@5";
}

function main() {
  const tsSpec = lockedTypescriptSpec();
  const buildDir = mkdtempSync(join(tmpdir(), "algenta-ts-build-"));
  const packDir = mkdtempSync(join(tmpdir(), "algenta-ts-pack-"));
  const projDir = mkdtempSync(join(tmpdir(), "algenta-ts-consumer-"));
  try {
    // 1) Copy the package sources (no node_modules/dist/tarballs) into a temp build dir so the
    //    repo working tree is never mutated, and so the pack MUST rebuild dist/ via `prepack`.
    cpSync(PKG_DIR, buildDir, {
      recursive: true,
      filter: (src) =>
        !/(^|[/\\])(node_modules|dist)([/\\]|$)/.test(src) && !src.endsWith(".tgz"),
    });
    run("npm", ["ci", "--no-audit", "--no-fund"], { cwd: buildDir });

    // 2) Pack the publishable tarball. `npm pack` runs `prepack` (tsc) first, so the tarball
    //    carries a freshly built dist/.
    run("npm", ["pack", "--pack-destination", packDir], { cwd: buildDir });
    const tgz = readdirSync(packDir).filter((f) => f.endsWith(".tgz"));
    assert(tgz.length === 1, `expected exactly one .tgz, got ${JSON.stringify(tgz)}`);
    assert(
      tgz[0] === `algenta-sdk-${EXPECTED_VERSION}.tgz`,
      `packed tarball ${tgz[0]} does not match source version ${EXPECTED_VERSION}`,
    );
    const tarball = join(packDir, tgz[0]);

    // 3) Fresh consumer project OUTSIDE the repo -> install the TARBALL (resolves @grpc/* from npm).
    run("npm", ["init", "-y"], { cwd: projDir, stdio: "ignore" });
    run("npm", ["install", "--no-audit", "--no-fund", tarball], { cwd: projDir });
    const installed = join(projDir, "node_modules", "algenta-sdk");

    // 4) Metadata assertions — read the installed package.json from disk (the `exports` map blocks
    //    the `algenta-sdk/package.json` subpath import, so a require() would wrongly fail here).
    const meta = JSON.parse(readFileSync(join(installed, "package.json"), "utf8"));
    assert(meta.version === EXPECTED_VERSION, `installed version ${meta.version} != ${EXPECTED_VERSION}`);
    assert(meta.license === EXPECTED_LICENSE, `installed license ${meta.license} != ${EXPECTED_LICENSE}`);
    // proto/runtime.proto is loaded at runtime relative to dist/ (__dirname/../proto), so the
    // specific file — not just the dir — must ship or grpc-backed calls ENOENT in the wild.
    for (const f of ["LICENSE", "README.md", "dist/index.js", "dist/index.d.ts", "proto/runtime.proto"]) {
      assert(existsSync(join(installed, f)), `published tarball is missing ${f}`);
    }

    // 5) CJS require smoke.
    writeFileSync(
      join(projDir, "smoke.cjs"),
      [
        "const sdk = require('algenta-sdk');",
        `for (const k of ${JSON.stringify(REQUIRED_VALUE_EXPORTS)}) if (sdk[k] === undefined) throw new Error('CJS missing export: ' + k);`,
        "if (typeof sdk.AlgentaClient !== 'function') throw new Error('CJS AlgentaClient is not a class');",
        "console.log('  [cjs] require OK — CONTRACT_VERSION=' + sdk.CONTRACT_VERSION);",
        "",
      ].join("\n"),
    );
    run("node", ["smoke.cjs"], { cwd: projDir });

    // 6) ESM named-import smoke — the real Node ESM consumer path; proves the re-exported names
    //    survive cjs-module-lexer's static analysis of the CommonJS build.
    writeFileSync(
      join(projDir, "smoke.mjs"),
      [
        "import { AlgentaClient, DecisionEngineClient, Runtime, CONTRACT_VERSION, DEFAULT_BASE_URL } from 'algenta-sdk';",
        "for (const [n, v] of Object.entries({ AlgentaClient, DecisionEngineClient, Runtime })) if (typeof v !== 'function') throw new Error('ESM ' + n + ' is not a class');",
        "if (!CONTRACT_VERSION || !DEFAULT_BASE_URL) throw new Error('ESM constant export missing');",
        "console.log('  [esm] named imports OK — CONTRACT_VERSION=' + CONTRACT_VERSION);",
        "",
      ].join("\n"),
    );
    run("node", ["smoke.mjs"], { cwd: projDir });

    // 7) gRPC + proto smoke — the runtime transport lazy-imports @grpc/grpc-js + @grpc/proto-loader
    //    and loads proto/runtime.proto relative to dist/. Prove both runtime deps resolve from the
    //    installed package AND the shipped proto parses (deterministic; no daemon / no network).
    writeFileSync(
      join(projDir, "grpc_proto.mjs"),
      [
        "import { existsSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "await import('@grpc/grpc-js');",
        "const loader = await import('@grpc/proto-loader');",
        "const proto = join(process.cwd(), 'node_modules', 'algenta-sdk', 'proto', 'runtime.proto');",
        "if (!existsSync(proto)) throw new Error('shipped proto missing: ' + proto);",
        "const def = loader.loadSync(proto, {});",
        "if (!def || Object.keys(def).length === 0) throw new Error('proto/runtime.proto loaded empty');",
        "console.log('  [grpc] @grpc/* deps resolve + proto/runtime.proto loads (' + Object.keys(def).length + ' defs)');",
        "",
      ].join("\n"),
    );
    run("node", ["grpc_proto.mjs"], { cwd: projDir });

    // 8) TS type-consumption check — install the SAME tsc the SDK builds with + @types/node, then
    //    STRICT-typecheck (skipLibCheck:false) the published `.d.ts` the way a real consumer would,
    //    so a corrupt/regressed declaration surface fails the gate.
    run("npm", ["install", "--no-audit", "--no-fund", "--no-save", tsSpec, "@types/node@20"], { cwd: projDir });
    writeFileSync(
      join(projDir, "consumer.ts"),
      [
        "import { AlgentaClient, DecisionEngineClient, Runtime, CONTRACT_VERSION } from 'algenta-sdk';",
        "import type { AlgentaClientConfig, DecisionEngineClientConfig, RuntimeConfig } from 'algenta-sdk';",
        "type _A = AlgentaClientConfig;",
        "type _D = DecisionEngineClientConfig;",
        "type _R = RuntimeConfig;",
        "const ctors: Array<new (...args: never[]) => unknown> = [AlgentaClient, DecisionEngineClient, Runtime];",
        "const version: string = CONTRACT_VERSION;",
        "void ctors; void version;",
        "void (0 as unknown as _A); void (0 as unknown as _D); void (0 as unknown as _R);",
        "",
      ].join("\n"),
    );
    writeFileSync(
      join(projDir, "tsconfig.consumer.json"),
      JSON.stringify(
        {
          compilerOptions: {
            module: "NodeNext",
            moduleResolution: "NodeNext",
            target: "ES2020",
            strict: true,
            noEmit: true,
            skipLibCheck: false,
            types: ["node"],
          },
          files: ["consumer.ts"],
        },
        null,
        2,
      ),
    );
    run(join(projDir, "node_modules", ".bin", "tsc"), ["-p", "tsconfig.consumer.json"], { cwd: projDir });
    console.log(`  [tsc] published .d.ts strict-typechecks for a consumer (${tsSpec})`);

    console.log(
      `\n[ok] algenta-sdk@${EXPECTED_VERSION}: packed tarball builds, installs into a fresh project; CJS + ESM + gRPC/proto + strict types all import.`,
    );
  } finally {
    rmSync(buildDir, { recursive: true, force: true });
    rmSync(packDir, { recursive: true, force: true });
    rmSync(projDir, { recursive: true, force: true });
  }
  return 0;
}

process.exit(main());
