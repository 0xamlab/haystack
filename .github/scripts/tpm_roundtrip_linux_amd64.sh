#!/usr/bin/env bash
# TpmKeyStore round-trip against a real TPM 2.0 software stack (swtpm + libtss2 + tpm2-pytss),
# executed inside an ubuntu:22.04 container (tpm.yml mounts the checkout at /work). The TPM
# stack is Linux-only and installed as root with apt, so the container keeps it off the runner.
# Same container pattern as clean_machine_contract_linux_amd64.sh.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null
# libtss2-tcti-swtpm0 is the TCTI connector tpm2-pytss dlopens for TCTI=swtpm:... --
# libtss2-dev alone does not pull it ('Could not initialize TCTI file: swtpm').
apt-get install -y -qq --no-install-recommends \
  swtpm swtpm-tools tpm2-tools libtss2-dev libtss2-tcti-swtpm0 \
  build-essential pkg-config curl xz-utils ca-certificates >/dev/null

# CPython 3.14 via uv (ubuntu:22.04's distro python is 3.10; tpm2-pytss builds against the
# libtss2 headers above when no matching wheel exists for this interpreter).
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
export PATH=/root/.local/bin:$PATH
uv python install 3.14 >/dev/null
PY="$(uv python find 3.14)"
"$PY" -m venv /tmp/tpm-venv
. /tmp/tpm-venv/bin/activate
python -m pip install --quiet --disable-pip-version-check "tpm2-pytss" cryptography structlog

# Start swtpm (TCP). Three container realities, each found the hard way; the flags are kept
# as-is because they are harmless natively and each one closed a real hang:
#  1. swtpm_setup is skipped entirely (it deadlocked with 0% CPU, with or without
#     --create-ek-cert): --flags not-need-init,startup-clear lets swtpm socket create fresh
#     TPM state on its own (verified).
#  2. swtpm's seccomp filter install can fail inside a container (errno 125) and kill the
#     process -- --seccomp action=none disables it (safe: disposable CI container).
#  3. --daemon's double-fork was unreliable -- plain background instead.
STATE=/tmp/swtpm
mkdir -p "$STATE"
swtpm socket --tpm2 --tpmstate dir="$STATE" \
  --server type=tcp,port=2321,bindaddr=127.0.0.1 \
  --ctrl type=tcp,port=2322,bindaddr=127.0.0.1 \
  --flags not-need-init,startup-clear \
  --seccomp action=none > "$STATE/swtpm.log" 2>&1 &
swtpm_up=0
for i in $(seq 1 40); do
  if (exec 3<>/dev/tcp/127.0.0.1/2321) 2>/dev/null; then exec 3>&- 3<&-; swtpm_up=1; echo "swtpm up"; break; fi
  sleep 0.25
done
if [ "$swtpm_up" -ne 1 ]; then
  echo "::error::swtpm never came up on 127.0.0.1:2321"
  ps aux | grep -E "swtpm" | grep -v grep || true
  ls -la "$STATE" || true
  exit 1
fi

export ALGENTA_TPM_TCTI="swtpm:host=localhost,port=2321"
export ALGENTA_RUNTIME_DIR=/tmp/algenta-runtime
export PYTHONDONTWRITEBYTECODE=1 # keep the mounted checkout free of root-owned __pycache__

python - <<'PY'
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.exceptions import InvalidSignature

from apps.runtime.hardware_key_store import TpmKeyStore
from apps.runtime.device_keypair import thumbprint_for_public_pem, verify_signature

ks = TpmKeyStore()
assert ks.available(), "TPM backend must be available (swtpm) in CI"

# public key is a genuine secp256r1 SPKI
pem = ks.public_pem()
pub = serialization.load_pem_public_key(pem.encode())
assert isinstance(pub, ec.EllipticCurvePublicKey) and isinstance(pub.curve, ec.SECP256R1), "not P-256"

# sign in the TPM; verify with the exported public key; tamper must fail
msg = b"algenta license nonce"
der = ks.sign(msg)
pub.verify(der, msg, ec.ECDSA(hashes.SHA256()))            # raises InvalidSignature on failure
r, s = decode_dss_signature(der)                           # valid DER if this parses
assert 0 < r < (1 << 256) and 0 < s < (1 << 256), "DER Ecdsa-Sig-Value out of range"
try:
    pub.verify(der, b"tampered", ec.ECDSA(hashes.SHA256())); raise AssertionError("tamper verified!")
except InvalidSignature:
    pass

# algorithm-agnostic verify path + thumbprint (matches the SE / server convention)
assert verify_signature(pem, msg, der) is True
tp = ks.public_key_thumbprint()
assert tp.startswith("secp256r1:"), tp
assert thumbprint_for_public_pem(pem) == tp                # server recompute agrees

# many signs don't exhaust TPM transient slots (leaf+primary flushed each call)
for _ in range(12):
    d = ks.sign(b"beat")
    pub.verify(d, b"beat", ec.ECDSA(hashes.SHA256()))

# cross-process reload: a fresh store instance yields the SAME key (persisted blobs)
assert TpmKeyStore().public_pem() == pem
assert TpmKeyStore().public_key_thumbprint() == tp
print("TPM round-trip OK")
PY

echo "tpm round-trip container OK"
