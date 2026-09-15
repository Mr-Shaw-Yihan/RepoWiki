"""Command-line interface: argument parsing and subcommand wiring."""
from __future__ import annotations

import argparse
from pathlib import Path

from taskvane.config import load_config
from taskvane.dates import parse_due_date
from taskvane.models import Task
from taskvane.storage import TaskStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskvane")
    parser.add_argument("--store", type=Path, default=None, help="override the store file")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="add a task")
    add.add_argument("title")
    add.add_argument("--priority", default="normal")
    add.add_argument("--due", default=None)

    ls = sub.add_parser("list", help="list tasks")
    ls.add_argument("--open", action="store_true", help="only open tasks")

    done = sub.add_parser("done", help="mark a task done")
    done.add_argument("task_id", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    store = TaskStore(args.store or config.store_path)

    if args.command == "add":
        task = Task(title=args.title, priority=args.priority, due=parse_due_date(args.due))
        store.add(task)
        print(f"added #{task.id}: {task.title}")
        return 0
    if args.command == "list":
        for task in store.list(open_only=args.open):
            print(f"#{task.id} [{task.priority}] {task.title}")
        return 0
    if args.command == "done":
        store.mark_done(args.task_id)
        return 0
    return 2
