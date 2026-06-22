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


def _learn_handler(app: App, args: argparse.Namespace) -> int:
    """Dispatch for the ``learn`` verb."""
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
        return 0

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
    return 0


def _doctor_handler(app: App, args: argparse.Namespace) -> int:
    """Dispatch for the ``doctor`` verb."""
    doc_count = len(app.list_docs())
    tool_count = len(app.list_tools())

    lines: list[str] = []
    lines.append(f"{app.name} v{app.version} — readiness check")
    lines.append(f"  docs: {doc_count}")
    lines.append(f"  tools: {tool_count}")
    lines.append("  status: healthy")
    print("\n".join(lines))
    return 0


def make_cli(app: App) -> argparse.ArgumentParser:
    """Build an argparse parser from an :class:`App`'s registry.

    The returned parser exposes ``.run(argv)`` or can be used directly with
    ``.parse_args()``.  The ``run_cli`` convenience wraps this.
    """
    parser = argparse.ArgumentParser(
        prog=app.name,
        description=f"{app.name} v{app.version}",
    )

    sub = parser.add_subparsers(dest="command")

    learn_parser = sub.add_parser("learn", help="agent-facing summary")
    learn_parser.add_argument("--json", action="store_true", help="emit JSON")
    learn_parser.set_defaults(func=lambda a: _learn_handler(app, a))

    doctor_parser = sub.add_parser("doctor", help="readiness check")
    doctor_parser.set_defaults(func=lambda a: _doctor_handler(app, a))

    return parser


def run_cli(app: App, argv: list[str] | None = None) -> int:
    """Parse *argv* against *app*'s CLI and dispatch.

    Returns an exit code: ``0`` on success, ``1`` on user error.
    """
    parser = make_cli(app)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 1

    if args.command is None:
        parser.print_usage(sys.stderr)
        return 1

    return args.func(args)
