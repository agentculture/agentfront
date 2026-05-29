"""Core types for the rubric engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

Severity = Literal["error", "warn", "info"]


@dataclass(frozen=True)
class RunOutput:
    """Captured output of a subprocess invocation."""

    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    """Runs ``<tool> <args>`` in the target project and returns its output."""

    def run(self, args: list[str], *, timeout: float = 10.0) -> RunOutput: ...


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single check.

    ``severity`` is only meaningful when ``passed`` is False — it tells the
    verifier whether this counts as a hard failure (``error``), a
    recommendation (``warn``), or informational (``info``).

    ``auto_fixable`` and ``fix_id`` are doctor's contract: when a failed check
    declares ``auto_fixable=True`` and a non-empty ``fix_id``, ``agentfront doctor
    --fix`` will look the id up in :mod:`agentfront.doctor.fixes` and apply the
    handler. Checks that need a code edit must leave both at the defaults.
    """

    bundle: str
    check: str
    passed: bool
    severity: Severity
    evidence: str
    remediation: str = ""
    auto_fixable: bool = False
    fix_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "bundle": self.bundle,
            "check": self.check,
            "passed": self.passed,
            "severity": self.severity,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "auto_fixable": self.auto_fixable,
            "fix_id": self.fix_id,
        }


@dataclass
class VerifyContext:
    """Everything a checker needs about the target project."""

    target_path: Path
    tool_name: str
    runner: Runner
    repo_files: list[Path] = field(default_factory=list)
