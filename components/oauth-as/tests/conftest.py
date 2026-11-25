import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from foundation import POLICY, provision


@pytest.fixture
def local(tmp_path):
    keys = tmp_path / "keys"
    provision(keys)
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps(POLICY))
    return keys, policy


@pytest.fixture(scope="module")
def upstream_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)
