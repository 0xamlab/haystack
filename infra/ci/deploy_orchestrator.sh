#!/usr/bin/env bash
# Deploy ci-orch — the orchestrator VM of the algenta Azure CI compute plane.
#
# Creates Standard_D2s_v4 Ubuntu 22.04 VM `ci-orch` in RG thyn-ci / subnet
# `builders`, with cloud-init from infra/ci/orchestrator-cloud-init.yaml and
# the queue-watcher source infra/ci/az_orchestrator.py embedded in it.
#
# Run as an identity with Contributor on RG thyn-ci (default: the az CLI's
# active context, i.e. angel@thyn.ai). GitHub inputs come from the gh CLI
# (repo thyn-ai/algenta, admin access) unless overridden:
#
#   GITHUB_CI_TOKEN   token baked into the VM as env for the queue-watcher
#                     (job polling + JIT runner registration). Default: the
#                     gh CLI's active token. ROTATION: re-run this script with
#                     a new token and --replace.
#   AZURE_SP_FILE     thyn-ci-builder SP credential file
#                     (default ~/.azure/thyn-ci-builder.json; RG-scoped
#                     Contributor ONLY — it can never touch anything outside
#                     RG thyn-ci).
#   AZURE_VM_SIZES    worker sizes tried in order, default
#                     "Standard_D8s_v4 Standard_D8s_v3" (one size per family =
#                     up to 2 concurrent workers under the subscription's
#                     per-family caps; D8s_v6 is capacity-restricted in eastus;
#                     switch to
#                     "Standard_D16s_v5 Standard_D8s_v5" once DSv5 quota is
#                     granted — see PR description).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RG="thyn-ci"
LOCATION="eastus"
VM_NAME="ci-orch"
SUBNET_ID="/subscriptions/fed0aaeb-1166-4483-a437-1ef62d224f04/resourceGroups/thyn-ci/providers/Microsoft.Network/virtualNetworks/thyn-gh-runners/subnets/builders"
SP_FILE="${AZURE_SP_FILE:-$HOME/.azure/thyn-ci-builder.json}"
REPO="thyn-ai/algenta"
REPLACE=0
[[ "${1:-}" == "--replace" ]] && REPLACE=1

log() { printf '== %s\n' "$*"; }

command -v az >/dev/null || { echo "az CLI not found" >&2; exit 1; }
command -v gh >/dev/null || { echo "gh CLI not found" >&2; exit 1; }
[[ -f "$SP_FILE" ]] || { echo "SP credential file missing: $SP_FILE" >&2; exit 1; }

az account show >/dev/null || { echo "not logged into az" >&2; exit 1; }

if [[ "$REPLACE" == 1 ]]; then
  if az vm show -g "$RG" -n "$VM_NAME" >/dev/null 2>&1; then
    log "deleting existing $VM_NAME (--replace)"
    az vm delete -g "$RG" -n "$VM_NAME" --yes
  fi
elif az vm show -g "$RG" -n "$VM_NAME" >/dev/null 2>&1; then
  echo "$VM_NAME already exists; re-run with --replace to redeploy" >&2
  exit 1
fi

log "reading SP credentials from $SP_FILE"
# Only clientId/clientSecret come from the SP file: its tenantId/subscriptionId
# fields hold the literal string "None" (written at generation time), so tenant
# and subscription are derived from the authenticated az CLI context instead.
read -r CLIENT_ID CLIENT_SECRET <<<"$(python3 - "$SP_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(d["clientId"], d["clientSecret"])
PY
)"
TENANT_ID="$(az account show --query tenantId -o tsv)"
SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
for v in "$CLIENT_ID" "$CLIENT_SECRET" "$TENANT_ID" "$SUBSCRIPTION_ID"; do
  if [[ -z "$v" || "$v" == "None" ]]; then
    echo "invalid credential/context value (empty or literal 'None')" >&2
    exit 1
  fi
done

log "obtaining GitHub inputs (repo $REPO)"
GITHUB_CI_TOKEN="${GITHUB_CI_TOKEN:-$(gh auth token)}"
ORCH_RUNNER_REG_TOKEN="$(gh api -X POST "repos/$REPO/actions/runners/registration-token" --jq .token)"
[[ -n "$ORCH_RUNNER_REG_TOKEN" ]] || { echo "failed to obtain runner registration token" >&2; exit 1; }

