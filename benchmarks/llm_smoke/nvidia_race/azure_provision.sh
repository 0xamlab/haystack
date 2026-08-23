#!/usr/bin/env bash
# azure_provision.sh — quota-aware, idempotent Azure SPOT fleet provisioner for the GPU race
# campaign. Provisions up to 2 spot VMs per GPU series, ONLY in regions that (a) offer the
# SKU in the catalog and (b) have granted family quota — never exceeding the granted limit.
#
# Provisioning state on 2026-08-23 (see benchmarks/llm_smoke/amd_launch_readiness.md §4 for
# the evidence): every GPU family in this subscription is 0-of-0 in EVERY region (all portal
# quota requests auto-failed "ContactSupport"; four support tickets open). This script is the
# one-command fleet step for when grants land — it skips and records every 0-of-0 series.
#
# Series -> SKU family -> candidate regions (catalog scan, az vm list-skus --all, 2026-08-23):
#   ND H100 v5      standardNDSH100v5Family      eastus southcentralus australiaeast swedencentral
#                                                canadacentral westus2 westus3 uksouth westeurope
#                                                northeurope japaneast koreacentral
#   NCCads H100 v5  StandardNCadsH100v5Family    eastus (NC40ads/NC80adis; the owner's portal
#                                                tickets filed ND-series instead — both covered)
#   ND H200 v5      standardNDISRH200V5Family    uksouth eastus2 australiaeast westus3 japaneast
#                                                francecentral switzerlandnorth uaenorth italynorth
#                                                polandcentral spaincentral
#   ND128isr GB300  standardNDISRGB300V6Family   westus2 westus3 uksouth northeurope swedencentral
#                                                eastus2 germanywestcentral brazilsouth
#   ND MI300X v5    standardNDISv5MI300XFamily   francecentral   <-- the ONLY region offering it
#
# Requirements: az CLI authenticated (az account show), jq, ssh-keygen.
#
# Usage:
#   bash benchmarks/llm_smoke/nvidia_race/azure_provision.sh [--dry-run] [series ...]
#     series: any of h100v5 ncch100v5 h200v5 gb300v6 mi300xv5 (default: all five)
#   AZ_RESOURCE_GROUP  resource group (default algenta-race)
#   AZ_IMAGE           image alias (default Ubuntu2204; Ubuntu2404 if a GB300/MI300X image
#                      route requires it — check the SKUs' marketplace image at launch)
#   AZ_SSH_KEY         private key path (default ~/.ssh/algenta_azure_ed25519; generated if absent)
#   AZ_COUNT           VMs per series (default 2 — the campaign request; never exceeds quota)
#
# Spot policy: --priority Spot --eviction-policy Deallocate --max-price -1 (pay up to
# on-demand; a preempted VM stops instead of being deleted, boot-disk state survives —
# the GCP lane's restart behaviour, same intent). After a reboot/deallocate, re-check the
# NVIDIA dpkg 'rc' state gotcha recorded in setup_vm.sh's stage 2.
#
# VM naming: algenta-az-<series-slug>-{1,2}. OS disk: 512 GB premium SSD. No system-assigned
# identity (not needed). Public IP kept for ssh; the report prints internal + external IPs.
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=1; shift; fi

RG="${AZ_RESOURCE_GROUP:-algenta-race}"
IMAGE="${AZ_IMAGE:-Ubuntu2204}"
SSH_KEY="${AZ_SSH_KEY:-$HOME/.ssh/algenta_azure_ed25519}"
COUNT="${AZ_COUNT:-2}"

command -v az >/dev/null || { echo "azure_provision: az CLI not found"; exit 1; }
command -v jq >/dev/null || { echo "azure_provision: jq not found"; exit 1; }
az account show -o none 2>/dev/null || { echo "azure_provision: az not authenticated (az login)"; exit 1; }

log() { echo "[azure_provision $(date -u +%H:%M:%S)] $*"; }

# series slug -> quota family -> candidate regions (see header for provenance)
family_for() {
    case "$1" in
        h100v5)    echo "standardNDSH100v5Family" ;;
        ncch100v5) echo "StandardNCadsH100v5Family" ;;
        h200v5)    echo "standardNDISRH200V5Family" ;;
        gb300v6)   echo "standardNDISRGB300V6Family" ;;
        mi300xv5)  echo "standardNDISv5MI300XFamily" ;;
        *) return 1 ;;
    esac
}
regions_for() {
    case "$1" in
        h100v5)    echo "eastus southcentralus australiaeast swedencentral canadacentral westus2 westus3 uksouth westeurope northeurope japaneast koreacentral" ;;
        ncch100v5) echo "eastus uksouth westeurope northeurope westus2" ;;
        h200v5)    echo "uksouth eastus2 australiaeast westus3 japaneast francecentral switzerlandnorth uaenorth italynorth polandcentral spaincentral" ;;
        gb300v6)   echo "westus2 westus3 uksouth northeurope swedencentral eastus2 germanywestcentral brazilsouth" ;;
        mi300xv5)  echo "francecentral" ;;
        *) return 1 ;;
    esac
}
sku_for() {   # the concrete size name inside the family (catalog-discovered, not hardcoded)
    local family="$1" loc="$2"
    az vm list-skus --location "$loc" --all --resource-type virtualMachines -o json 2>/dev/null \
        | jq -r --arg fam "$family" \
            '[.[] | select(.family == $fam) | .name] | sort | last // empty'
}

