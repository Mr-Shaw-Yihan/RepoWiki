"""Pipeline composition and execution.

A pipeline is an ordered list of stages. Each stage receives an iterable of
rows and returns an iterable of rows, so stages compose lazily: no data
materializes between stages unless a stage itself buffers.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

Row = dict
Stage = Callable[[Iterable[Row]], Iterable[Row]]


class Pipeline:
    def __init__(self, stages: list[Stage] | None = None):
        self.stages: list[Stage] = list(stages or [])

    def then(self, stage: Stage) -> "Pipeline":
        self.stages.append(stage)
        return self

    def run(self, rows: Iterable[Row]) -> Iterator[Row]:
        stream: Iterable[Row] = rows
        for stage in self.stages:
            stream = stage(stream)
        yield from stream

    def collect(self, rows: Iterable[Row]) -> list[Row]:
        return list(self.run(rows))
