"""Agent-first rubric — seven bundles of checks.

Public API:

* :class:`VerifyContext` — carries target path, tool name, subprocess runner.
* :func:`run_rubric` — invokes every checker in the default rubric and
  returns a flat ``list[CheckResult]``.
* :func:`default_rubric` — the ordered list of bundles shipped with agentfront.

Individual checker modules live under :mod:`agentfront.rubric.checks`.
"""

from __future__ import annotations

from agentfront.rubric._types import CheckResult, RunOutput, Severity, VerifyContext
from agentfront.rubric.checks import doctor as _doctor_checks
from agentfront.rubric.checks import errors as _errors_checks
from agentfront.rubric.checks import explain_cmd as _explain_checks
from agentfront.rubric.checks import json_output as _json_checks
from agentfront.rubric.checks import learnability as _learn_checks
from agentfront.rubric.checks import overview_cmd as _overview_checks
from agentfront.rubric.checks import structure as _structure_checks


def default_rubric() -> list:
    """Return the default ordered list of bundle modules."""
    return [
        _structure_checks,
        _learn_checks,
        _json_checks,
        _errors_checks,
        _explain_checks,
        _overview_checks,
        _doctor_checks,
    ]


def run_rubric(ctx: VerifyContext) -> list[CheckResult]:
    """Run every bundle's checks against ``ctx`` and return a flat result list."""
    results: list[CheckResult] = []
    for bundle in default_rubric():
        results.extend(bundle.run(ctx))
    return results


__all__ = [
    "CheckResult",
    "RunOutput",
    "Severity",
    "VerifyContext",
    "default_rubric",
    "run_rubric",
]
