"""Unified CLI entry point for afi.

Noun-based command groups will be registered here as they land. The initial
scaffold ships only the top-level parser, `--version`, and a `learn` stub so
the agent-learnability principle is wired in from commit one.
"""

from __future__ import annotations

import argparse
import sys

from afi import __version__


def _cmd_learn(_args: argparse.Namespace) -> int:
    """Print a minimal self-description aimed at an agent reader.

    This is the `learn` affordance: an agent can run `afi learn` and get
    enough to author its own usage skill without scraping `--help`.
    """
    print(
        "afi — Agent First Interface scaffolder.\n"
        "\n"
        "Status: scaffold only. No feature commands yet.\n"
        "\n"
        "Planned surfaces (all generated from one source of truth):\n"
        "  - CLI with learn affordance (this command is the prototype).\n"
        "  - MCP server with a minimal menu.\n"
        "  - HTTP site with markdown pages and a sitemap.\n"
        "\n"
        "See: https://github.com/agentculture/afi-cli"
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="afi",
        description="afi — Agent First Interface scaffolder",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    learn = sub.add_parser("learn", help="Print a self-description for agent consumers.")
    learn.set_defaults(func=_cmd_learn)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
