import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE / "golden"))

import secrets  # noqa: E402

import pytest  # noqa: E402

from caesar import keystore  # noqa: E402

REAL_LOAD_KEY = keystore.load_key


@pytest.fixture(autouse=True)
def test_keychain(monkeypatch):
    """Tests never touch the person's keychain: each test gets an in-memory one. A test that needs
    no keychain at all patches load_key again; the keychain round trip test uses REAL_LOAD_KEY."""
    keys = {}

    def load_key(create, service=keystore.SERVICE):
        if service not in keys and create:
            keys[service] = secrets.token_bytes(32)
        return (keys[service], "") if service in keys else (None, "the test keychain has no ledger key yet")

    monkeypatch.setattr(keystore, "load_key", load_key)
    monkeypatch.delenv("LOCAL_STUDIO_ASK", raising=False)
    monkeypatch.delenv("LOCAL_STUDIO_ASK_TOKEN", raising=False)
    monkeypatch.delenv("LOCAL_STUDIO_ASK_PID", raising=False)
    return keys
