#!/usr/bin/env bash
# The clean-machine contract leg of build-runtime.yml, executed inside an amd64 ubuntu:22.04
# container on the self-hosted macOS fleet (job `clean-machine-contract` mounts $GITHUB_WORKSPACE
# at /work after downloading the linux runtime wheel into dist-runtime/). Replaces the
# GitHub-hosted `ubuntu-latest` job, which is billing-blocked. Every check mirrors the hosted job
# 1:1: trust-anchor pairing -> algenta wheel build -> clean venv install -> runtime doctor ->
# contract sweep -> CLI execute -> simulate banner.
set -euo pipefail
cd /work

# shellcheck source=_linux_container_bootstrap.sh
source "$(dirname "$0")/_linux_container_bootstrap.sh"

# ── Pair runtime and Algenta trust anchor (verbatim logic of the hosted step) ───────────────
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile

wheels = sorted(Path("dist-runtime").glob("*.whl"))
if len(wheels) != 1:
    raise SystemExit(f"expected one Linux runtime wheel, found {len(wheels)}")
with ZipFile(wheels[0]) as archive:
    public_key = archive.read(
        "algenta_runtime_native/algenta_release_pub.pem"
    )
if not public_key.startswith(b"-----BEGIN PUBLIC KEY-----"):
    raise SystemExit("runtime wheel contains an invalid release public key")
Path(
    "packages/algenta/algenta/_keys/algenta_release_pub.pem"
).write_bytes(public_key)
PY

