"""Unit tests for host command registration and no-command handler (t7).

Covers:
  - add_command / get_command / list_commands
  - duplicate add_command raises DuplicateError
  - handler dispatchable via argparse subparser
  - set_no_command_handler / no_command_handler property
"""

import argparse
from typing import Optional

import pytest

from agentfront import App
from agentfront._registry import DuplicateError


def _make_handler() -> tuple:
    """Return (handler, called_flag) for testing dispatch."""
    called = [False]

    def handler(args: argparse.Namespace) -> Optional[int]:
        called[0] = True
        return None

    return handler, called


def test_add_command_registers_and_retrieves():
    app = App(name="t")
    handler, called = _make_handler()
    app.add_command("tui", handler, help="interactive UI")

    cmd = app.get_command("tui")
    assert cmd is not None
    assert cmd.name == "tui"
    assert cmd.handler is handler
    assert cmd.help == "interactive UI"


def test_list_commands_contains_registered():
    app = App(name="t")
    h1, _ = _make_handler()
    h2, _ = _make_handler()
    app.add_command("tui", h1, help="interactive UI")
    app.add_command("serve", h2, help="start server")

    commands = app.list_commands()
    names = {c.name for c in commands}
    assert names == {"tui", "serve"}


def test_duplicate_add_command_raises():
    app = App(name="t")
    h, _ = _make_handler()
    app.add_command("tui", h, help="interactive UI")

    with pytest.raises(DuplicateError):
        app.add_command("tui", h, help="duplicate")


def test_get_command_missing_returns_none():
    app = App(name="t")
    assert app.get_command("nonexistent") is None


def test_handler_dispatchable_via_subparser():
    """A host command's handler can be dispatched through argparse."""
    app = App(name="t")
    handler, called = _make_handler()
    app.add_command("tui", handler, help="interactive UI")

    cmd = app.get_command("tui")
    assert cmd is not None

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    sub = subparsers.add_parser(cmd.name, help=cmd.help)
    sub.set_defaults(func=cmd.handler)

    args = parser.parse_args(["tui"])
    result = args.func(args)
    assert called[0] is True
    assert result is None


def test_set_no_command_handler():
    app = App(name="t")

    def handler(args: argparse.Namespace) -> Optional[int]:
        return 0

    app.set_no_command_handler(handler)
    assert app.no_command_handler is handler


def test_no_command_handler_default_is_none():
    app = App(name="t")
    assert app.no_command_handler is None
