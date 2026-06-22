"""The ``cli`` noun group — verbs ``doctor``, ``overview``.

``agentfront cli doctor``   — run the seven-bundle rubric against a target CLI
                       and surface inconsistencies with actionable remediation
                       (replaces ``agentfront cli verify``; ``--fix`` applies any
                       auto-fixable handlers).
``agentfront cli overview`` — read-only descriptive snapshot of a target CLI.

``agentfront cli verify`` is kept as a deprecated alias that forwards to
``cli doctor`` for one minor cycle; removed in v0.6.0.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from agentfront.cli._commands.doctor import cmd_cli_doctor, cmd_cli_verify_deprecated
from agentfront.cli._output import emit_result
from agentfront.overview import build as build_overview
from agentfront.overview import to_json_dict, to_markdown

_JSON_HELP = "Emit structured JSON."
_PATH_HELP = "Target project path (default: .)."
_STRICT_HELP = "Treat warnings as failures (non-zero exit on any not-passed check)."


def cmd_cli_overview(args: argparse.Namespace) -> int:
    """Handler for ``agentfront cli overview [path]``.

    Read-only descriptive snapshot. If ``path`` is missing or points at a
    project without a detectable CLI surface, emits the overview of agentfront's
    own runtime model (the "zero-target default").
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


def register(sub: argparse._SubParsersAction) -> None:
    cli_parser = sub.add_parser(
        "cli",
        help="CLI-related commands: doctor a target against the agent-first rubric.",
    )
    cli_sub = cli_parser.add_subparsers(dest="cli_command")

    doctor = cli_sub.add_parser(
        "doctor",
        help=(
            "Audit the CLI at <path> against the seven-bundle agent-first rubric "
            "and surface remediations; --fix applies auto-fixable ones."
        ),
    )
    # Default kept as None (not "."): the cwd fallback lives in cmd_cli_doctor
    # so we can tell "no args" from "explicit path" and reject `--package`
    # combined with an explicit path.
    doctor.add_argument(
        "path",
        nargs="?",
        default=None,
        help=_PATH_HELP + " Omit and pass --package to audit by distribution name.",
    )
    doctor.add_argument(
        "--package",
        default=None,
        metavar="NAME",
        help=(
            "Audit an editable-installed distribution by name (looks up "
            "its source root via PEP 610 direct_url.json). Mutually "
            "exclusive with the path positional."
        ),
    )
    doctor.add_argument("--json", action="store_true", help=_JSON_HELP)
    # --fix and --dry-run are alternatives: --dry-run previews what --fix
    # would do. Mutually exclusive at the argparse layer so passing both
    # gives a clear error instead of silent precedence.
    fix_group = doctor.add_mutually_exclusive_group()
    fix_group.add_argument(
        "--fix",
        action="store_true",
        help="Apply auto-fixable remediations.",
    )
    fix_group.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Preview which fixes would be applied without mutating.",
    )
    doctor.add_argument(
        "--strict",
        action="store_true",
        help=_STRICT_HELP,
    )
    doctor.set_defaults(func=cmd_cli_doctor)

    # Deprecated alias for one minor cycle. Mirror the v0.4 verify shape so
    # CI and scripts that call `agentfront cli verify .` keep working; the deprecation
    # diagnostic is emitted by cmd_cli_verify_deprecated to stderr.
    verify = cli_sub.add_parser(
        "verify",
        help="(Deprecated) Alias for `agentfront cli doctor`. Removed in v0.6.0.",
    )
    verify.add_argument("path", nargs="?", default=".", help=_PATH_HELP)
    verify.add_argument("--json", action="store_true", help=_JSON_HELP)
    verify.add_argument(
        "--strict",
        action="store_true",
        help=_STRICT_HELP,
    )
    verify.set_defaults(func=cmd_cli_verify_deprecated)

    overview = cli_sub.add_parser(
        "overview",
        help=(
            "Read-only descriptive snapshot of the CLI at <path> "
            "(defaults: agentfront's runtime model)."
        ),
    )
    overview.add_argument(
        "path",
        nargs="?",
        default=None,
        help=(
            "Target project path. If omitted (or the target has no CLI surface), "
            "describe agentfront's own runtime model."
        ),
    )
    overview.add_argument("--json", action="store_true", help=_JSON_HELP)
    overview.set_defaults(func=cmd_cli_overview)

    def _no_verb(_args: argparse.Namespace) -> int:
        cli_parser.print_help()
        return 0

    cli_parser.set_defaults(func=_no_verb)
