"""Row readers for CSV and JSON inputs."""
from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

Row = dict


def read_csv(path: Path, *, delimiter: str = ",") -> Iterator[Row]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle, delimiter=delimiter)


def read_json(path: Path) -> Iterator[Row]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"expected a JSON array of rows in {path}")
    yield from raw


def read_any(path: Path) -> Iterable[Row]:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return read_csv(path)
    if suffix == ".json":
        return read_json(path)
    raise ValueError(f"unsupported input format: {suffix}")
