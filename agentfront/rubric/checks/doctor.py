"""Bundle 7 — ``doctor`` verb: diagnosability with actionable remediation.

Asserts the target CLI implements the fourth pillar of the agent-first
contract: a ``doctor`` verb that surfaces internal inconsistencies and
explains how to fix them. Bundles 2/5/6 cover the introspection triple
(``learn`` / ``explain`` / ``overview``); this bundle covers diagnosis.

Four checks, all black-box via ``ctx.runner``:

1. ``doctor_global_exists`` — ``<tool> doctor`` produces a non-empty stdout
   report. Exit code is *not* asserted: a healthy doctor exits 0, an
   unhealthy doctor exits 1 — both satisfy the contract that the verb
   exists and produces a report.
2. ``doctor_json_shape`` — ``<tool> doctor --json`` parses to a dict with
   stable keys ``healthy`` (bool) and ``checks`` (list).
3. ``doctor_check_shape`` — every entry in the ``checks`` list carries
   ``id``, ``passed``, ``severity``, ``message`` keys.
4. ``doctor_remediation_when_unhealthy`` — when ``healthy`` is false, every
   failed check supplies a non-empty ``remediation`` string. This is the
   contract that distinguishes ``doctor`` from a plain audit: failures must
   always be actionable.

The ``--fix`` flag is part of the doctor design but is *not* asserted by
this bundle — auto-fixes have side effects, so a black-box probe of
``--fix`` would mutate the target. Targets that wire ``auto_fixable=true``
into individual checks declare the contract; black-box mutation is not
the rubric runner's job.
"""

from __future__ import annotations

import json

from agentfront.rubric._types import CheckResult, VerifyContext

BUNDLE = "doctor"

_REQUIRED_TOP_KEYS = ("healthy", "checks")
_REQUIRED_CHECK_KEYS = ("id", "passed", "severity", "message")

# Cascading remediation: when `doctor --json` cannot be parsed at all, every
# downstream check has the same root cause and the same fix — go look at
# doctor_json_shape's evidence and repair that first. Centralised so the
# message stays in lockstep across check modules.
_PARSE_FAILURE_REMEDIATION = "fix `doctor_json_shape` first"


def _check_doctor_global_exists(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["doctor"], timeout=10.0)
    if out.stdout.strip():
        return CheckResult(
            BUNDLE,
            "doctor_global_exists",
            True,
            "info",
            f"exit={out.returncode} stdout_len={len(out.stdout)}",
        )
    return CheckResult(
        BUNDLE,
        "doctor_global_exists",
        False,
        "error",
        f"`doctor` produced no stdout (exit={out.returncode})",
        remediation=(
            "add a top-level `doctor` verb that surfaces internal inconsistencies "
            "with actionable remediation; this is the agent-first diagnosability pillar"
        ),
    )


def _check_doctor_json_shape(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["doctor", "--json"], timeout=10.0)
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError as err:
        return CheckResult(
            BUNDLE,
            "doctor_json_shape",
            False,
            "error",
            f"`doctor --json` stdout is not JSON: {err}",
            remediation="`doctor --json` must emit a single JSON object to stdout",
        )
    if not isinstance(payload, dict):
        return CheckResult(
            BUNDLE,
            "doctor_json_shape",
            False,
            "error",
            f"`doctor --json` is {type(payload).__name__}, not object",
            remediation="top-level JSON must be an object with `healthy` and `checks` keys",
        )
    missing = [k for k in _REQUIRED_TOP_KEYS if k not in payload]
    if missing:
        return CheckResult(
            BUNDLE,
            "doctor_json_shape",
            False,
            "error",
            f"`doctor --json` missing keys: {missing}",
            remediation="add stable keys: healthy (bool), checks (list of objects)",
        )
    if not isinstance(payload["healthy"], bool):
        return CheckResult(
            BUNDLE,
            "doctor_json_shape",
            False,
            "error",
            f"`healthy` is {type(payload['healthy']).__name__}, not bool",
            remediation="`healthy` must be a JSON boolean",
        )
    if not isinstance(payload["checks"], list):
        return CheckResult(
            BUNDLE,
            "doctor_json_shape",
            False,
            "error",
            f"`checks` is {type(payload['checks']).__name__}, not array",
            remediation="`checks` must be a JSON array of check-result objects",
        )
    return CheckResult(
        BUNDLE,
        "doctor_json_shape",
        True,
        "info",
        f"healthy={payload['healthy']}, checks={len(payload['checks'])}",
    )


