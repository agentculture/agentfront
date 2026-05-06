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
import json as _json
from importlib import metadata as _metadata
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from afi.cli._errors import EXIT_USER_ERROR, AfiError
from afi.cli._output import emit_diagnostic, emit_result
from afi.doctor import is_healthy, run_self_diagnosis
from afi.doctor.fixes import apply_fix
from afi.rubric import run_rubric
from afi.rubric._runner import SubprocessRunner
from afi.rubric._types import CheckResult, VerifyContext

_JSON_HELP = "Emit structured JSON."
_PACKAGE_HELP = (
    "Audit an editable-installed distribution by name (looks up its source "
    "root via PEP 610 direct_url.json). Mutually exclusive with the path "
    "positional."
)


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


def _group_by_bundle(results: list[CheckResult]) -> dict[str, list[CheckResult]]:
    by_bundle: dict[str, list[CheckResult]] = {}
    for r in results:
        by_bundle.setdefault(r.bundle, []).append(r)
    return by_bundle


def _format_check_lines(r: CheckResult) -> list[str]:
    mark = "PASS" if r.passed else f"FAIL ({r.severity})"
    lines = [f"  {mark:<12} {r.check}: {r.evidence}"]
    if not r.passed and r.remediation:
        lines.append(f"               hint: {r.remediation}")
    return lines


def _emit_text_body(results: list[CheckResult]) -> None:
    for bundle, items in _group_by_bundle(results).items():
        emit_result(f"[{bundle}]", json_mode=False)
        for r in items:
            for line in _format_check_lines(r):
                emit_result(line, json_mode=False)
        emit_result("", json_mode=False)


def _self_headline(summary: dict[str, int], healthy: bool) -> str:
    # Self-mode headline scopes the verdict to "structural self-check" so an
    # agent doesn't read a green light here as a green light on the CLI it's
    # actually working with. See agentculture/afi-cli#13.
    suffix = "Run 'afi doctor <path>' to audit a target CLI."
    if healthy:
        return (
            f"afi doctor: structural self-check passed "
            f"({summary['passed']}/{summary['total']}). {suffix}"
        )
    return (
        f"afi doctor: structural self-check failed "
        f"({summary['passed']}/{summary['total']} passed, "
        f"{summary['errors']} errors, {summary['warnings']} warnings). "
        f"{suffix}"
    )


def _target_headline(summary: dict[str, int], healthy: bool) -> str:
    verdict = "healthy" if healthy else "unhealthy"
    return (
        f"{verdict}: {summary['passed']}/{summary['total']} passed, "
        f"{summary['errors']} errors, {summary['warnings']} warnings"
    )


