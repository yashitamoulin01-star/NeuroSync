"""
TokenCipher — authenticated symmetric encryption for OAuth tokens at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) keyed off settings.CONNECTOR_ENCRYPTION_KEY.
If `cryptography` is not installed, the cipher reports itself unavailable and the
service refuses to persist tokens — we degrade SAFE (no storage), never SILENT
(no cleartext on disk).
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from backend.core.config import settings

logger = logging.getLogger("neurosync.connectors.crypto")

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when dep missing
    Fernet = None          # type: ignore
    InvalidToken = Exception  # type: ignore
    _CRYPTO_AVAILABLE = False


def _derive_key(secret: str) -> bytes:
    """Derive a urlsafe-base64 32-byte Fernet key from the configured secret."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class TokenCipher:
    def __init__(self) -> None:
        self._fernet = None
        if _CRYPTO_AVAILABLE:
            try:
                self._fernet = Fernet(_derive_key(settings.CONNECTOR_ENCRYPTION_KEY))
            except Exception as exc:
                logger.error("TokenCipher init failed: %s", exc)
                self._fernet = None

    @property
    def available(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        if plaintext is None:
            return None
        if not self._fernet:
            raise RuntimeError(
                "Token encryption unavailable — install `cryptography` and set "
                "CONNECTOR_ENCRYPTION_KEY. Refusing to store tokens in cleartext."
            )
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        if ciphertext is None:
            return None
        if not self._fernet:
            raise RuntimeError("Token decryption unavailable — `cryptography` not installed.")
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken:
            logger.error("TokenCipher decrypt failed — key rotation or corruption.")
            raise


token_cipher = TokenCipher()