def _check_doctor_check_shape(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["doctor", "--json"], timeout=10.0)
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError:
        return CheckResult(
            BUNDLE,
            "doctor_check_shape",
            False,
            "error",
            "`doctor --json` did not parse — see doctor_json_shape",
            remediation=_PARSE_FAILURE_REMEDIATION,
        )
    checks = payload.get("checks") if isinstance(payload, dict) else None
    if not isinstance(checks, list):
        return CheckResult(
            BUNDLE,
            "doctor_check_shape",
            False,
            "error",
            "`checks` is not an array — see doctor_json_shape",
            remediation=_PARSE_FAILURE_REMEDIATION,
        )
    if not checks:
        # An empty list is shape-valid; treat as info-pass.
        return CheckResult(
            BUNDLE,
            "doctor_check_shape",
            True,
            "info",
            "checks list is empty (no checks defined yet)",
        )
    bad: list[str] = []
    for i, entry in enumerate(checks):
        if not isinstance(entry, dict):
            bad.append(f"checks[{i}] is {type(entry).__name__}, not object")
            continue
        missing = [k for k in _REQUIRED_CHECK_KEYS if k not in entry]
        if missing:
            label = entry.get("id", f"checks[{i}]")
            bad.append(f"{label} missing {missing}")
    if bad:
        return CheckResult(
            BUNDLE,
            "doctor_check_shape",
            False,
            "error",
            "; ".join(bad[:3]) + ("; …" if len(bad) > 3 else ""),
            remediation=(
                "every entry in `checks` must carry id (str), passed (bool), "
                "severity (str), and message (str)"
            ),
        )
    return CheckResult(
        BUNDLE,
        "doctor_check_shape",
        True,
        "info",
        f"every check ({len(checks)}) carries the required keys",
    )


def _check_doctor_remediation_when_unhealthy(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["doctor", "--json"], timeout=10.0)
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError:
        return CheckResult(
            BUNDLE,
            "doctor_remediation_when_unhealthy",
            False,
            "error",
            "`doctor --json` did not parse — see doctor_json_shape",
            remediation=_PARSE_FAILURE_REMEDIATION,
        )
    if not isinstance(payload, dict):
        return CheckResult(
            BUNDLE,
            "doctor_remediation_when_unhealthy",
            False,
            "error",
            "top-level is not an object — see doctor_json_shape",
            remediation=_PARSE_FAILURE_REMEDIATION,
        )
    if payload.get("healthy") is True:
        return CheckResult(
            BUNDLE,
            "doctor_remediation_when_unhealthy",
            True,
            "info",
            "doctor reports healthy; remediation contract trivially satisfied",
        )
    failed = [
        c for c in payload.get("checks", []) if isinstance(c, dict) and c.get("passed") is False
    ]
    if not failed:
        # healthy=false but no failed checks listed — odd, but not this bundle's job.
        return CheckResult(
            BUNDLE,
            "doctor_remediation_when_unhealthy",
            True,
            "info",
            "no failed checks listed; nothing to remediate",
        )
    missing = [
        str(c.get("id", "<no-id>"))
        for c in failed
        if not (isinstance(c.get("remediation"), str) and c["remediation"].strip())
    ]
    if missing:
        return CheckResult(
            BUNDLE,
            "doctor_remediation_when_unhealthy",
            False,
            "error",
            f"failed checks without remediation: {', '.join(missing[:3])}"
            + ("…" if len(missing) > 3 else ""),
            remediation=(
                "every failed check must carry a non-empty `remediation` string — "
                "doctor's promise is that failures are always actionable"
            ),
        )
    return CheckResult(
        BUNDLE,
        "doctor_remediation_when_unhealthy",
        True,
        "info",
        f"all {len(failed)} failed checks supply a remediation",
    )


CHECKS = [
    _check_doctor_global_exists,
    _check_doctor_json_shape,
    _check_doctor_check_shape,
    _check_doctor_remediation_when_unhealthy,
]


def run(ctx: VerifyContext) -> list[CheckResult]:
    return [check(ctx) for check in CHECKS]
