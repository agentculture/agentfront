"""The ``cli`` noun group — verbs ``cite``, ``doctor``, ``overview``.

``afi cli cite``     — drop the agent-first CLI reference tree into the target
                       project under ``.afi/reference/<lang>-cli/``.
``afi cli doctor``   — run the seven-bundle rubric against a target CLI
                       and surface inconsistencies with actionable remediation
                       (replaces ``afi cli verify``; ``--fix`` applies any
                       auto-fixable handlers).
``afi cli overview`` — read-only descriptive snapshot of a target CLI.

``afi cli verify`` is kept as a deprecated alias that forwards to
``cli doctor`` for one minor cycle; removed in v0.6.0.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from afi.cite import SUPPORTED_LANGS, emit_reference
from afi.cli._commands.doctor import cmd_cli_doctor, cmd_cli_verify_deprecated
from afi.cli._output import emit_result
from afi.overview import build as build_overview
from afi.overview import to_json_dict, to_markdown

_JSON_HELP = "Emit structured JSON."
_PATH_HELP = "Target project path (default: .)."
_STRICT_HELP = "Treat warnings as failures (non-zero exit on any not-passed check)."


def cmd_cite(args: argparse.Namespace) -> None:
    """Handler for ``afi cli cite``.

    Returns ``None`` on success (treated as ``EXIT_SUCCESS`` by
    :func:`afi.cli._dispatch`); every failure path raises
    :class:`AfiError`.
    """
    target_path = Path(args.path).resolve()
    lang = args.lang
    out = Path(args.out).resolve() if args.out else None
    report = emit_reference(target_path, lang=lang, out=out)
    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        emit_result(report.to_dict(), json_mode=True)
        return

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
            "For the rubric itself:    afi explain cli doctor",
        ]
    )
    emit_result("\n".join(lines), json_mode=False)


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


def register(sub: argparse._SubParsersAction) -> None:
    cli_parser = sub.add_parser(
        "cli",
        help="CLI-related commands: cite a reference tree, doctor against the rubric.",
    )
    cli_sub = cli_parser.add_subparsers(dest="cli_command")

    cite = cli_sub.add_parser(
        "cite",
        help="Emit the agent-first CLI reference tree into <path>/.afi/reference/.",
    )
    cite.add_argument("path", nargs="?", default=".", help=_PATH_HELP)
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
    cite.add_argument("--json", action="store_true", help=_JSON_HELP)
    cite.set_defaults(func=cmd_cite)

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
    # CI and scripts that call `afi cli verify .` keep working; the deprecation
    # diagnostic is emitted by cmd_cli_verify_deprecated to stderr.
    verify = cli_sub.add_parser(
        "verify",
        help="(Deprecated) Alias for `afi cli doctor`. Removed in v0.6.0.",
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
    overview.add_argument("--json", action="store_true", help=_JSON_HELP)
    overview.set_defaults(func=cmd_cli_overview)

    def _no_verb(_args: argparse.Namespace) -> int:
        cli_parser.print_help()
        return 0

    cli_parser.set_defaults(func=_no_verb)
