"""Bundle 2 — learnability (``<tool> learn`` affordance, black-box)."""

from __future__ import annotations

from agentfront.rubric._types import CheckResult, VerifyContext

BUNDLE = "learnability"
MIN_LEN = 200
REQUIRED_MARKERS = ("purpose", "commands", "exit", "--json", "explain")


def _check_learn_exit_zero(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["learn"], timeout=5.0)
    if out.returncode == 0:
        return CheckResult(
            BUNDLE, "learn_exit_zero", True, "info", f"exit=0 stdout_len={len(out.stdout)}"
        )
    return CheckResult(
        BUNDLE,
        "learn_exit_zero",
        False,
        "error",
        f"exit={out.returncode}",
        remediation="add a `learn` subcommand that prints a self-teaching prompt",
    )


def _check_learn_min_length(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["learn"], timeout=5.0)
    if len(out.stdout) >= MIN_LEN:
        return CheckResult(
            BUNDLE,
            "learn_min_length",
            True,
            "info",
            f"{len(out.stdout)} chars ≥ {MIN_LEN}",
        )
    return CheckResult(
        BUNDLE,
        "learn_min_length",
        False,
        "error",
        f"{len(out.stdout)} chars < {MIN_LEN}",
        remediation=f"expand `learn` output to at least {MIN_LEN} characters",
    )


def _check_learn_markers(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["learn"], timeout=5.0)
    text = out.stdout.lower()
    missing = [m for m in REQUIRED_MARKERS if m.lower() not in text]
    if not missing:
        return CheckResult(BUNDLE, "learn_markers", True, "info", "all required markers present")
    return CheckResult(
        BUNDLE,
        "learn_markers",
        False,
        "error",
        f"missing markers: {', '.join(missing)}",
        remediation=(
            "include the following markers in `learn` output: " + ", ".join(REQUIRED_MARKERS)
        ),
    )


CHECKS = [
    _check_learn_exit_zero,
    _check_learn_min_length,
    _check_learn_markers,
]


def run(ctx: VerifyContext) -> list[CheckResult]:
    return [check(ctx) for check in CHECKS]
