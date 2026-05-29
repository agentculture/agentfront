"""Shared fake Runner for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentfront.rubric._types import RunOutput


@dataclass
class FakeRunner:
    """Runner that returns canned output for given argv tuples."""

    responses: dict[tuple[str, ...], RunOutput] = field(default_factory=dict)
    default: RunOutput = field(default_factory=lambda: RunOutput(0, "", ""))
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def run(self, args: list[str], *, timeout: float = 10.0) -> RunOutput:
        # `timeout` is part of the Runner protocol; the fake doesn't run
        # subprocesses, so the value is intentionally discarded.
        del timeout
        key = tuple(args)
        self.calls.append(key)
        return self.responses.get(key, self.default)
