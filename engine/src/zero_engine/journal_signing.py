"""Journal signing-key loading.

Private keys are loaded only from process environment. They are never written
to root files; roots contain only the public key and signature.
"""
from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from typing import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from zero_engine.journal_chain import JournalChainError


SIGNING_KEY_ENV = "ZERO_JOURNAL_SIGNING_KEY_B64"
SIGNING_KEY_ID_ENV = "ZERO_JOURNAL_SIGNING_KEY_ID"
DEFAULT_SIGNING_KEY_ID = "deployment-ed25519-v1"


@dataclass(frozen=True)
class JournalSigningKey:
    """Loaded Ed25519 signing key with stable key id."""

    key_id: str
    private_key: Ed25519PrivateKey


def _b64decode_padded(value: str) -> bytes:
    normalized = value.strip()
    padding = "=" * (-len(normalized) % 4)
    try:
        return base64.urlsafe_b64decode(normalized + padding)
    except (ValueError, binascii.Error) as exc:
        raise JournalChainError(f"{SIGNING_KEY_ENV} is not valid base64") from exc


def load_signing_key_from_env(
    environ: Mapping[str, str] | None = None,
) -> JournalSigningKey | None:
    """Load the journal Ed25519 signing key from environment if present.

    Supported formats:
    - raw 32-byte Ed25519 private key, base64/base64url encoded,
    - PEM Ed25519 private key, base64/base64url encoded.
    """
    env = environ or os.environ
    encoded = env.get(SIGNING_KEY_ENV, "").strip()
    if not encoded:
        return None

    raw = _b64decode_padded(encoded)
    key_id = env.get(SIGNING_KEY_ID_ENV, DEFAULT_SIGNING_KEY_ID).strip() or DEFAULT_SIGNING_KEY_ID
    if len(raw) == 32:
        return JournalSigningKey(key_id=key_id, private_key=Ed25519PrivateKey.from_private_bytes(raw))

    if raw.startswith(b"-----BEGIN"):
        key = load_pem_private_key(raw, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise JournalChainError(f"{SIGNING_KEY_ENV} must contain an Ed25519 private key")
        return JournalSigningKey(key_id=key_id, private_key=key)

    raise JournalChainError(f"{SIGNING_KEY_ENV} must decode to a 32-byte Ed25519 key or PEM")
