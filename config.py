from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DualEngineConfig:
    upstox_access_token: str
    poll_interval_seconds: int = 300
    log_file_path: str = "logs/dualengine_shadow.jsonl"
    symbols: tuple[str, ...] = (
        "RELIANCE",
        "TCS",
        "INFY",
        "HDFCBANK",
        "ICICIBANK",
        "SBIN",
        "BHARTIARTL",
        "ITC",
        "LT",
        "AXISBANK",
    )
    timezone: str = "Asia/Kolkata"
    max_batch_size: int = 500


def load_config(root_dir: Path | None = None) -> DualEngineConfig:
    root = (root_dir or Path(__file__).resolve().parent).resolve()

    # Load from .env file in root if present
    env_file = root / ".env"
    if not env_file.exists():
        # Check fallback location for credentials in parent directory
        parent_cred = root.parent / "Upstox_Credentials.env"
        if parent_cred.exists():
            env_file = parent_cred

    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token and env_file.exists():
        token = _parse_env_key(env_file, "UPSTOX_ACCESS_TOKEN")

    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
    log_path = os.getenv("LOG_FILE_PATH", "logs/dualengine_shadow.jsonl")

    raw_symbols = os.getenv("SYMBOLS", "")
    if raw_symbols.strip():
        symbols = tuple(s.strip().upper() for s in raw_symbols.split(",") if s.strip())
    else:
        symbols = (
            "RELIANCE",
            "TCS",
            "INFY",
            "HDFCBANK",
            "ICICIBANK",
            "SBIN",
            "BHARTIARTL",
            "ITC",
            "LT",
            "AXISBANK",
        )

    return DualEngineConfig(
        upstox_access_token=token,
        poll_interval_seconds=poll_interval,
        log_file_path=log_path,
        symbols=symbols,
    )


def _parse_env_key(file_path: Path, key: str) -> str:
    if not file_path.exists():
        return ""
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip("'\"")
    return ""