log "rendering cloud-init"
CLOUD_INIT="$(mktemp -t az-orch-cloud-init.XXXXXX)"
chmod 600 "$CLOUD_INIT"
trap 'rm -f "$CLOUD_INIT"' EXIT

export RENDER_TEMPLATE="$REPO_ROOT/infra/ci/orchestrator-cloud-init.yaml"
export RENDER_PY_SOURCE="$REPO_ROOT/infra/ci/az_orchestrator.py"
export RENDER_GITHUB_CI_TOKEN="$GITHUB_CI_TOKEN"
export RENDER_ORCH_RUNNER_REG_TOKEN="$ORCH_RUNNER_REG_TOKEN"
export RENDER_CLIENT_ID="$CLIENT_ID"
export RENDER_CLIENT_SECRET="$CLIENT_SECRET"
export RENDER_TENANT_ID="$TENANT_ID"
export RENDER_SUBSCRIPTION_ID="$SUBSCRIPTION_ID"
export RENDER_SUBNET_ID="$SUBNET_ID"
export RENDER_VM_SIZES="${AZURE_VM_SIZES:-Standard_D8s_v4 Standard_D8s_v3}"
python3 - "$CLOUD_INIT" <<'PY'
import base64, os, sys

with open(os.environ["RENDER_TEMPLATE"], encoding="utf-8") as fh:
    doc = fh.read()
with open(os.environ["RENDER_PY_SOURCE"], "rb") as fh:
    py_b64 = base64.b64encode(fh.read()).decode("ascii")

substitutions = {
    "__ORCHESTRATOR_PY_B64__": py_b64,
    "__GITHUB_CI_TOKEN__": os.environ["RENDER_GITHUB_CI_TOKEN"],
    "__ORCH_RUNNER_REG_TOKEN__": os.environ["RENDER_ORCH_RUNNER_REG_TOKEN"],
    "__AZURE_SP_CLIENT_ID__": os.environ["RENDER_CLIENT_ID"],
    "__AZURE_SP_CLIENT_SECRET__": os.environ["RENDER_CLIENT_SECRET"],
    "__AZURE_TENANT_ID__": os.environ["RENDER_TENANT_ID"],
    "__AZURE_SUBSCRIPTION_ID__": os.environ["RENDER_SUBSCRIPTION_ID"],
    "__AZURE_SUBNET_ID__": os.environ["RENDER_SUBNET_ID"],
    "__AZURE_VM_SIZES__": os.environ["RENDER_VM_SIZES"],
}
for token, value in substitutions.items():
    if token not in doc:
        raise SystemExit(f"template placeholder missing: {token}")
    doc = doc.replace(token, value)
leftover = [t for t in substitutions if t in doc]
if leftover:
    raise SystemExit(f"unresolved placeholders: {leftover}")
try:
    doc.encode("ascii")
except UnicodeEncodeError as exc:
    # Azure custom-data is latin-1 transported; non-ASCII fails mid-vm-create.
    raise SystemExit(f"rendered cloud-init is not ASCII-clean: {exc}")
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    fh.write(doc)
PY

log "creating VM $VM_NAME (Standard_B2s, Ubuntu 22.04, subnet builders)"
az vm create \
  --resource-group "$RG" \
  --name "$VM_NAME" \
  --location "$LOCATION" \
  --image "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest" \
  --size Standard_D2s_v4 \
  --admin-username azureuser \
  --generate-ssh-keys \
  --subnet "$SUBNET_ID" \
  --public-ip-sku Standard \
  --os-disk-size-gb 30 \
  --custom-data "$CLOUD_INIT" \
  --tags plane=az-ci role=orchestrator

log "$VM_NAME created. cloud-init now installs the az-orch runner + the"
log "az-orchestrator queue-watcher (few minutes). Watch:"
log "  gh api repos/$REPO/actions/runners   (runner ci-orch / label az-orch)"
log "  ssh azureuser@<public-ip> 'journalctl -u az-orchestrator -f'"
