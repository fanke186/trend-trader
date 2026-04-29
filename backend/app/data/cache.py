from __future__ import annotations

from pathlib import Path

import json

from app.models import DailyBar


class BarCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, symbol: str, bars: list[DailyBar]) -> None:
        if not bars:
            return
        path = self.root / f"{symbol}.json"
        path.write_text(
            json.dumps([bar.model_dump(mode="json") for bar in bars], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, symbol: str) -> list[DailyBar]:
        path = self.root / f"{symbol}.json"
        if not path.exists():
            return []
        rows = json.loads(path.read_text(encoding="utf-8"))
        return [DailyBar(**row) for row in rows]
