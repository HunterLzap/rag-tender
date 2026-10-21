import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings


@dataclass(frozen=True)
class StoredFile:
    path: Path
    sha256: str
    size: int


def store_upload(filename: str, content: bytes) -> StoredFile:
    settings = get_settings()
    digest = hashlib.sha256(content).hexdigest()
    suffix = Path(filename).suffix.lower()
    directory = settings.uploads_dir / digest[:2]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}{suffix}"
    if not path.exists():
        tmp = path.with_suffix(f"{path.suffix}.tmp")
        tmp.write_bytes(content)
        os.replace(tmp, path)
    return StoredFile(path=path, sha256=digest, size=len(content))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
