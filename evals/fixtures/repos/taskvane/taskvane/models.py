"""Task record and field validation."""
from __future__ import annotations

from dataclasses import dataclass, field

PRIORITIES = ("low", "normal", "high", "urgent")


def validate_priority(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in PRIORITIES:
        raise ValueError(f"priority must be one of {PRIORITIES}, got {value!r}")
    return normalized


@dataclass
class Task:
    title: str
    priority: str = "normal"
    due: str | None = None
    done: bool = False
    id: int | None = field(default=None)

    def __post_init__(self) -> None:
        self.priority = validate_priority(self.priority)
        if not self.title.strip():
            raise ValueError("title must not be empty")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "due": self.due,
            "done": self.done,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Task":
        return cls(
            title=raw["title"],
            priority=raw.get("priority", "normal"),
            due=raw.get("due"),
            done=bool(raw.get("done", False)),
            id=raw.get("id"),
        )
