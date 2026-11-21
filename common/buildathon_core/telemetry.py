"""A tiny timing tracer.

His ``pipeline_core`` ships a ``Tracer`` that builds one span tree and one cost
roll-up across a whole pipeline. There is no LLM cost here, so the analog is a
wall-clock roll-up: how long each solution took to score, which is the "selector
CPU per batch" / "~25s grid search" kind of number the track READMEs report.
Pure stdlib, no dependency.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Span:
    name: str
    seconds: float


@dataclass
class Tracer:
    spans: list[Span] = field(default_factory=list)

    @contextmanager
    def span(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.spans.append(Span(name, time.perf_counter() - t0))

    @property
    def total_seconds(self) -> float:
        return sum(s.seconds for s in self.spans)

    def tree(self) -> str:
        lines = [f"total {self.total_seconds:.2f}s"]
        for s in self.spans:
            lines.append(f"  {s.name}: {s.seconds:.2f}s")
        return "\n".join(lines)
