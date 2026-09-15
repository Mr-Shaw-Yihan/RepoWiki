"""JSON-file persistence for tasks.

Tasks are stored as a list of objects in a single JSON document. The file is
rewritten atomically on every mutation so a crash cannot leave a half-written
store behind.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from taskvane.models import Task


class TaskStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: list[Task] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._tasks = [Task.from_dict(item) for item in raw.get("tasks", [])]

    def _save(self) -> None:
        payload = {"tasks": [t.to_dict() for t in self._tasks]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, task: Task) -> None:
        task.id = max((t.id or 0 for t in self._tasks), default=0) + 1
        self._tasks.append(task)
        self._save()

    def list(self, open_only: bool = False) -> list[Task]:
        if open_only:
            return [t for t in self._tasks if not t.done]
        return list(self._tasks)

    def mark_done(self, task_id: int) -> None:
        for task in self._tasks:
            if task.id == task_id:
                task.done = True
                self._save()
                return
        raise KeyError(f"no task #{task_id}")
