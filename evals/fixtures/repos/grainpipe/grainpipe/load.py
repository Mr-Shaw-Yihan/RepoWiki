"""SQLite writer stage."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

Row = dict


def write_sqlite(path: Path, table: str):
    connection = sqlite3.connect(Path(path))
    columns: list[str] | None = None
    inserted = 0

    def stage(rows: Iterable[Row]) -> Iterator[Row]:
        nonlocal columns, inserted
        for row in rows:
            if columns is None:
                columns = list(row.keys())
                ddl = ", ".join(f'"{name}" TEXT' for name in columns)
                connection.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({ddl})')
            placeholders = ", ".join("?" for _ in columns)
            connection.execute(
                f'INSERT INTO "{table}" VALUES ({placeholders})',
                [str(row.get(name, "")) for name in columns],
            )
            inserted += 1
            if inserted % 500 == 0:
                connection.commit()
            yield row

    def finalize(stream):
        yield from stream
        connection.commit()
        connection.close()

    return lambda rows: finalize(stage(rows))
