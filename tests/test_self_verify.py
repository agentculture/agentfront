"""Acceptance gate: afi-cli must pass its own six-bundle rubric.

This is what makes afi a first citizen of the rubric it publishes. If any
rubric check regresses — `learn` drops below 200 chars, `explain` loses an
entry, an error handler swallows the traceback — this test fails and blocks
the commit.

The rubric runs in-process: a ``VerifyContext`` is built pointed at the
repo root, with a :class:`SubprocessRunner` that invokes ``afi`` via the
dev venv's ``afi`` script.
"""

from __future__ import annotations

from pathlib import Path

from afi.rubric import run_rubric
from afi.rubric._runner import SubprocessRunner
from afi.rubric._types import VerifyContext

REPO_ROOT = Path(__file__).resolve().parent.parent


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


def test_self_verify_covers_all_six_bundles() -> None:
    ctx = VerifyContext(
        target_path=REPO_ROOT,
        tool_name="afi",
        runner=SubprocessRunner(cwd=REPO_ROOT, tool_name="afi"),
    )

    results = run_rubric(ctx)

    bundles = {r.bundle for r in results}
    assert bundles == {"structure", "learnability", "json", "errors", "explain", "overview"}
