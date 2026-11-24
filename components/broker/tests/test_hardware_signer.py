import os
import secrets
import time
from pathlib import Path

import pytest

from broker import GATEWAY
from dpop import Verifier, decode
from hardware_signer import HardwareProofClient

BINARY = os.environ.get("SECURE_SIGNER_TEST_BINARY")
pytestmark = pytest.mark.skipif(not BINARY, reason="Set SECURE_SIGNER_TEST_BINARY for hardware tests")


def test_hardware_proofs_and_key_replacement():
    first = HardwareProofClient(Path(BINARY))
    second = HardwareProofClient(Path(BINARY))
    try:
        assert first.jkt != second.jkt
        for endpoint, token in (("https://127.0.0.1:8081/token", None),
                                (GATEWAY, "synthetic-token")):
            verifier = Verifier(endpoint, secrets.token_bytes(32))
            first.nonces[endpoint] = verifier.new_nonce(first.jkt, int(time.time()))
            proof = first.sign(endpoint, token)
            assert len(decode(proof.split(".")[2])) == 64
            verifier.validate([proof], token=token, binding=first.jkt if token else None)
        assert not hasattr(first, "key")
    finally:
        first.close()
        second.close()
    assert first.process.poll() is not None


@pytest.mark.parametrize("operation,fields", [
    ("export", {}), ("proof", {"endpoint": "https://unapproved.invalid/token"}),
    ("proof", {"endpoint": "https://127.0.0.1:8081/token", "token": "unexpected"}),
])
def test_rejected_helper_requests_end_session(operation, fields):
    signer = HardwareProofClient(Path(BINARY))
    try:
        with pytest.raises(ValueError):
            signer.request(operation, **fields)
        assert signer.process.poll() is not None
    finally:
        signer.close()


def test_helper_death_stops_signing():
    signer = HardwareProofClient(Path(BINARY))
    signer.process.kill()
    signer.process.wait()
    try:
        with pytest.raises(ValueError):
            signer.sign(GATEWAY, "synthetic-token")
    finally:
        signer.close()


def test_duplicate_ipc_members_end_helper():
    signer = HardwareProofClient(Path(BINARY))
    try:
        signer.process.stdin.write(b'{"id":"duplicate","op":"public","op":"export"}\n')
        assert signer.process.wait(timeout=3) != 0
    finally:
        signer.close()