def _emit_payload(
    *,
    subject: str,
    tool: str,
    results: list[CheckResult],
    json_mode: bool,
    is_self: bool = False,
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

    _emit_text_body(results)
    headline = _self_headline if is_self else _target_headline
    emit_diagnostic(headline(summary, healthy))


def _exit_code(results: list[CheckResult], *, strict: bool) -> int:
    summary = _summarize(results)
    if strict:
        return 0 if summary["failed"] == 0 else 1
    return 0 if summary["errors"] == 0 else 1


def _resolve_tool_name(target_path: Path, *, command: str = "afi doctor") -> str:
    """Read the first ``[project.scripts]`` entry from ``target_path/pyproject.toml``.

    Mirrors the helper that used to live in ``cli.py`` for ``cmd_verify``;
    kept here so doctor stays the source of truth for target audits.

    ``command`` is the verb the user invoked (``afi doctor`` or
    ``afi cli doctor``); it is woven into the not-a-project-root remediation
    so the diagnostic names the runnable command the user actually typed.
    """
    import tomllib

    pp = target_path / "pyproject.toml"
    if not pp.is_file():
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"'{target_path}' is not a project root (no pyproject.toml at {pp})",
            remediation=(
                f"pass a path to a Python project root (e.g. `{command} .` from "
                f"inside the repo, or `{command} /path/to/<project>`); to audit "
                f"an editable-installed distribution by name, use "
                f"`{command} --package <name>`"
            ),
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


def _resolve_package_source_root(name: str, *, command: str = "afi doctor") -> Path:
    """Return the editable-install source root for distribution ``name``.

    Reads PEP 610 ``direct_url.json`` from the installed distribution and
    returns the recorded source path when it points at a real *editable*
    project root (``file://`` URL with ``dir_info.editable == true`` and a
    ``pyproject.toml`` on disk). Raises :class:`AfiError` on every other
    branch with a remediation that names the next step (install editable,
    or pass a path).

    ``command`` is the verb the user invoked; threaded into every
    remediation so error output names the runnable command they typed.
    """
    try:
        dist = _metadata.distribution(name)
    except _metadata.PackageNotFoundError as err:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"no installed distribution named '{name}'",
            remediation=(
                f"install '{name}' editable in this environment (e.g. "
                f"`uv pip install -e /path/to/{name}`), or pass a path: "
                f"`{command} /path/to/{name}`"
            ),
        ) from err

    raw = dist.read_text("direct_url.json")
    if not raw:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"'{name}' is installed but not as an editable file:// install",
            remediation=(
                f"reinstall editable from a source checkout (e.g. "
                f"`uv pip install -e /path/to/{name}`), or pass a path: "
                f"`{command} /path/to/{name}`"
            ),
        )
    try:
        info = _json.loads(raw)
    except _json.JSONDecodeError as err:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"'{name}': direct_url.json is not valid JSON ({err})",
            remediation=f"reinstall '{name}' to refresh its install metadata",
        ) from err

    url = info.get("url", "") if isinstance(info, dict) else ""
    parsed = urlparse(url)
    if parsed.scheme != "file":
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=(
                f"'{name}' was installed from a non-file source ({url!r}); "
                f"afi doctor needs a source checkout with pyproject.toml"
            ),
            remediation=(
                f"reinstall editable from a local checkout (e.g. "
                f"`uv pip install -e /path/to/{name}`), or pass a path: "
                f"`{command} /path/to/{name}`"
            ),
        )

    # Enforce the contract the help text already promises: --package only
    # accepts editable installs. A non-editable file:// install (e.g.
    # `pip install /path/to/repo` without -e) would otherwise be silently
    # accepted, and a later `--fix` could mutate a source tree the install
    # copy isn't tracking. Surface this *before* the pyproject probe so the
    # diagnostic names the real cause instead of a downstream symptom.
    dir_info = info.get("dir_info") if isinstance(info, dict) else None
    if not (isinstance(dir_info, dict) and dir_info.get("editable") is True):
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=(
                f"'{name}' is installed from a local source but not editable; "
                f"afi doctor needs an editable install so source mutations are visible"
            ),
            remediation=(
                f"reinstall with -e (e.g. `uv pip install -e /path/to/{name}`), "
                f"or pass a path: `{command} /path/to/{name}`"
            ),
        )

    src = Path(unquote(parsed.path)).resolve()
    if not (src / "pyproject.toml").is_file():
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=(f"'{name}' resolves to '{src}' but no pyproject.toml is there"),
            remediation=(
                f"reinstall editable from a real project root, or pass a path "
                f"directly: `{command} /path/to/{name}`"
            ),
        )
    return src


def _run_target_audit(
    target_path: Path,
    *,
    fix: bool,
    dry_run: bool,
    command: str = "afi doctor",
) -> tuple[str, list[CheckResult]]:
    """Run the rubric against ``target_path``; optionally apply auto-fixes.

    Returns ``(tool_name, results)``. ``--fix`` re-runs the rubric after
    applying handlers so the returned results reflect post-fix state;
    ``--dry-run`` only prints a fix preview to stderr and returns the
    pre-fix results unchanged. ``command`` is forwarded to
    :func:`_resolve_tool_name` so its remediations name the verb the user
    typed.
    """
    tool_name = _resolve_tool_name(target_path, command=command)
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


