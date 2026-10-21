import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _load_key() -> bytes:
    settings = get_settings()
    if settings.secret_key:
        return settings.secret_key.encode()

    key_path = settings.resolved_data_dir / ".secret_key"
    if key_path.exists():
        return key_path.read_bytes().strip()

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    os.chmod(Path(key_path), 0o600)
    return key


def encrypt_secret(value: str) -> str:
    return Fernet(_load_key()).encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return Fernet(_load_key()).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("无法解密 API Key，请重新保存模型配置") from exc


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"****{value[-4:]}"