# quota_free <loc> <family> -> prints free VM slots (limit - current), or -1 if absent
quota_free() {
    local loc="$1" family="$2"
    az vm list-usage -l "$loc" -o json 2>/dev/null | jq -r --arg fam "$family" \
        '[.[] | select(.name.value | ascii_downcase == ($fam | ascii_downcase))]
         | if length == 0 then -1
           else ((.[0].limit | tonumber) - (.[0].currentValue | tonumber)) end'
}

SERIES=("$@")
if [[ ${#SERIES[@]} -eq 0 ]]; then SERIES=(h100v5 ncch100v5 h200v5 gb300v6 mi300xv5); fi

if [[ ! -f "$SSH_KEY.pub" ]]; then
    log "generating campaign ssh key at $SSH_KEY"
    [[ $DRY_RUN -eq 1 ]] || ssh-keygen -q -t ed25519 -N "" -f "$SSH_KEY"
fi

REPORT="$(mktemp)"
trap 'rm -f "$REPORT"' EXIT

for series in "${SERIES[@]}"; do
    family="$(family_for "$series")" || { log "unknown series: $series — skipped"; continue; }
    chosen_loc=""; chosen_sku=""; free=0

    # ── pick the first candidate region that OFFERS the SKU AND has granted quota ──
    for loc in $(regions_for "$series"); do
        sku="$(sku_for "$family" "$loc")"
        if [[ -z "$sku" ]]; then
            log "$series: $loc — SKU not offered (catalog) — next"
            continue
        fi
        f="$(quota_free "$loc" "$family")"
        if [[ "$f" == "-1" ]]; then
            log "$series: $loc — family not in usage list (treat as 0-of-0) — next"
            continue
        fi
        log "$series: $loc offers $sku — granted free slots: $f"
        if [[ "$f" -gt 0 ]]; then chosen_loc="$loc"; chosen_sku="$sku"; free="$f"; break; fi
    done

    if [[ -z "$chosen_loc" ]]; then
        log "$series: NO region with offered SKU + granted quota — SKIPPED (0-of-0 or not offered)"
        echo "$series|SKIPPED|-|-|0-of-0 or SKU not offered in any candidate region" >> "$REPORT"
        continue
    fi

    want="$COUNT"
    if [[ "$free" -lt "$want" ]]; then
        log "$series: only $free free slot(s) under quota — provisioning $free of $want (never exceed quota)"
        want="$free"
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "$series: DRY-RUN — would provision $want x $chosen_sku in $chosen_loc"
        echo "$series|DRY-RUN|$chosen_loc|$chosen_sku|$want slots" >> "$REPORT"
        continue
    fi

    az group show -n "$RG" >/dev/null 2>&1 || az group create -n "$RG" -l "$chosen_loc" -o none

    for i in $(seq 1 "$want"); do
        name="algenta-az-${series}-${i}"
        if az vm show -g "$RG" -n "$name" >/dev/null 2>&1; then
            log "$series: $name already exists — kept (idempotent)"
            echo "$series|EXISTS|$chosen_loc|$name|already provisioned" >> "$REPORT"
            continue
        fi
        log "$series: creating $name ($chosen_sku, spot Deallocate, 512GB premium SSD, $IMAGE)"
        if az vm create \
            -g "$RG" -n "$name" \
            --location "$chosen_loc" \
            --size "$chosen_sku" \
            --image "$IMAGE" \
            --os-disk-size-gb 512 \
            --storage-sku Premium_LRS \
            --priority Spot --eviction-policy Deallocate --max-price -1 \
            --admin-user algenta \
            --ssh-key-value "$SSH_KEY.pub" \
            -o json > "/tmp/azure_vm_${name}.json"; then
            priv="$(jq -r '.privateIpAddress // "-"' "/tmp/azure_vm_${name}.json")"
            pub="$(jq -r '.publicIpAddress // "-"' "/tmp/azure_vm_${name}.json")"
            log "$series: $name up — internal $priv, public $pub"
            echo "$series|PROVISIONED|$chosen_loc|$name|internal=$priv public=$pub ssh -i $SSH_KEY algenta@$pub" >> "$REPORT"
        else
            log "$series: $name FAILED (az vm create error above) — recording and continuing"
            echo "$series|FAILED|$chosen_loc|$name|az vm create failed (quota race or capacity)" >> "$REPORT"
        fi
    done
done

log "── fleet report ──"
column -t -s'|' "$REPORT" || cat "$REPORT"

log "next steps for PROVISIONED NVIDIA VMs (H100/H200 = sm_90):"
log "  scp -i $SSH_KEY benchmarks/llm_smoke/nvidia_race/setup_vm.sh algenta@<public-ip>:~/"
log "  ssh -i $SSH_KEY algenta@<public-ip> 'bash ~/setup_vm.sh sm_90'   # re-run after the stage-2 reboot"
log "GB300 v6 (Blackwell, sm_100+) needs CUDA >= 12.8 — setup_vm.sh stage 3 pins 12.6; adapt before use."
log "MI300X v5 VMs are the AMD lane — see benchmarks/llm_smoke/amd_launch_readiness.md §5 (ROCm, not CUDA)."
