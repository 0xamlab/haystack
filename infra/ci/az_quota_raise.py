#!/usr/bin/env python3
"""Raise Azure quotas for the ephemeral CI plane via the Microsoft.Quota RP.

The subscription's default 10 total regional cores caps the orchestrator at one
8-vCPU worker per region; the user mandate is scale-to-20. Requests 40 cores +
40 per DS/FS family per region, and 100 Standard-SKU PIPs (the 20-PIP wall bit
eastus). CPU-family increases are normally auto-approved.

Env: same as az_orchestrator.py (AZURE_SP_CLIENT_ID/SECRET, TENANT, SUBSCRIPTION).
"""
import json
import os
import time
import urllib.error
import urllib.request

SUB = os.environ["AZURE_SUBSCRIPTION_ID"]
TENANT = os.environ["AZURE_TENANT_ID"]
CID = os.environ.get("AZURE_SP_CLIENT_ID") or os.environ["AZURE_CLIENT_ID"]
CSEC = os.environ.get("AZURE_SP_CLIENT_SECRET") or os.environ["AZURE_CLIENT_SECRET"]

REGIONS = [
    "eastus2", "eastus", "centralus", "westus2", "westus",
    "westus3", "southcentralus", "northcentralus",
]
CORES = 40
FAMILIES = [
    "standardDSv3Family", "standardDSv4Family", "standardDSv5Family",
    "standardDSv6Family", "standardFSv2Family",
]
PIP_LIMIT = 100


def token():
    body = (
        f"grant_type=client_credentials&client_id={CID}&client_secret={CSEC}"
        "&scope=https%3A%2F%2Fmanagement.azure.com%2F.default"
    ).encode()
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


TOK = token()


def arm(method, path, body=None, api="2025-09-01"):
    url = f"https://management.azure.com{path}{'&' if '?' in path else '?'}api-version={api}"
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOK}", "Content-Type": "application/json"},
    )
    for attempt in (1, 2, 3, 4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                d = json.loads(raw)
            except Exception:
                d = {"raw": raw.decode(errors="replace")[:300]}
            if e.code == 429 and attempt < 4:
                time.sleep(20 * attempt)
                continue
            return e.code, d
    return 429, {}


def main():
    st, d = arm("POST", f"/subscriptions/{SUB}/providers/Microsoft.Quota/register", api="2021-04-01")
    print(f"register Microsoft.Quota: {st}")
    if st not in (200, 202):
        print("   ", json.dumps(d)[:400])
    for region in REGIONS:
        cscope = f"/subscriptions/{SUB}/providers/Microsoft.Compute/locations/{region}"
        for name in ["cores"] + FAMILIES:
            body = {
                "properties": {
                    "name": {"value": name},
                    "limit": {"limitObjectType": "LimitValue", "value": CORES},
                }
            }
            st, d = arm("PUT", f"{cscope}/providers/Microsoft.Quota/quotas/{name}", body)
            print(f"{region} {name}: {st}")
            if st not in (200, 201, 202):
                print("   ", json.dumps(d)[:400])
            time.sleep(3)
        nscope = f"/subscriptions/{SUB}/providers/Microsoft.Network/locations/{region}"
        body = {
            "properties": {
                "name": {"value": "StandardSkuPublicIpAddresses"},
                "limit": {"limitObjectType": "LimitValue", "value": PIP_LIMIT},
                "resourceType": "PublicIpAddresses",
            }
        }
        st, d = arm("PUT", f"{nscope}/providers/Microsoft.Quota/quotas/StandardSkuPublicIpAddresses", body)
        print(f"{region} StandardSkuPublicIpAddresses: {st}")
        if st not in (200, 201, 202):
            print("   ", json.dumps(d)[:400])
        time.sleep(1)


if __name__ == "__main__":
    main()