# ── Clean-machine install + runtime doctor (verbatim logic of the hosted step) ──────────────
uv pip install --python /usr/local/bin/python3 --quiet build
python3 -P -m build --wheel packages/algenta --outdir /work/dist-algenta
python3 -m venv /tmp/clean && . /tmp/clean/bin/activate
pip install --quiet dist-runtime/*.whl dist-algenta/*.whl
! command -v mojo && ! command -v modular || (echo "toolchain unexpectedly present" && exit 1)
out=$(algenta runtime doctor || true)
echo "$out"
echo "$out" | grep -q "runtime source:  bundled runtime"
echo "$out" | grep -q "mode:            bundled worker"
echo "$out" | grep -q "fallback:        denied"
echo "$out" | grep -q "tcp listeners:   none"
echo "$out" | grep -q "status:          READY"
forbidden=("mojo command not found" "install Mo""jo" "install Mod""ular" "start daemon" "docker run")
for bad in "${forbidden[@]}"; do
  if echo "$out" | grep -qi "$bad"; then echo "::error::doctor leaked forbidden runtime setup text"; exit 1; fi
done
python - <<'PY'
import os
import time

import algenta
from algenta.native import loader

result = loader.execute({'engine_type': 'runtime_smoke', 'runs': 1})
if not isinstance(result, dict):
    raise SystemExit('runtime returned non-object payload')

runtime = algenta.MojoRuntime(mode='local')
health = runtime.health()
if health.get('status') != 'ok' or health.get('tcp_listeners') != []:
    raise SystemExit(f'encapsulated runtime health failed: {health}')
modules = runtime.list_modules()
from algenta.runtime_library_contract import runtime_modules
contract_modules = runtime_modules()
if len(modules) != len(contract_modules):
    raise SystemExit(
        f'live runtime reports {len(modules)} modules; the packaged '
        f'contract this same wheel ships declares {len(contract_modules)}'
    )
live_functions = sum(len(item['functions']) for item in modules)
contract_functions = sum(len(m.functions) for m in contract_modules)
if live_functions != contract_functions:
    raise SystemExit(
        f'live runtime reports {live_functions} functions; the packaged '
        f'contract this same wheel ships declares {contract_functions}'
    )

from algenta.native import worker
from algenta.runtime_library_contract import runtime_modules

shard_routes = {}
for module_name in worker.runtime_module_filter() or ():
    resolution = worker.require_worker(
        module_name=module_name, require_verified=True
    )
    shard_routes.setdefault(resolution.path.name, module_name)
if len(shard_routes) < 2:
    raise SystemExit(f'expected multiple internal runtime workers: {shard_routes}')
for worker_name, module_name in sorted(shard_routes.items()):
    resolution = worker.require_worker(
        module_name=module_name, require_verified=True
    )
    response = worker._session_for(resolution).execute({'type': 'ping'}, 15.0)
    if response != {'status': 'ok'}:
        raise SystemExit(f'runtime worker {worker_name} failed ping: {response}')

def representative_value(type_name):
    scalars = {
        'Bool': True,
        'String': 'alpha',
        'Int': 5,
        'UInt8': 3,
        'UInt16': 3,
        'UInt32': 3,
        'UInt64': 3,
        'Float32': 5.0,
        'Float64': 5.0,
        'None': None,
    }
    if type_name in scalars:
        return scalars[type_name]
    if type_name.startswith('List[') and type_name.endswith(']'):
        inner = type_name[5:-1]
        return [representative_value(inner)] * 3
    raise ValueError(type_name)

executed_workers = set()
for module_spec in runtime_modules():
    resolution = worker.require_worker(
        module_name=module_spec.import_path, require_verified=True
    )
    if resolution.path.name in executed_workers:
        continue
    for function_spec in module_spec.functions:
        try:
            args = [
                representative_value(param.typ)
                for param in function_spec.params
            ]
        except ValueError:
            continue
        try:
            result = runtime.execute(
                module_spec.import_path, function_spec.name, args
            )
        except Exception:
            continue
        if result.get('success') and result.get('engine_used') == 'mojo':
            executed_workers.add(resolution.path.name)
            break
if executed_workers != set(shard_routes):
    missing = sorted(set(shard_routes) - executed_workers)
    raise SystemExit(f'workers without real function execution: {missing}')

# dot64_f32 requires exactly 64 elements (short lists return the 0.0 sentinel),
# so the latency probe uses full-length vectors.
request = {
    'a': [1.0, 2.0, 3.0] + [0.0] * 61,
    'b': [3.0, 2.0, 2.0] + [0.0] * 61,
}
# The warm-latency tripwire budget. 15 ms is the contract for NATIVE linux x86_64; this job now
# runs under amd64 emulation on the self-hosted macOS fleet, which is slower per call, so the
# workflow passes an enlarged budget explicitly rather than silently weakening the default.
budget_ms = float(os.environ.get('ALGENTA_CLEAN_MACHINE_WARM_MS_BUDGET', '15.0'))
latencies = []
for index in range(11):
    started = time.perf_counter()
    execution = runtime.execute('vector_kernels.dot', 'dot64_f32', request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not execution.get('success') or execution.get('result') != 13.0:
        raise SystemExit(f'library execution failed: {execution}')
    if index:
        latencies.append(elapsed_ms)
if max(latencies) > budget_ms:
    raise SystemExit(f'warm runtime exceeded {budget_ms} ms: {latencies}')
print('clean-machine contract OK')
PY
algenta runtime execute vector_kernels.dot dot64_f32 \
  --args-json '{"a":[1,2,3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],"b":[3,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]}' \
  > /tmp/algenta-runtime-execute.json
echo "--- execute payload:"; cat /tmp/algenta-runtime-execute.json; echo
python - <<'PY'
import json
p = json.load(open("/tmp/algenta-runtime-execute.json"))
assert p["success"] and p["engine_used"] == "mojo" and p["result"] == 13.0, p
PY
algenta simulate > /tmp/algenta-simulate.txt
grep -q "Engine:             bundled native runtime" /tmp/algenta-simulate.txt
grep -q "Python fallback:    disabled" /tmp/algenta-simulate.txt

# The container ran as root on the mounted runner workspace; hand the produced/modified trees
# back to the workspace owner so the runner-side artifact upload and the next job's checkout are
# not locked out by root-owned files.
OWNER="$(stat -c '%u:%g' /work/.git)"
chown -R "$OWNER" /work/dist-algenta /work/packages/algenta/algenta/_keys 2>/dev/null || true
echo "clean-machine contract leg OK"
