"""Due-date parsing and validation.

Accepted formats are ISO ``YYYY-MM-DD`` and the shorthand ``+Nd`` / ``+Nw``
for days and weeks from today.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

_SHORTHAND = re.compile(r"^\+(\d+)([dw])$")


def parse_due_date(value: str | None, *, today: date | None = None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    match = _SHORTHAND.match(value)
    if match:
        amount = int(match.group(1))
        base = today or date.today()
        delta = timedelta(days=amount if match.group(2) == "d" else amount * 7)
        return (base + delta).isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f"due date must be YYYY-MM-DD or +Nd/+Nw, got {value!r}") from None
