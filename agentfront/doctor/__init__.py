"""``agentfront doctor`` engine — self-diagnosis for an installed agentfront.

The doctor verb is the agent-first contract for "tell me what's wrong and
how to fix it." For agentfront itself it surfaces inconsistencies between the
package, its declared version, the CLI parser tree, the explain catalog,
and the bundled reference tree. It is read-only and fast (no subprocesses,
no network); deeper black-box auditing of *target* CLIs is what
``agentfront cli doctor <path>`` provides via the rubric runner.

Public surface:

- :func:`run_self_diagnosis` — collect every self-check and return a
  :class:`Diagnosis` carrying the flat list of :class:`CheckResult` plus a
  precomputed ``healthy`` flag.
- :class:`Diagnosis` — aggregate (subject, healthy, checks) used by the
  CLI's text/JSON renderers.
- :func:`is_healthy` — returns True when no ``error``-severity check
  failed; mirrors the ``agentfront cli doctor`` non-strict exit-code policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentfront.doctor._self_checks import run_self_checks
from agentfront.doctor.fixes import FixOutcome, apply_fix, register_fix
from agentfront.rubric._types import CheckResult

__all__ = [
    "Diagnosis",
    "FixOutcome",
    "apply_fix",
    "is_healthy",
    "register_fix",
    "run_self_diagnosis",
]


@dataclass(frozen=True)
class Diagnosis:
    """Aggregate result of a doctor run."""

    subject: str  # e.g. "agentfront self" or a target path
    healthy: bool
    checks: list[CheckResult]


def is_healthy(results: list[CheckResult]) -> bool:
    """Healthy ⇔ no ``error``-severity check failed.

    ``warn`` and ``info`` failures do not flip the bit; they are advisory.
    Mirrors the ``agentfront cli doctor`` non-strict exit-code policy.
    """
    return not any(not r.passed and r.severity == "error" for r in results)


def run_self_diagnosis() -> Diagnosis:
    """Run every self-check and return a :class:`Diagnosis`.

    The doctor walks agentfront's own install: pyproject version vs. package
    version, CHANGELOG entry presence, surface coherence between the
    argparse tree and ``learn`` / ``explain``, reference-tree integrity,
    and rubric-module loadability. All in-process, no subprocesses.
    """
    results = run_self_checks()
    return Diagnosis(subject="agentfront self", healthy=is_healthy(results), checks=results)
