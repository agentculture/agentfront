"""``afi doctor`` and ``afi cli doctor`` — diagnosis with actionable remediation.

The doctor verb is the agent-first contract for "tell me what's wrong and
how to fix it." Two entry points:

* ``afi doctor [path]`` — global. With no path, runs the in-process
  self-diagnosis from :mod:`afi.doctor`. With a path, delegates to the
  target-audit flow (same as ``afi cli doctor <path>``).
* ``afi cli doctor <path>`` — replaces ``afi cli verify``: runs the rubric
  against the target. Adds ``--fix`` / ``--dry-run`` for auto-remediation
  of checks that declare ``auto_fixable=true``. ``afi cli verify`` stays
  as a deprecated alias that forwards here for one minor cycle.

Output contract:

* JSON shape — ``{tool, subject, healthy: bool, checks: [...], summary: {...}}``.
  Required by rubric bundle 7 (``healthy``, ``checks`` keys; each check
  carries ``id``, ``passed``, ``severity``, ``message``, plus optional
  ``remediation`` / ``auto_fixable`` / ``fix_id`` / ``bundle``).
* Text — bundle-grouped lines with PASS / FAIL marks, then a one-line
  health verdict to stderr.

Exit code: 0 if no ``error``-severity check failed; 1 otherwise. ``--strict``
promotes ``warn`` failures to non-zero.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from afi.cli._errors import EXIT_USER_ERROR, AfiError
from afi.cli._output import emit_diagnostic, emit_result
from afi.doctor import is_healthy, run_self_diagnosis
from afi.doctor.fixes import apply_fix
from afi.rubric import run_rubric
from afi.rubric._runner import SubprocessRunner
from afi.rubric._types import CheckResult, VerifyContext

_JSON_HELP = "Emit structured JSON."


def _check_to_dict(r: CheckResult) -> dict[str, object]:
    """Convert a CheckResult to the doctor wire format.

    ``id`` and ``message`` are the agent-friendly key names (the rubric's
    own ``CheckResult.to_dict`` uses ``check`` and ``evidence``). Both
    spellings are preserved-by-mapping in the doctor output so consumers
    don't have to learn rubric-internal vocabulary.
    """
    return {
        "id": r.check,
        "bundle": r.bundle,
        "passed": r.passed,
        "severity": r.severity,
        "message": r.evidence,
        "remediation": r.remediation,
        "auto_fixable": r.auto_fixable,
        "fix_id": r.fix_id,
    }


def _summarize(results: Iterable[CheckResult]) -> dict[str, int]:
    results = list(results)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    errors = sum(1 for r in results if not r.passed and r.severity == "error")
    warnings = sum(1 for r in results if not r.passed and r.severity == "warn")
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "warnings": warnings,
    }


def _emit_payload(
    *,
    subject: str,
    tool: str,
    results: list[CheckResult],
    json_mode: bool,
) -> None:
    summary = _summarize(results)
    healthy = is_healthy(results)
    if json_mode:
        emit_result(
            {
                "tool": tool,
                "subject": subject,
                "healthy": healthy,
                "checks": [_check_to_dict(r) for r in results],
                "summary": summary,
            },
            json_mode=True,
        )
        return

    by_bundle: dict[str, list[CheckResult]] = {}
    for r in results:
        by_bundle.setdefault(r.bundle, []).append(r)
    for bundle, items in by_bundle.items():
        emit_result(f"[{bundle}]", json_mode=False)
        for r in items:
            mark = "PASS" if r.passed else f"FAIL ({r.severity})"
            emit_result(f"  {mark:<12} {r.check}: {r.evidence}", json_mode=False)
            if not r.passed and r.remediation:
                emit_result(f"               hint: {r.remediation}", json_mode=False)
        emit_result("", json_mode=False)
    verdict = "healthy" if healthy else "unhealthy"
    emit_diagnostic(
        f"{verdict}: {summary['passed']}/{summary['total']} passed, "
        f"{summary['errors']} errors, {summary['warnings']} warnings"
    )


def _exit_code(results: list[CheckResult], *, strict: bool) -> int:
    summary = _summarize(results)
    if strict:
        return 0 if summary["failed"] == 0 else 1
    return 0 if summary["errors"] == 0 else 1


def _resolve_tool_name(target_path: Path) -> str:
    """Read the first ``[project.scripts]`` entry from ``target_path/pyproject.toml``.

    Mirrors the helper that used to live in ``cli.py`` for ``cmd_verify``;
    kept here so doctor stays the source of truth for target audits.
    """
    import tomllib

    pp = target_path / "pyproject.toml"
    if not pp.is_file():
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"no pyproject.toml at {pp}",
            remediation="run doctor from the root of a Python project with pyproject.toml",
        )
    try:
        data = tomllib.loads(pp.read_text())
    except tomllib.TOMLDecodeError as err:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"invalid TOML in {pp}: {err}",
            remediation="fix the TOML syntax error in pyproject.toml",
        ) from err
    project = data.get("project") if isinstance(data, dict) else None
    if project is not None and not isinstance(project, dict):
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"invalid {pp}: [project] must be a TOML table",
            remediation=(
                "rewrite the [project] section as a table per PEP 621 "
                "(https://peps.python.org/pep-0621/)"
            ),
        )
    scripts = project.get("scripts") if isinstance(project, dict) else None
    if scripts is not None and not isinstance(scripts, dict):
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"invalid {pp}: [project.scripts] must be a TOML table",
            remediation='rewrite [project.scripts] as a table of name = "module:func" entries',
        )
    if not scripts:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"no [project.scripts] in {pp}",
            remediation=(
                "add a [project.scripts] entry to pyproject.toml so the tool has an entry point"
            ),
        )
    return next(iter(scripts.keys()))


def _run_target_audit(
    target_path: Path,
    *,
    fix: bool,
    dry_run: bool,
) -> tuple[str, list[CheckResult]]:
    """Run the rubric against ``target_path``; optionally apply auto-fixes.

    Returns ``(tool_name, results)``. ``--fix`` re-runs the rubric after
    applying handlers so the returned results reflect post-fix state;
    ``--dry-run`` only prints a fix preview to stderr and returns the
    pre-fix results unchanged.
    """
    tool_name = _resolve_tool_name(target_path)
    runner = SubprocessRunner(cwd=target_path, tool_name=tool_name)
    ctx = VerifyContext(target_path=target_path, tool_name=tool_name, runner=runner)
    results = run_rubric(ctx)

    if not (fix or dry_run):
        return tool_name, results

    fixable = [r for r in results if (not r.passed) and r.auto_fixable and r.fix_id]
    if dry_run:
        if not fixable:
            emit_diagnostic("--dry-run: no auto-fixable failures.")
        else:
            emit_diagnostic(f"--dry-run: would attempt {len(fixable)} fix(es):")
            for r in fixable:
                emit_diagnostic(f"  - [{r.bundle}] {r.check} → fix_id={r.fix_id}")
        return tool_name, results

    # Apply branch — --fix is set, --dry-run is not (mutually exclusive).
    if not fixable:
        emit_diagnostic("--fix: no auto-fixable failures.")
        return tool_name, results
    emit_diagnostic(f"--fix: applying {len(fixable)} fix(es)...")
    for r in fixable:
        outcome = apply_fix(r.fix_id, ctx)
        prefix = "applied" if outcome.applied else "skipped"
        emit_diagnostic(f"  {prefix}: [{r.bundle}] {r.check} — {outcome.message}")
    # Re-run so callers see the post-fix verdict.
    results = run_rubric(ctx)
    return tool_name, results


def cmd_doctor(args: argparse.Namespace) -> int:
    """Handler for ``afi doctor [path]`` — global verb.

    No path → self-diagnosis (in-process, fast, read-only). With path →
    rubric audit of the target (delegates to the same engine that powers
    ``afi cli doctor``).
    """
    json_mode = bool(getattr(args, "json", False))
    fix = bool(getattr(args, "fix", False))
    dry_run = bool(getattr(args, "dry_run", False))
    strict = bool(getattr(args, "strict", False))

    raw = getattr(args, "path", None)
    if raw is None:
        # self-doctor
        if fix or dry_run:
            emit_diagnostic(
                "--fix / --dry-run are no-ops on self-doctor (read-only); "
                "use them with `afi cli doctor <path>`."
            )
        diagnosis = run_self_diagnosis()
        _emit_payload(
            subject=diagnosis.subject,
            tool="afi",
            results=diagnosis.checks,
            json_mode=json_mode,
        )
        return _exit_code(diagnosis.checks, strict=strict)

    # Target audit (alias for `afi cli doctor <path>`).
    target_path = Path(raw).resolve()
    tool_name, results = _run_target_audit(target_path, fix=fix, dry_run=dry_run)
    _emit_payload(
        subject=str(target_path),
        tool=tool_name,
        results=results,
        json_mode=json_mode,
    )
    return _exit_code(results, strict=strict)


def cmd_cli_doctor(args: argparse.Namespace) -> int:
    """Handler for ``afi cli doctor <path>`` — target audit with optional --fix."""
    target_path = Path(args.path).resolve()
    json_mode = bool(getattr(args, "json", False))
    fix = bool(getattr(args, "fix", False))
    dry_run = bool(getattr(args, "dry_run", False))
    strict = bool(getattr(args, "strict", False))

    tool_name, results = _run_target_audit(target_path, fix=fix, dry_run=dry_run)
    _emit_payload(
        subject=str(target_path),
        tool=tool_name,
        results=results,
        json_mode=json_mode,
    )
    return _exit_code(results, strict=strict)


def cmd_cli_verify_deprecated(args: argparse.Namespace) -> int:
    """Handler for the deprecated ``afi cli verify`` alias.

    Emits a deprecation diagnostic to stderr, then forwards to
    :func:`cmd_cli_doctor`. Removed in v0.6.0.
    """
    emit_diagnostic(
        "deprecated: 'afi cli verify' is an alias for 'afi cli doctor'; "
        "will be removed in v0.6.0."
    )
    return cmd_cli_doctor(args)


def register(sub: argparse._SubParsersAction) -> None:
    """Register the global ``afi doctor`` verb. Called from afi.cli.__init__."""
    p = sub.add_parser(
        "doctor",
        help=(
            "Diagnose afi (no path) or audit a target CLI (with path) and "
            "report inconsistencies with actionable remediation."
        ),
    )
    p.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Target project path. Omit to self-diagnose afi's own install.",
    )
    p.add_argument("--json", action="store_true", help=_JSON_HELP)
    # --fix and --dry-run are alternatives, not orthogonal: --dry-run previews
    # what --fix would do, so passing both is meaningless. Argparse rejects it
    # with a clear error rather than silently picking one.
    fix_group = p.add_mutually_exclusive_group()
    fix_group.add_argument(
        "--fix",
        action="store_true",
        help="Apply auto-fixable remediations (target audits only).",
    )
    fix_group.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Preview which fixes would be applied without mutating.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures (non-zero exit on any not-passed check).",
    )
    p.set_defaults(func=cmd_doctor)
