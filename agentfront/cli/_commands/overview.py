"""``agentfront overview [path]`` — top-level rollup across all interface surfaces.

Currently only the ``cli`` surface is implemented; ``mcp`` and ``site`` ship
in v0.4 / v0.5. This command is a rollup stub: it renders the ``cli``
subject and appends a ``> note:`` about the unimplemented surfaces so the
contract is locked in before those nouns exist.

When ``mcp`` and ``site`` inspectors land, this verb builds each and emits
a combined report. The public shape — a single :class:`OverviewReport` with
``subject="all"`` — is fixed now so culture's embed helper can write
against it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from agentfront.cli._output import emit_result
from agentfront.overview import build as build_overview
from agentfront.overview import to_json_dict, to_markdown


def cmd_overview(args: argparse.Namespace) -> int:
    raw = getattr(args, "path", None)
    path: Path | None = Path(raw).resolve() if raw else None
    report = build_overview("all", path)
    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        emit_result(to_json_dict(report), json_mode=True)
    else:
        emit_result(to_markdown(report), json_mode=False)
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "overview",
        help=(
            "Rollup overview across all interface surfaces (cli/mcp/site). "
            "Currently reports cli only; mcp/site land in v0.4/v0.5."
        ),
    )
    p.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Target project path. If omitted, describe agentfront's default scaffolded template.",
    )
    p.add_argument("--json", action="store_true", help="Emit structured JSON.")
    p.set_defaults(func=cmd_overview)
