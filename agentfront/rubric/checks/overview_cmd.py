"""Bundle 6 — ``overview`` verb: descriptive surface snapshot.

Asserts the target CLI implements the third verb of the agent-first triple
(``learn`` / ``explain`` / ``overview``). Bundle 5 covers ``explain``, bundle
2 covers ``learn``; this bundle covers the descriptive survey.

Four checks, all black-box via ``ctx.runner``:

1. ``overview_global_exists`` — ``<tool> overview`` exits 0 with non-empty
   stdout.
2. ``overview_cli_noun_exists`` — ``<tool> cli overview`` exits 0 with
   non-empty stdout (a noun that has action-verbs like ``verify`` must also
   expose ``overview``; in agentfront's current tree only ``cli`` qualifies, but
   the check generalises to any target declaring a ``cli`` noun).
3. ``overview_json_shape`` — ``<tool> overview --json`` parses and carries
   the stable keys ``subject`` and ``sections``.
4. ``overview_graceful_on_bad_path`` — ``<tool> overview /path/that/does/
   not/exist`` exits 0 (descriptive verbs fall back to a zero-target report
   with a warning; they do not hard-fail on missing targets the way
   ``verify`` does).

The **read-only** invariant — that overview never modifies the target — is
a *design* contract (reflected in the command's argparse shape: no
``--out``, no ``--write``, no mutating flags) rather than a runtime probe.
Enforcing it here would require a filesystem snapshot around every run and
significantly widen the rubric runner's scope; we keep this check black-box
and trust the structural bundle.
"""

from __future__ import annotations

import json
import secrets
import tempfile
from pathlib import Path

from agentfront.rubric._types import CheckResult, VerifyContext

BUNDLE = "overview"


def _fresh_missing_path() -> str:
    """Return a random, guaranteed-non-existent path for the graceful-fallback probe.

    The path is never created — the whole point is that the target tool's
    ``overview`` verb must fall back gracefully when handed a missing target.
    The random suffix avoids a predictable ``/tmp/`` location that a malicious
    actor could pre-seed with crafted content (overview is a file-reading verb
    in target mode). Overridable in tests via monkey-patch.
    """
    return str(Path(tempfile.gettempdir()) / f"agentfront-overview-missing-{secrets.token_hex(8)}")


def _check_overview_global_exists(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["overview"], timeout=10.0)
    if out.returncode == 0 and out.stdout.strip():
        return CheckResult(
            BUNDLE,
            "overview_global_exists",
            True,
            "info",
            f"{len(out.stdout)} chars on stdout",
        )
    return CheckResult(
        BUNDLE,
        "overview_global_exists",
        False,
        "error",
        f"exit={out.returncode} stdout_len={len(out.stdout)}",
        remediation="add a top-level `overview` command (rollup across interface surfaces)",
    )


def _check_overview_cli_noun_exists(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["cli", "overview"], timeout=10.0)
    if out.returncode == 0 and out.stdout.strip():
        return CheckResult(
            BUNDLE,
            "overview_cli_noun_exists",
            True,
            "info",
            f"`cli overview` produced {len(out.stdout)} chars",
        )
    return CheckResult(
        BUNDLE,
        "overview_cli_noun_exists",
        False,
        "error",
        f"`cli overview` exit={out.returncode}",
        remediation=(
            "add an `overview` verb under the `cli` noun (every noun with "
            "action-verbs must also expose `overview`)"
        ),
    )


def _check_overview_json_shape(ctx: VerifyContext) -> CheckResult:
    out = ctx.runner.run(["overview", "--json"], timeout=10.0)
    if out.returncode != 0:
        return CheckResult(
            BUNDLE,
            "overview_json_shape",
            False,
            "error",
            f"`overview --json` exit={out.returncode}",
            remediation="`overview --json` must exit 0 on success",
        )
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError as err:
        return CheckResult(
            BUNDLE,
            "overview_json_shape",
            False,
            "error",
            f"`overview --json` stdout is not JSON: {err}",
            remediation="`overview --json` must emit a single JSON object to stdout",
        )
    if not isinstance(payload, dict):
        return CheckResult(
            BUNDLE,
            "overview_json_shape",
            False,
            "error",
            f"`overview --json` is {type(payload).__name__}, not object",
            remediation="top-level JSON must be an object with `subject` and `sections` keys",
        )
    missing = [k for k in ("subject", "sections") if k not in payload]
    if missing:
        return CheckResult(
            BUNDLE,
            "overview_json_shape",
            False,
            "error",
            f"`overview --json` missing keys: {missing}",
            remediation="add stable keys: subject (str), sections (list of objects)",
        )
    return CheckResult(
        BUNDLE,
        "overview_json_shape",
        True,
        "info",
        f"subject={payload.get('subject')!r}, sections={len(payload.get('sections', []))}",
    )


def _check_overview_graceful_on_bad_path(ctx: VerifyContext) -> CheckResult:
    bogus = _fresh_missing_path()
    out = ctx.runner.run(["overview", bogus], timeout=10.0)
    if out.returncode == 0:
        return CheckResult(
            BUNDLE,
            "overview_graceful_on_bad_path",
            True,
            "info",
            "overview fell back gracefully on a missing target path",
        )
    return CheckResult(
        BUNDLE,
        "overview_graceful_on_bad_path",
        False,
        "error",
        f"`overview <bogus-path>` exit={out.returncode}",
        remediation=(
            "overview must fall back to a zero-target report with a warning "
            "when the target path is missing; hard-failing is `verify`'s job, "
            "not a descriptive verb's"
        ),
    )


CHECKS = [
    _check_overview_global_exists,
    _check_overview_cli_noun_exists,
    _check_overview_json_shape,
    _check_overview_graceful_on_bad_path,
]


def run(ctx: VerifyContext) -> list[CheckResult]:
    return [check(ctx) for check in CHECKS]
