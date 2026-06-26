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


# --- BUG 4: reserved meta-verbs, tool collisions, alias collisions --------


def test_add_command_reserved_meta_verb_learn_raises():
    """add_command('learn', ...) must raise DuplicateError — learn is a meta-verb."""
    app = App(name="t")
    h, _ = _make_handler()
    with pytest.raises(DuplicateError, match="reserved"):
        app.add_command("learn", h, help="not allowed")


@pytest.mark.parametrize("verb", ["explain", "overview", "doctor"])
def test_add_command_reserved_meta_verbs(verb: str):
    """add_command for any reserved meta-verb raises DuplicateError."""
    app = App(name="t")
    h, _ = _make_handler()
    with pytest.raises(DuplicateError, match="reserved"):
        app.add_command(verb, h, help="not allowed")


def test_add_command_alias_collides_with_meta_verb_raises():
    """An alias colliding with a reserved meta-verb also raises."""
    app = App(name="t")
    h, _ = _make_handler()
    with pytest.raises(DuplicateError, match="reserved"):
        app.add_command("mylearn", h, aliases=("learn",))


def test_add_command_top_level_tool_collision_raises():
    """add_command colliding with a top-level tool name raises DuplicateError."""
    app = App(name="t")

    def deploy_fn() -> str:
        return "ok"

    app.tool(deploy_fn, name="deploy")
    h, _ = _make_handler()
    with pytest.raises(DuplicateError, match="already registered"):
        app.add_command("deploy", h, help="not allowed")


def test_add_command_alias_collides_with_top_level_tool_raises():
    """An alias colliding with a top-level tool name raises DuplicateError."""
    app = App(name="t")

    def deploy_fn() -> str:
        return "ok"

    app.tool(deploy_fn, name="deploy")
    h, _ = _make_handler()
    with pytest.raises(DuplicateError, match="already registered"):
        app.add_command("ship", h, aliases=("deploy",))


def test_add_command_alias_collides_with_existing_command_name_raises():
    """An alias colliding with an existing host command name raises DuplicateError."""
    app = App(name="t")
    h1, _ = _make_handler()
    h2, _ = _make_handler()
    app.add_command("tui", h1, help="interactive UI")
    with pytest.raises(DuplicateError, match="already registered"):
        app.add_command("console", h2, help="dup alias", aliases=("tui",))


def test_add_command_alias_collides_with_existing_command_alias_raises():
    """An alias colliding with an existing host command alias raises DuplicateError."""
    app = App(name="t")
    h1, _ = _make_handler()
    h2, _ = _make_handler()
    app.add_command("tui", h1, aliases=("ui",))
    with pytest.raises(DuplicateError, match="already registered"):
        app.add_command("console", h2, aliases=("ui",))


def test_add_command_non_colliding_still_builds_cli():
    """A non-colliding add_command still allows make_cli to build successfully."""
    app = App(name="t")

    def search_fn(query: str) -> str:
        return query

    app.tool(search_fn, name="search")
    h, _ = _make_handler()
    app.add_command("tui", h, help="interactive UI")

    from agentfront.cli_surface import make_cli

    parser = make_cli(app)
    # Verify the command is present by checking subparser names
    # argparse stores them in the _name_parser dict of the subparsers action
    subparsers_action = None
    for action in parser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_action = action
            break
    assert subparsers_action is not None
    assert "tui" in subparsers_action._name_parser_map
    assert "search" in subparsers_action._name_parser_map
