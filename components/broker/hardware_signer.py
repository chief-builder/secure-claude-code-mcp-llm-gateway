"""Bounded pipe client for the session-scoped Secure Enclave helper."""

import json
import os
import selectors
import subprocess
import threading
import time
import uuid

from cryptography.hazmat.primitives.asymmetric import ec

from dpop import decode, thumbprint
from foundation import read_object
from lab_invoke import ProofClient


class HardwareProofClient(ProofClient):
    def __init__(self, executable):
        self.nonces = {}
        self.lock = threading.Lock()
        self.buffer = bytearray()
        self.process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        close_fds=True, bufsize=0)
        try:
            response = self.request("public")
            self.jwk = response["jwk"]
            if set(self.jwk) != {"kty", "crv", "x", "y"} or self.jwk["kty"] != "EC" or self.jwk["crv"] != "P-256":
                raise ValueError("Invalid signer key")
            x, y = decode(self.jwk["x"]), decode(self.jwk["y"])
            if len(x) != 32 or len(y) != 32:
                raise ValueError("Invalid signer key")
            ec.EllipticCurvePublicNumbers(int.from_bytes(x, "big"), int.from_bytes(y, "big"),
                                         ec.SECP256R1()).public_key()
            self.jkt = thumbprint(self.jwk)
        except BaseException:
            self.close()
            raise

    def request(self, operation, **fields):
        with self.lock:
            identity = str(uuid.uuid4()).upper()
            body = json.dumps({"id": identity, "op": operation, **fields},
                              sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            if len(body) > 24576 or self.process.poll() is not None:
                raise ValueError("Hardware signer unavailable")
            try:
                self.process.stdin.write(body + b"\n")
                deadline = time.monotonic() + 5
                with selectors.DefaultSelector() as selector:
                    selector.register(self.process.stdout, selectors.EVENT_READ)
                    while b"\n" not in self.buffer:
                        if not selector.select(max(0, deadline - time.monotonic())):
                            raise ValueError("Hardware signer timeout")
                        chunk = os.read(self.process.stdout.fileno(), 4096)
                        if not chunk or len(self.buffer) + len(chunk) > 16384:
                            raise ValueError("Hardware signer unavailable")
                        self.buffer.extend(chunk)
                line, _, remainder = self.buffer.partition(b"\n")
                self.buffer = bytearray(remainder)
                result = read_object(line)
                expected = {"id", "jwk"} if operation == "public" else {"id", "proof"}
                if set(result) != expected or result["id"] != identity:
                    raise ValueError("Invalid signer response")
                return result
            except (OSError, ValueError):
                self.close()
                raise ValueError("Hardware signer unavailable") from None

    def sign(self, endpoint, token=None):
        fields = {"endpoint": endpoint}
        if token is not None:
            fields["token"] = token
        if endpoint in self.nonces:
            fields["nonce"] = self.nonces[endpoint]
        proof = self.request("proof", **fields)["proof"]
        if not isinstance(proof, str) or len(proof) > 8192:
            self.close()
            raise ValueError("Invalid hardware proof")
        return proof

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for pipe in (self.process.stdin, self.process.stdout):
            if pipe is not None:
                pipe.close()