def _resolve_target_or_raise(
    *,
    raw_path: str | None,
    package: str | None,
    command: str = "afi doctor",
) -> Path:
    """Pick the audit target from the (path, package) pair.

    Caller policies:

    * Both set → user error (mutually exclusive).
    * ``package`` set → resolve via :func:`_resolve_package_source_root`.
    * ``raw_path`` set → resolve as a filesystem path.

    The "neither set" case is handled by callers (it means different things
    for ``afi doctor`` vs. ``afi cli doctor``). ``command`` is the verb the
    user invoked; threaded into mutex/no-target remediations so they name
    the runnable command they typed.
    """
    if package is not None and raw_path is not None:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message="--package and a path argument are mutually exclusive",
            remediation=(
                f"pass exactly one: either a path "
                f"(`{command} /path/to/project`) or a package name "
                f"(`{command} --package <name>`)"
            ),
        )
    if package is not None:
        return _resolve_package_source_root(package, command=command)
    if raw_path is None:
        # Defensive: callers gate the "neither set" branch themselves.
        # If we ever land here it means a new caller forgot to do so.
        raise AfiError(
            code=EXIT_USER_ERROR,
            message="no audit target supplied",
            remediation=f"pass a path or `{command} --package <name>`",
        )
    return Path(raw_path).resolve()


def cmd_doctor(args: argparse.Namespace) -> int:
    """Handler for ``afi doctor [path]`` — global verb.

    No path and no ``--package`` → self-diagnosis (in-process, fast,
    read-only). With either, runs the rubric audit (same engine as
    ``afi cli doctor``).
    """
    json_mode = bool(getattr(args, "json", False))
    fix = bool(getattr(args, "fix", False))
    dry_run = bool(getattr(args, "dry_run", False))
    strict = bool(getattr(args, "strict", False))

    raw = getattr(args, "path", None)
    package = getattr(args, "package", None)
    if raw is None and package is None:
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
            is_self=True,
        )
        return _exit_code(diagnosis.checks, strict=strict)

    # Target audit (alias for `afi cli doctor <path>` / `--package <name>`).
    target_path = _resolve_target_or_raise(raw_path=raw, package=package, command="afi doctor")
    tool_name, results = _run_target_audit(
        target_path, fix=fix, dry_run=dry_run, command="afi doctor"
    )
    _emit_payload(
        subject=str(target_path),
        tool=tool_name,
        results=results,
        json_mode=json_mode,
    )
    return _exit_code(results, strict=strict)


def cmd_cli_doctor(args: argparse.Namespace) -> int:
    """Handler for ``afi cli doctor [path] | --package <name>``.

    Path positional defaults to ``.``; ``--package`` overrides it. Passing
    a non-default path together with ``--package`` is rejected.
    """
    json_mode = bool(getattr(args, "json", False))
    fix = bool(getattr(args, "fix", False))
    dry_run = bool(getattr(args, "dry_run", False))
    strict = bool(getattr(args, "strict", False))

    raw = getattr(args, "path", None)
    package = getattr(args, "package", None)
    # `afi cli doctor` (no args) audits cwd. We can't tell "user typed `.`"
    # from "argparse default" via the resolved value, so we keep the
    # default as None and apply the cwd fallback here when neither input
    # was given.
    if raw is None and package is None:
        target_path = Path(".").resolve()
    else:
        target_path = _resolve_target_or_raise(
            raw_path=raw, package=package, command="afi cli doctor"
        )

    tool_name, results = _run_target_audit(
        target_path, fix=fix, dry_run=dry_run, command="afi cli doctor"
    )
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
        help=(
            "Target project root (with pyproject.toml). Omit (and skip "
            "--package) to self-diagnose afi's own install."
        ),
    )
    p.add_argument(
        "--package",
        default=None,
        metavar="NAME",
        help=_PACKAGE_HELP,
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
