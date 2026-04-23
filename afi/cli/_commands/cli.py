"""The ``cli`` noun group — verbs ``cite``, ``verify``, and ``overview``.

``afi cli cite``     — drop the agent-first CLI reference tree into the target
                       project under ``.afi/reference/<lang>-cli/``.
``afi cli verify``   — run the six-bundle rubric against a target CLI.
``afi cli overview`` — read-only descriptive snapshot of a target CLI.
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from afi.cite import SUPPORTED_LANGS, emit_reference
from afi.cli._errors import EXIT_USER_ERROR, AfiError
from afi.cli._output import emit_diagnostic, emit_result
from afi.overview import build as build_overview
from afi.overview import to_json_dict, to_markdown
from afi.rubric import run_rubric
from afi.rubric._runner import SubprocessRunner
from afi.rubric._types import CheckResult, VerifyContext


def _resolve_tool_name(target_path: Path) -> str:
    pp = target_path / "pyproject.toml"
    if not pp.is_file():
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"no pyproject.toml at {pp}",
            remediation="run verify from the root of a Python project with pyproject.toml",
        )
    try:
        data = tomllib.loads(pp.read_text())
    except tomllib.TOMLDecodeError as err:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"invalid TOML in {pp}: {err}",
            remediation="fix the TOML syntax error in pyproject.toml",
        ) from err
    scripts = data.get("project", {}).get("scripts", {})
    if not scripts:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"no [project.scripts] in {pp}",
            remediation=(
                "add a [project.scripts] entry to pyproject.toml so the tool has an entry point"
            ),
        )
    return next(iter(scripts.keys()))


def cmd_cite(args: argparse.Namespace) -> None:
    """Handler for ``afi cli cite``.

    Returns ``None`` on success (treated as ``EXIT_SUCCESS`` by
    :func:`afi.cli._dispatch`); every failure path raises
    :class:`AfiError`. This keeps the handler protocol simple: "raise on
    failure, return an int only when the success exit code varies" — the
    way :func:`cmd_verify` does, and the way future verbs that need
    nuanced exit codes (e.g. rubric fail) will.
    """
    target_path = Path(args.path).resolve()
    lang = args.lang
    out = Path(args.out).resolve() if args.out else None
    report = emit_reference(target_path, lang=lang, out=out)
    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        emit_result(report.to_dict(), json_mode=True)
        return

    # The cite report IS the command's result — must go to stdout to honour
    # the stdout/stderr split (results → stdout). `emit_diagnostic` is
    # reserved for optional progress/side info and is unused in this path.
    lines = [
        f"Wrote {report.written_count} files to {report.out}",
        (
            "Added `.afi/` to .gitignore"
            if report.gitignore_updated
            else ".gitignore already ignores `.afi/`"
        ),
        "",
        "Next steps:",
    ]
    for i, step in enumerate(report.describe_next_steps(), start=1):
        lines.append(f"  {i}. {step}")
    lines.extend(
        [
            "",
            "For details on any step:  afi explain cli cite",
            "For the rubric itself:    afi explain cli verify",
        ]
    )
    emit_result("\n".join(lines), json_mode=False)


def cmd_verify(args: argparse.Namespace) -> int:
    target_path = Path(args.path).resolve()
    tool_name = _resolve_tool_name(target_path)
    runner = SubprocessRunner(cwd=target_path, tool_name=tool_name)
    ctx = VerifyContext(target_path=target_path, tool_name=tool_name, runner=runner)

    results = run_rubric(ctx)
    summary = _summarize(results)
    json_mode = bool(getattr(args, "json", False))
    strict = bool(getattr(args, "strict", False))

    if json_mode:
        emit_result(
            {
                "tool": tool_name,
                "path": str(target_path),
                "results": [r.to_dict() for r in results],
                "summary": summary,
            },
            json_mode=True,
        )
    else:
        _render_text(results, summary)

    if strict:
        return 0 if summary["failed"] == 0 else 1
    return 0 if summary["errors"] == 0 else 1


def cmd_cli_overview(args: argparse.Namespace) -> int:
    """Handler for ``afi cli overview [path]``.

    Read-only descriptive snapshot. If ``path`` is missing or points at a
    project without a detectable CLI surface, emits the overview of afi's
    own scaffolded template (the "zero-target default").
    """
    raw = getattr(args, "path", None)
    path: Path | None = Path(raw).resolve() if raw else None
    report = build_overview("cli", path)
    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        emit_result(to_json_dict(report), json_mode=True)
    else:
        emit_result(to_markdown(report), json_mode=False)
    return 0


def _summarize(results: list[CheckResult]) -> dict[str, object]:
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    errors = sum(1 for r in results if not r.passed and r.severity == "error")
    warnings = sum(1 for r in results if not r.passed and r.severity == "warn")
    bundles: dict[str, dict[str, int]] = {}
    for r in results:
        b = bundles.setdefault(r.bundle, {"passed": 0, "failed": 0})
        b["passed" if r.passed else "failed"] += 1
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "warnings": warnings,
        "bundles": bundles,
    }


def _render_text(results: list[CheckResult], summary: dict[str, object]) -> None:
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
    emit_diagnostic(
        f"Summary: {summary['passed']}/{summary['total']} passed, "
        f"{summary['errors']} errors, {summary['warnings']} warnings"
    )


def register(sub: argparse._SubParsersAction) -> None:
    cli_parser = sub.add_parser(
        "cli",
        help="CLI-related commands: cite a reference tree, verify against the rubric.",
    )
    cli_sub = cli_parser.add_subparsers(dest="cli_command")

    cite = cli_sub.add_parser(
        "cite",
        help="Emit the agent-first CLI reference tree into <path>/.afi/reference/.",
    )
    cite.add_argument("path", nargs="?", default=".", help="Target project path (default: .).")
    cite.add_argument(
        "--lang",
        default="python",
        choices=list(SUPPORTED_LANGS),
        help="Reference language (default: python).",
    )
    cite.add_argument(
        "--out",
        default=None,
        help="Override output directory (default: <path>/.afi/reference/<lang>-cli/).",
    )
    cite.add_argument("--json", action="store_true", help="Emit structured JSON.")
    cite.set_defaults(func=cmd_cite)

    verify = cli_sub.add_parser(
        "verify",
        help="Audit a CLI at <path> against the six-bundle agent-first rubric.",
    )
    verify.add_argument("path", nargs="?", default=".", help="Target project path (default: .).")
    verify.add_argument("--json", action="store_true", help="Emit structured JSON.")
    verify.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures (non-zero exit on any not-passed check).",
    )
    verify.set_defaults(func=cmd_verify)

    overview = cli_sub.add_parser(
        "overview",
        help="Read-only descriptive snapshot of the CLI at <path> (defaults: afi template).",
    )
    overview.add_argument(
        "path",
        nargs="?",
        default=None,
        help=(
            "Target project path. If omitted (or the target has no CLI surface), "
            "describe afi's default scaffolded template."
        ),
    )
    overview.add_argument("--json", action="store_true", help="Emit structured JSON.")
    overview.set_defaults(func=cmd_cli_overview)

    def _no_verb(_args: argparse.Namespace) -> int:
        cli_parser.print_help()
        return 0

    cli_parser.set_defaults(func=_no_verb)
