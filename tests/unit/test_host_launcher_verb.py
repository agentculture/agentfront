"""Host launcher verb: a host-owned REPL/TUI command registered via add_command.

Demonstrates the boundary: agentfront cannot generate a raw-mode REPL; the host
registers it via the extension hook (app.add_command). The verb appears beside
generated verbs in the CLI and dispatches to the host-written handler.
"""

from __future__ import annotations

import argparse
from typing import Optional

from agentfront import App
from agentfront.cli_surface import make_cli, run_cli


def test_host_tui_command_dispatches_handler() -> None:
    """A host-written 'tui' command registered via add_command dispatches correctly."""
    called = [False]

    def tui_handler(args: argparse.Namespace) -> Optional[int]:
        called[0] = True
        return 0

    app = App(name="mytool", version="1.0")
    app.add_command("tui", tui_handler, help="launch interactive TUI")

    rc = run_cli(app, ["tui"])
    assert rc == 0
    assert called[0] is True


def test_host_tui_command_appears_in_cli_parser() -> None:
    """The host 'tui' command appears as a subparser alongside generated verbs."""
    app = App(name="mytool", version="1.0")

    @app.tool
    def search(query: str) -> str:
        """Search the corpus."""
        return query

    app.add_command("tui", lambda args: 0, help="launch interactive TUI")

    parser = make_cli(app)
    # Parse with --help to see available subcommands
    # We check that 'tui' is a valid subcommand by parsing it
    args = parser.parse_args(["tui"])
    assert hasattr(args, "func")
    assert args.func is not None


def test_host_command_appears_beside_generated_verbs() -> None:
    """Host commands and generated tools coexist in the same CLI."""
    app = App(name="mytool", version="1.0")

    @app.tool
    def search(query: str) -> str:
        """Search the corpus."""
        return query

    @app.tool
    def index(path: str) -> str:
        """Index a file."""
        return path

    tui_called = [False]

    def tui_handler(args: argparse.Namespace) -> Optional[int]:
        tui_called[0] = True
        return 0

    app.add_command("tui", tui_handler, help="launch interactive TUI")

    # Both generated tools and the host command are dispatchable
    rc = run_cli(app, ["search", "test"])
    assert rc == 0

    rc = run_cli(app, ["tui"])
    assert rc == 0
    assert tui_called[0] is True


def test_host_command_with_configure_hook() -> None:
    """A host command can customise its argparse subparser via configure."""
    app = App(name="mytool", version="1.0")

    def configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--port", type=int, default=8080)

    def handler(args: argparse.Namespace) -> Optional[int]:
        assert hasattr(args, "port")
        assert args.port == 9090
        return 0

    app.add_command("serve", handler, help="start server", configure=configure)

    rc = run_cli(app, ["serve", "--port", "9090"])
    assert rc == 0


def test_host_command_not_generated_from_tool() -> None:
    """A host command is NOT a @app.tool — it's registered via add_command."""
    app = App(name="mytool", version="1.0")

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    app.add_command("tui", lambda args: 0, help="interactive TUI")

    # 'tui' is NOT in the tool registry
    tools = [t.name for t in app.list_tools()]
    assert "tui" not in tools

    # 'tui' IS in the host commands
    commands = [c.name for c in app.list_commands()]
    assert "tui" in commands

    # Both are dispatchable via the CLI
    rc = run_cli(app, ["tui"])
    assert rc == 0

    rc = run_cli(app, ["search", "q"])
    assert rc == 0
