"""Tests for the CLI builder — make_cli/run_cli with registered tools (t8).

Asserts:
  - a registered typed op becomes an invocable subcommand that runs with parsed args
  - every generated verb supports --json: success->stdout, failure->stderr+nonzero exit
  - a registered noun group with no verb renders that group's overview (exit 0)
  - host commands are dispatched
  - learn/doctor meta-verbs still work
  - no-command handler is invoked when no subcommand is given
"""

from __future__ import annotations

import json

import pytest

from agentfront import App
from agentfront.cli_surface import make_cli, run_cli
from agentfront.errors import AgentfrontError

# --- fixtures -----------------------------------------------------------


@pytest.fixture
def app_with_tools() -> App:
    """An App with grouped tools for CLI builder tests."""
    app = App(name="mytool", version="1.0.0")

    @app.tool(group="feedback")
    def record(item: str, score: int = 0) -> str:
        """Record feedback."""
        return f"{item}:{score}"

    @app.tool(group="feedback")
    def list_items() -> list[str]:
        """List recorded items."""
        return []

    @app.tool(group="auth")
    def login(username: str, password: str) -> str:
        """Login."""
        return username

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    return app


# --- registered typed op dispatch ----------------------------------------


def test_registered_op_invoked_with_parsed_args(app_with_tools: App, capsys) -> None:
    """A registered typed op becomes invocable: run_cli actually CALLS it."""
    rc = run_cli(app_with_tools, ["feedback", "record", "hello", "--score", "5"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "hello:5" in out


def test_registered_op_positional_only(app_with_tools: App, capsys) -> None:
    """Required positional params work without --flag syntax."""
    rc = run_cli(app_with_tools, ["feedback", "record", "world"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "world:0" in out


def test_registered_op_with_default(app_with_tools: App, capsys) -> None:
    """Default values are used when not provided."""
    rc = run_cli(app_with_tools, ["feedback", "record", "test"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "test:0" in out


def test_grouped_op_with_multiple_positionals(app_with_tools: App, capsys) -> None:
    """Multiple required positional params work."""
    rc = run_cli(app_with_tools, ["auth", "login", "alice", "secret"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "alice" in out


def test_top_level_tool_invoked(app_with_tools: App, capsys) -> None:
    """Top-level (ungrouped) tools are invocable directly."""
    rc = run_cli(app_with_tools, ["search", "query"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "query" in out


# --- --json support on generated verbs -----------------------------------


def test_verb_json_mode_success(app_with_tools: App, capsys) -> None:
    """A verb returning a value with --json prints JSON to stdout."""
    rc = run_cli(app_with_tools, ["feedback", "record", "hello", "--score", "5", "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload == "hello:5"


def test_verb_no_json_mode_success(app_with_tools: App, capsys) -> None:
    """Without --json, the verb prints plain text to stdout."""
    rc = run_cli(app_with_tools, ["feedback", "record", "hello", "--score", "5"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "hello:5" in captured.out
    # Should NOT be JSON
    assert not captured.out.strip().startswith("{")


# --- error handling on generated verbs -----------------------------------


@pytest.fixture
def app_with_error_tool() -> App:
    """An App with a tool that raises AgentfrontError."""
    app = App(name="errtool", version="1.0.0")

    @app.tool(group="ops")
    def boom() -> None:
        """Cause an error."""
        raise AgentfrontError(code=1, message="boom", remediation="fix it")

    return app


def test_verb_error_structured_stderr(app_with_error_tool: App, capsys) -> None:
    """An op raising AgentfrontError emits structured error to stderr."""
    rc = run_cli(app_with_error_tool, ["ops", "boom"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert captured.out == ""


def test_verb_error_json_mode(app_with_error_tool: App, capsys) -> None:
    """With --json, error is JSON on stderr, stdout clean."""
    rc = run_cli(app_with_error_tool, ["ops", "boom", "--json"])
    assert rc == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.err.strip())
    assert payload["code"] == 1
    assert payload["message"] == "boom"
    assert payload["remediation"] == "fix it"
    assert captured.out == ""


# --- bare noun group overview ------------------------------------------


def test_bare_noun_group_overview(app_with_tools: App, capsys) -> None:
    """Invoking a noun group with no verb renders its overview (exit 0)."""
    rc = run_cli(app_with_tools, ["feedback"])
    assert rc == 0
    out = capsys.readouterr().out
    # Should list the group's verbs
    assert "record" in out
    assert "list_items" in out


def test_bare_noun_group_overview_auth(app_with_tools: App, capsys) -> None:
    """Another group's overview lists its own verbs."""
    rc = run_cli(app_with_tools, ["auth"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "login" in out


# --- host commands ------------------------------------------------------


def test_host_command_dispatched(app_with_tools: App, capsys) -> None:
    """A registered host command is dispatched."""
    called = [False]

    def handler(args):
        called[0] = True
        return 0

    app_with_tools.add_command("custom", handler, help="custom command")

    rc = run_cli(app_with_tools, ["custom"])
    assert rc == 0
    assert called[0] is True


def test_host_command_with_configure(app_with_tools: App, capsys) -> None:
    """A host command's configure callback is called."""
    called = [False]

    def handler(args):
        return 0

    def configure(parser):
        called[0] = True
        parser.add_argument("--flag", action="store_true")

    app_with_tools.add_command("configured", handler, help="configured", configure=configure)
    rc = run_cli(app_with_tools, ["configured", "--flag"])
    assert rc == 0
    assert called[0] is True


# --- learn/doctor meta-verbs ------------------------------------------


def test_learn_still_works(app_with_tools: App, capsys) -> None:
    """The learn meta-verb still works."""
    rc = run_cli(app_with_tools, ["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "mytool" in out


def test_learn_json_still_works(app_with_tools: App, capsys) -> None:
    """learn --json still works."""
    rc = run_cli(app_with_tools, ["learn", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "mytool"


def test_doctor_still_works(app_with_tools: App, capsys) -> None:
    """The doctor meta-verb still works."""
    rc = run_cli(app_with_tools, ["doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "mytool" in out


# --- no-command handler ------------------------------------------------


def test_no_command_handler_invoked() -> None:
    """When no subcommand is given and no_command_handler is set, it's called."""
    app = App(name="t", version="1.0")

    def handler(args):
        return 42

    app.set_no_command_handler(handler)
    rc = run_cli(app, [])
    assert rc == 42


def test_no_command_handler_none_prints_help() -> None:
    """When no subcommand and no handler, prints help and returns 0."""
    app = App(name="t", version="1.0")
    rc = run_cli(app, [])
    assert rc == 0


# --- aliases ----------------------------------------------------------


def test_tool_alias_works(capsys) -> None:
    """A tool alias resolves to the same handler."""
    app = App(name="t", version="1.0")

    @app.tool(group="ops", aliases=("rec",))
    def record(item: str) -> str:
        """Record."""
        return item

    rc = run_cli(app, ["ops", "rec", "hello"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "hello" in out


# --- bool-annotated params become --flag/--no-flag -----------------------


def test_bool_param_becomes_boolean_optional(capsys) -> None:
    """A bool-annotated param becomes --flag/--no-flag."""
    app = App(name="t", version="1.0")

    @app.tool(group="ops")
    def toggle(enabled: bool = False) -> str:
        """Toggle."""
        return str(enabled)

    rc = run_cli(app, ["ops", "toggle", "--enabled"])
    assert rc == 0
    assert "True" in capsys.readouterr().out

    rc2 = run_cli(app, ["ops", "toggle", "--no-enabled"])
    assert rc2 == 0
    assert "False" in capsys.readouterr().out


# --- make_cli returns parser -------------------------------------------


def test_make_cli_returns_parser(app_with_tools: App) -> None:
    """make_cli returns an ArgumentParser."""
    parser = make_cli(app_with_tools)
    assert parser is not None
    assert hasattr(parser, "parse_args")


# --- unknown verb exits nonzero ----------------------------------------


def test_unknown_verb_exits_nonzero(app_with_tools: App) -> None:
    """An unknown verb exits with nonzero code."""
    rc = run_cli(app_with_tools, ["bogus"])
    assert rc != 0
