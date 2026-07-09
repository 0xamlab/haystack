"""TPM 2.0 device-key backend (apps/runtime/hardware_key_store.TpmKeyStore).

Skipped unless a TPM is reachable — tpm2-pytss imports AND a TCTI connects (set ALGENTA_TPM_TCTI, e.g.
``swtpm:host=localhost,port=2321`` for a simulator or ``device:/dev/tpmrm0`` on real HW). So it runs on a
TPM/swtpm host and is silently skipped on the macOS dev laptop (no libtss2) and in the lean unit CI.

The authoritative TPM validation runs in .github/workflows/tpm.yml (ubuntu + swtpm); this mirrors it for
local / real-hardware use.
"""
from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from apps.runtime.device_keypair import thumbprint_for_public_pem, verify_signature
from apps.runtime.hardware_key_store import TpmKeyStore

pytestmark = pytest.mark.skipif(
    not TpmKeyStore().available(),
    reason="no TPM reachable (set ALGENTA_TPM_TCTI to a TPM/swtpm and install tpm2-pytss)",
)


def _pub(store: TpmKeyStore):
    return serialization.load_pem_public_key(store.public_pem().encode())


def test_public_pem_is_secp256r1_spki() -> None:
    pub = _pub(TpmKeyStore())
    assert isinstance(pub, ec.EllipticCurvePublicKey)
    assert isinstance(pub.curve, ec.SECP256R1)


def test_roundtrip_verify_and_tamper() -> None:
    ks = TpmKeyStore()
    pub = _pub(ks)
    der = ks.sign(b"nonce")
    pub.verify(der, b"nonce", ec.ECDSA(hashes.SHA256()))  # no raise
    with pytest.raises(InvalidSignature):
        pub.verify(der, b"tampered", ec.ECDSA(hashes.SHA256()))


def test_der_is_valid_dss() -> None:
    r, s = decode_dss_signature(TpmKeyStore().sign(b"x"))
    order = ec.SECP256R1().key_size  # 256
    assert 0 < r < (1 << order) and 0 < s < (1 << order)


def test_algorithm_agnostic_verify_and_thumbprint() -> None:
    ks = TpmKeyStore()
    pem = ks.public_pem()
    der = ks.sign(b"m")
    assert verify_signature(pem, b"m", der) is True
    tp = ks.public_key_thumbprint()
    assert tp.startswith("secp256r1:")
    assert thumbprint_for_public_pem(pem) == tp  # server recompute agrees


def test_thumbprint_is_stable_across_instances() -> None:
    # reloads the persisted TPM-wrapped blobs rather than minting a fresh key each call
    assert TpmKeyStore().public_key_thumbprint() == TpmKeyStore().public_key_thumbprint()


def test_many_signs_dont_exhaust_transients() -> None:
    ks = TpmKeyStore()
    pub = _pub(ks)
    for _ in range(12):  # leaf + primary must be flushed each call (real-HW slot exhaustion guard)
        der = ks.sign(b"beat")
        pub.verify(der, b"beat", ec.ECDSA(hashes.SHA256()))
