#!/usr/bin/env bash
# Post-build: symlink the built @cline/* workspace packages into node_modules so
# files OUTSIDE the workspace packages (algenta/*) can `import "@cline/core"`.
# Run after:  bun install && bun run build:sdk
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"   # vendored cline root
mkdir -p "$root/node_modules/@cline"
for p in shared llms agents core sdk; do
  ln -sfn "../../sdk/packages/$p" "$root/node_modules/@cline/$p"
done
echo "linked @cline/{shared,llms,agents,core,sdk}"
