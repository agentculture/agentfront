"""Bundle 5 — global ``explain <path>`` command."""

from __future__ import annotations

from agentfront.rubric._types import CheckResult, VerifyContext

BUNDLE = "explain"

# A bogus path unlikely to collide with anything real.
BOGUS_PATH = "zzz-not-a-real-noun-xyz"


def _check_explain_exists(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["explain"], timeout=5.0)
    if out.returncode == 0 and out.stdout.strip():
        return CheckResult(
            BUNDLE, "explain_exists", True, "info", f"{len(out.stdout)} chars on stdout"
        )
    return CheckResult(
        BUNDLE,
        "explain_exists",
        False,
        "error",
        f"exit={out.returncode} stdout_len={len(out.stdout)}",
        remediation="add a global `explain` command that prints markdown for any path",
    )


def _check_explain_self(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["explain", ctx.tool_name], timeout=5.0)
    if out.returncode == 0 and out.stdout.strip():
        return CheckResult(
            BUNDLE,
            "explain_self",
            True,
            "info",
            f"`explain {ctx.tool_name}` produced {len(out.stdout)} chars",
        )
    return CheckResult(
        BUNDLE,
        "explain_self",
        False,
        "error",
        f"`explain {ctx.tool_name}` exit={out.returncode}",
        remediation=f"add an entry for '{ctx.tool_name}' (and the root) in the explain catalog",
    )


def _check_explain_bogus_fails_with_hint(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["explain", BOGUS_PATH], timeout=5.0)
    if out.returncode == 0:
        return CheckResult(
            BUNDLE,
            "explain_bogus_fails",
            False,
            "error",
            "unknown explain path exited 0",
            remediation="unknown paths should exit non-zero with a remediation hint",
        )
    err_lower = out.stderr.lower()
    if "hint:" in err_lower or "try:" in err_lower:
        return CheckResult(
            BUNDLE,
            "explain_bogus_fails",
            True,
            "info",
            f"exit={out.returncode} with hint",
        )
    return CheckResult(
        BUNDLE,
        "explain_bogus_fails",
        False,
        "error",
        f"exit={out.returncode} but no hint: line on stderr",
        remediation="add a `hint:` line pointing at valid paths when explain misses",
    )


CHECKS = [
    _check_explain_exists,
    _check_explain_self,
    _check_explain_bogus_fails_with_hint,
]


def run(ctx: VerifyContext) -> list[CheckResult]:
    return [check(ctx) for check in CHECKS]
