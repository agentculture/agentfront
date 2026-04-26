"""Acceptance gate: afi-cli must pass its own seven-bundle rubric and self-doctor.

This is what makes afi a first citizen of the rubric it publishes. If any
rubric check regresses — ``learn`` drops below 200 chars, ``explain``
loses an entry, an error handler swallows the traceback, the new
``doctor`` verb breaks — this test fails and blocks the commit.

The rubric runs via subprocess: a :class:`VerifyContext` is built pointed
at the repo root, with a :class:`SubprocessRunner` that invokes ``afi``
via the dev venv's ``afi`` script.

The self-doctor runs in-process (no subprocess) so we also assert it
returns ``healthy=True`` against the live source tree — a faster signal
than the subprocess bundle audit when surface drift creeps in.
"""

from __future__ import annotations

from pathlib import Path

from afi.doctor import run_self_diagnosis
from afi.rubric import run_rubric
from afi.rubric._runner import SubprocessRunner
from afi.rubric._types import VerifyContext

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_BUNDLES = {
    "structure",
    "learnability",
    "json",
    "errors",
    "explain",
    "overview",
    "doctor",
}


def test_self_verify_passes_every_bundle() -> None:
    ctx = VerifyContext(
        target_path=REPO_ROOT,
        tool_name="afi",
        runner=SubprocessRunner(cwd=REPO_ROOT, tool_name="afi"),
    )

    results = run_rubric(ctx)

    errors = [r for r in results if not r.passed and r.severity == "error"]
    assert not errors, "\n".join(
        f"[{r.bundle}] {r.check}: {r.evidence} — hint: {r.remediation}" for r in errors
    )


def test_self_verify_covers_all_seven_bundles() -> None:
    ctx = VerifyContext(
        target_path=REPO_ROOT,
        tool_name="afi",
        runner=SubprocessRunner(cwd=REPO_ROOT, tool_name="afi"),
    )

    results = run_rubric(ctx)

    bundles = {r.bundle for r in results}
    assert bundles == EXPECTED_BUNDLES


def test_self_doctor_reports_healthy_in_process() -> None:
    """In-process self-diagnosis catches surface drift faster than the bundle audit.

    No subprocess; the doctor walks the live source tree's argparse
    parser, learn payload, explain catalog, reference manifest, and
    rubric module list. Any drift between these surfaces fails this
    test before CI runs the slower bundle audit above.
    """
    diagnosis = run_self_diagnosis()
    failed = [r for r in diagnosis.checks if not r.passed and r.severity == "error"]
    assert diagnosis.healthy, "\n".join(
        f"[{r.bundle}] {r.check}: {r.evidence} — hint: {r.remediation}" for r in failed
    )
