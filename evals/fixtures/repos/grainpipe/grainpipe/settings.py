"""Pipeline settings loaded from a YAML file."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


@dataclass
class Settings:
    source: Path
    target: Path
    table: str = "rows"
    schema: dict = field(default_factory=dict)


def load_settings(path: Path) -> Settings:
    if yaml is None:
        raise RuntimeError("pyyaml is required to load pipeline settings")
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Settings(
        source=Path(raw["source"]),
        target=Path(raw["target"]),
        table=raw.get("table", "rows"),
        schema=raw.get("schema", {}),
    )
