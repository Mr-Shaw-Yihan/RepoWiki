"""User configuration loaded from ~/.config/taskvane/config.json."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    store_path: Path


def default_store_path() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "taskvane" / "tasks.json"


def load_config(path: Path | None = None) -> Config:
    path = path or Path.home() / ".config" / "taskvane" / "config.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if "store_path" in raw:
            return Config(store_path=Path(raw["store_path"]))
    return Config(store_path=default_store_path())
