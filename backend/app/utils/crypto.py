"""Encryption helpers for stored API secrets."""

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.utils.mask import mask_key

SECRET_KEY_ENV = "RAG_TENDER_SECRET_KEY"
ENCRYPTED_PREFIX = "enc:"


def is_encrypted_secret(value: Optional[str]) -> bool:
    """Return True when a stored secret uses the encrypted value format."""
    return bool(value and value.startswith(ENCRYPTED_PREFIX))


def _get_fernet() -> Fernet:
    """Build a Fernet cipher from the configured environment key."""
    key = (os.getenv(SECRET_KEY_ENV) or "").strip()
    if not key:
        raise RuntimeError(
            f"未配置环境变量 {SECRET_KEY_ENV}，无法加密或解密 API Key"
        )
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"环境变量 {SECRET_KEY_ENV} 不是有效的 Fernet 密钥，请重新生成"
        ) from exc


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    """Encrypt a plaintext secret for database storage."""
    if value is None or value == "":
        return value
    if is_encrypted_secret(value):
        return value
    token = _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    """Decrypt a stored secret. Legacy plaintext values are returned as-is."""
    if value is None or value == "":
        return value
    if not is_encrypted_secret(value):
        return value
    token = value[len(ENCRYPTED_PREFIX) :]
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("API Key 解密失败，请检查 RAG_TENDER_SECRET_KEY 是否正确") from exc


def mask_stored_secret(value: Optional[str]) -> Optional[str]:
    """Mask a stored secret without exposing ciphertext to callers."""
    if value is None or value == "":
        return mask_key(value)
    if is_encrypted_secret(value):
        return mask_key(decrypt_secret(value))
    return mask_key(value)
