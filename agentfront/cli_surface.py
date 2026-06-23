"""CLI surface derived from an :class:`agentfront.App`.

The host writes **zero** argparse code — building the CLI is just
``make_cli(app)``.  The surface reads from the App's single registry so it
cannot drift out of sync with the MCP or HTTP surfaces.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agentfront.app import App

__all__ = ["make_cli", "run_cli"]


class _CliParser(argparse.ArgumentParser):
    """An ``ArgumentParser`` that signals exit via an internal exception.

    argparse normally calls :func:`sys.exit` for ``--help`` (code 0) and parse
    errors (code 2). ``run_cli`` needs to *translate* those into a return value
    (so hosts and tests can call it in-process), but catching ``SystemExit`` to
    do that is both flagged by static analysis (SonarCloud S5754) and would
    silently swallow a genuine ``sys.exit`` raised by a tool handler. Overriding
    :meth:`exit` to raise a private exception keeps the translation local and
    precise: only argparse's own exits are intercepted.
    """

    class _Exit(Exception):
        """Carries argparse's intended exit code out to ``run_cli``."""

        def __init__(self, code: int) -> None:
            super().__init__(code)
            self.code = code

    def exit(self, status: int = 0, message: str | None = None) -> Any:  # type: ignore[override]
        if message:
            self._print_message(message, sys.stderr)
        raise self._Exit(status)


def _learn_handler(app: App, args: argparse.Namespace) -> None:
    """Dispatch for the ``learn`` verb — prints the agent-facing summary."""
    docs = [{"slug": d.slug, "title": d.title} for d in app.list_docs()]
    tools = [{"name": t.name, "description": t.description} for t in app.list_tools()]

    if args.json:
        payload: dict[str, Any] = {
            "name": app.name,
            "version": app.version,
            "docs": docs,
            "tools": tools,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return

    lines: list[str] = []
    lines.append(f"# {app.name} v{app.version}")
    if app.description:
        lines.append(app.description)
    lines.append("")

    lines.append("## Docs")
    for d in docs:
        lines.append(f"  - {d['slug']}: {d['title']}")
    lines.append("")

    lines.append("## Tools")
    for t in tools:
        lines.append(f"  - {t['name']}: {t['description']}")
    lines.append("")

    print("\n".join(lines))


def _doctor_handler(app: App) -> None:
    """Dispatch for the ``doctor`` verb — prints a readiness check."""
    doc_count = len(app.list_docs())
    tool_count = len(app.list_tools())

    lines: list[str] = []
    lines.append(f"{app.name} v{app.version} — readiness check")
    lines.append(f"  docs: {doc_count}")
    lines.append(f"  tools: {tool_count}")
    lines.append("  status: healthy")
    print("\n".join(lines))


def make_cli(app: App) -> argparse.ArgumentParser:
    """Build an argparse parser from an :class:`App`'s registry.

    The returned parser can be used directly with ``.parse_args()``; the
    ``run_cli`` convenience wraps it and translates argparse's exits into a
    return code.
    """
    parser = _CliParser(
        prog=app.name,
        description=f"{app.name} v{app.version}",
    )

    sub = parser.add_subparsers(dest="command")

    learn_parser = sub.add_parser("learn", help="agent-facing summary")
    learn_parser.add_argument("--json", action="store_true", help="emit JSON")
    learn_parser.set_defaults(func=lambda a: _learn_handler(app, a))

    doctor_parser = sub.add_parser("doctor", help="readiness check")
    doctor_parser.set_defaults(func=lambda a: _doctor_handler(app))

    return parser


def run_cli(app: App, argv: list[str] | None = None) -> int:
    """Parse *argv* against *app*'s CLI and dispatch.

    Returns an exit code: argparse's own code for ``--help`` (0) and parse
    errors (2), ``1`` for an empty invocation, otherwise ``0`` on success.
    """
    parser = make_cli(app)
    try:
        args = parser.parse_args(argv)
    except _CliParser._Exit as exc:
        # argparse exits 0 for --help and 2 for a parse error; preserve that
        # instead of flattening --help to a failure.
        return exc.code

    if args.command is None:
        parser.print_usage(sys.stderr)
        return 1

    args.func(args)
    return 0
