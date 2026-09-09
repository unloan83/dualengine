from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import DualEngineShadowRecord


class ShadowLogger:
    def __init__(self, log_path: str | Path, max_bytes: int = 10_000_000, backup_count: int = 5):
        self.path = Path(log_path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.backup_count = backup_count

    def log_record(self, record: DualEngineShadowRecord) -> None:
        self._rotate_if_needed()
        data = record.to_dict()
        line = json.dumps(data, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)

    def log_records(self, records: list[DualEngineShadowRecord]) -> None:
        for r in records:
            self.log_record(r)

    def _rotate_if_needed(self) -> None:
        if not self.path.exists():
            return
        try:
            if self.path.stat().st_size >= self.max_bytes:
                for i in range(self.backup_count - 1, 0, -1):
                    s = self.path.with_suffix(f".jsonl.{i}")
                    d = self.path.with_suffix(f".jsonl.{i + 1}")
                    if s.exists():
                        s.replace(d)
                self.path.replace(self.path.with_suffix(".jsonl.1"))
        except Exception:
            pass
