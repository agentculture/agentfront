"""``afi doctor`` engine — self-diagnosis for an installed afi.

The doctor verb is the agent-first contract for "tell me what's wrong and
how to fix it." For afi itself it surfaces inconsistencies between the
package, its declared version, the CLI parser tree, the explain catalog,
and the bundled reference tree. It is read-only and fast (no subprocesses,
no network); deeper black-box auditing of *target* CLIs is what
``afi cli doctor <path>`` provides via the rubric runner.

Public surface:

- :func:`run_self_diagnosis` — collect every self-check and return a flat
  ``list[CheckResult]``.
- :class:`Diagnosis` — convenience aggregate carrying ``healthy`` plus the
  same list of results, used by the CLI's text/JSON renderers.
- :func:`is_healthy` — returns True when no ``error``-severity check fails.
"""

from __future__ import annotations

from dataclasses import dataclass

from afi.doctor._self_checks import run_self_checks
from afi.doctor.fixes import FixOutcome, apply_fix, register_fix
from afi.rubric._types import CheckResult

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

    subject: str  # e.g. "afi self" or a target path
    healthy: bool
    checks: list[CheckResult]


def is_healthy(results: list[CheckResult]) -> bool:
    """Healthy ⇔ no ``error``-severity check failed.

    ``warn`` and ``info`` failures do not flip the bit; they are advisory.
    Mirrors the ``afi cli verify`` non-strict exit-code policy.
    """
    return not any(not r.passed and r.severity == "error" for r in results)


def run_self_diagnosis() -> Diagnosis:
    """Run every self-check and return a :class:`Diagnosis`.

    The doctor walks afi's own install: pyproject version vs. package
    version, CHANGELOG entry presence, surface coherence between the
    argparse tree and ``learn`` / ``explain``, reference-tree integrity,
    and rubric-module loadability. All in-process, no subprocesses.
    """
    results = run_self_checks()
    return Diagnosis(subject="afi self", healthy=is_healthy(results), checks=results)
