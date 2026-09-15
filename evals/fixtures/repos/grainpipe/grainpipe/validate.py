"""Row validation against a declarative schema.

A schema maps field names to rules: ``required`` drops rows missing the
field, ``type`` coerces and drops rows whose value does not convert, and
``choices`` whitelists values.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator

Row = dict
Rule = dict
Schema = dict[str, Rule]

_TYPES = {"int": int, "float": float, "str": str}


def _coerce(value, kind: str):
    caster = _TYPES.get(kind)
    if caster is None:
        raise ValueError(f"unknown rule type: {kind}")
    return caster(value)


def validate_rows(schema: Schema):
    def stage(rows: Iterable[Row]) -> Iterator[Row]:
        for row in rows:
            if _row_passes(row, schema):
                yield row

    return stage


def _row_passes(row: Row, schema: Schema) -> bool:
    for field_name, rule in schema.items():
        value = row.get(field_name)
        if value is None:
            if rule.get("required"):
                return False
            continue
        if "type" in rule:
            try:
                row[field_name] = _coerce(value, rule["type"])
            except (TypeError, ValueError):
                return False
        if "choices" in rule and row[field_name] not in rule["choices"]:
            return False
    return True
