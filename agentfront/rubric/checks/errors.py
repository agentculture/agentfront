"""Bundle 4 — error propagation (exit codes, remediation hints, no traceback)."""

from __future__ import annotations

from agentfront.rubric._types import CheckResult, VerifyContext

BUNDLE = "errors"

# A bogus verb unlikely to collide with anything real.
BOGUS = "zzz-does-not-exist-verb"


def _check_bogus_verb_exits_nonzero(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run([BOGUS], timeout=5.0)
    if out.returncode != 0:
        return CheckResult(
            BUNDLE,
            "bogus_verb_exits_nonzero",
            True,
            "info",
            f"exit={out.returncode}",
        )
    return CheckResult(
        BUNDLE,
        "bogus_verb_exits_nonzero",
        False,
        "error",
        "unknown verb exited 0",
        remediation="argparse (or equivalent) should exit non-zero on unknown verbs",
    )


def _check_error_has_hint(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run([BOGUS], timeout=5.0)
    err_lower = out.stderr.lower()
    if "hint:" in err_lower or "try:" in err_lower:
        return CheckResult(BUNDLE, "error_has_hint", True, "info", "found hint: or try: line")
    return CheckResult(
        BUNDLE,
        "error_has_hint",
        False,
        "error",
        "no 'hint:' or 'try:' line in stderr",
        remediation="include a 'hint: ...' line in error output with a concrete next step",
    )


def _check_no_traceback(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run([BOGUS], timeout=5.0)
    if "Traceback" not in out.stderr:
        return CheckResult(BUNDLE, "no_traceback", True, "info", "stderr has no Traceback")
    return CheckResult(
        BUNDLE,
        "no_traceback",
        False,
        "error",
        "Python traceback leaked to stderr",
        remediation="catch exceptions at the CLI boundary and emit structured errors",
    )


def _check_exit_codes_documented(ctx: VerifyContext) -> CheckResult:
    """Require learn output to document the full exit-code policy.

    We require the word "exit" AND all three codes 0, 1, 2 to appear in
    stdout. Matching any single digit was too loose — a tool could pass just
    by having "hello 1 world" anywhere in `learn` output.
    """
    out = ctx.runner.run(["learn"], timeout=5.0)
    text = out.stdout
    text_lower = text.lower()
    required_codes = ("0", "1", "2")
    missing_codes = [c for c in required_codes if c not in text]
    has_exit_word = "exit" in text_lower
    if has_exit_word and not missing_codes:
        return CheckResult(
            BUNDLE,
            "exit_codes_documented",
            True,
            "info",
            "learn output mentions 'exit' and codes 0/1/2",
        )
    details = []
    if not has_exit_word:
        details.append("word 'exit' absent from learn output")
    if missing_codes:
        details.append(f"codes missing: {', '.join(missing_codes)}")
    return CheckResult(
        BUNDLE,
        "exit_codes_documented",
        False,
        "warn",
        "; ".join(details) or "exit-code policy not documented",
        remediation="document the exit-code policy (0 success / 1 user / 2 env) in `learn` output",
    )


CHECKS = [
    _check_bogus_verb_exits_nonzero,
    _check_error_has_hint,
    _check_no_traceback,
    _check_exit_codes_documented,
]


def run(ctx: VerifyContext) -> list[CheckResult]:
    return [check(ctx) for check in CHECKS]
