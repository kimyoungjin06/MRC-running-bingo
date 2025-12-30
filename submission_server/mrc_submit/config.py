from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    storage_dir: Path
    allowed_origins: list[str]
    api_key: str | None
    admin_key: str | None
    max_file_bytes: int
    max_files: int


def load_settings(*, base_dir: Path) -> Settings:
    host = os.getenv("MRC_SUBMIT_HOST", "0.0.0.0")
    port = _parse_int(os.getenv("MRC_SUBMIT_PORT"), 8787)

    storage_raw = os.getenv("MRC_SUBMIT_STORAGE_DIR", "./storage")
    storage_dir = (base_dir / storage_raw).resolve() if not Path(storage_raw).is_absolute() else Path(storage_raw)

    allowed_origins = _parse_csv(os.getenv("MRC_SUBMIT_ALLOWED_ORIGINS")) or ["*"]
    api_key = os.getenv("MRC_SUBMIT_API_KEY") or None
    admin_key = os.getenv("MRC_ADMIN_KEY") or None

    max_file_mb = _parse_int(os.getenv("MRC_SUBMIT_MAX_FILE_MB"), 15)
    max_files = _parse_int(os.getenv("MRC_SUBMIT_MAX_FILES"), 5)

    return Settings(
        host=host,
        port=port,
        storage_dir=storage_dir,
        allowed_origins=allowed_origins,
        api_key=api_key,
        admin_key=admin_key,
        max_file_bytes=max_file_mb * 1024 * 1024,
        max_files=max_files,
    )
