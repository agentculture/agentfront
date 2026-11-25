"""Public CLI hooks: ``App.run_cli``, ``App.meta_verb``, ``App.add_learn_section``.

These are the supported replacements for reaching into ``cli_surface``'s
private names (``_CliParser``, ``_dispatch``, ``_propagate_raw_argv``,
``parser._actions``) to run an app's CLI for an exit code and to point the
reserved meta-verbs at host handlers.
"""

from __future__ import annotations

import argparse
import json
import sys

import pytest

import agentfront
from agentfront import App, Flag
from agentfront._registry import DuplicateError
from agentfront.errors import EXIT_ENV_ERROR, AgentfrontError
from agentfront.serve import surfaces_agree
from agentfront.testing import run_cli as harness_run_cli


@pytest.fixture
def app() -> App:
    a = App(name="mytool", version="1.2.3", description="A test tool for hooks.")
    a.add_doc(slug="intro", title="Introduction", text="# Intro\nbody")

    @a.tool
    def search(query: str) -> str:
        """Search the corpus."""
        return query

    @a.tool(group="data")
    def broken() -> str:
        """Always fails with an environment error."""
        raise AgentfrontError(code=EXIT_ENV_ERROR, message="no backend", remediation="start it")

    @a.tool(group="data")
    def interrupted() -> str:
        """Simulates Ctrl-C."""
        raise KeyboardInterrupt

    return a


# --- top-level Flag export --------------------------------------------------


def test_flag_is_exported_at_top_level() -> None:
    from agentfront._registry import Flag as RegistryFlag

    assert Flag is RegistryFlag
    assert "Flag" in agentfront.__all__


# --- App.run_cli: always an int, never SystemExit -----------------------------


def test_app_run_cli_dispatches_and_returns_zero(app: App, capsys) -> None:
    assert app.run_cli(["search", "hello"]) == 0
    assert capsys.readouterr().out.strip() == "hello"


def test_app_run_cli_help_returns_zero_without_system_exit(app: App, capsys) -> None:
    assert app.run_cli(["--help"]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_app_run_cli_version_flag(app: App, capsys) -> None:
    assert app.run_cli(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "mytool 1.2.3"


def test_app_run_cli_parse_error_returns_one_with_hint(app: App, capsys) -> None:
    assert app.run_cli(["bogus-verb"]) == 1
    err = capsys.readouterr().err
    assert "hint:" in err
    assert "Traceback" not in err


def test_app_run_cli_parse_error_honours_json(app: App, capsys) -> None:
    assert app.run_cli(["bogus-verb", "--json"]) == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["code"] == 1
    assert payload["remediation"]


def test_app_run_cli_none_argv_reads_sys_argv_for_json_peek(app: App, capsys, monkeypatch) -> None:
    """With argv=None the parse-error path still sees --json (it reads sys.argv)."""
    monkeypatch.setattr(sys, "argv", ["mytool", "bogus-verb", "--json"])
    assert app.run_cli() == 1
    assert json.loads(capsys.readouterr().err)["code"] == 1


def test_app_run_cli_handler_error_code_propagates(app: App, capsys) -> None:
    assert app.run_cli(["data", "broken"]) == EXIT_ENV_ERROR
    assert "hint: start it" in capsys.readouterr().err


def test_app_run_cli_keyboard_interrupt_returns_130(app: App) -> None:
    assert app.run_cli(["data", "interrupted"]) == 130


def test_host_added_version_flag_still_wins(app: App, capsys) -> None:
    """A host that adds its own --version to app.cli() must not hit a conflict."""
    parser = app.cli()
    parser.add_argument("--version", action="version", version="custom 9")
    from agentfront.cli_surface import _CliParser

    with pytest.raises(_CliParser._Exit):  # the generated parser's internal exit signal
        parser.parse_args(["--version"])
    assert capsys.readouterr().out.strip() == "custom 9"


def test_no_command_handler_none_return_is_zero(app: App) -> None:
    app.set_no_command_handler(lambda args: None)
    assert app.run_cli([]) == 0


def test_no_command_handler_error_is_structured(app: App, capsys) -> None:
    def handler(args: argparse.Namespace) -> int:
        raise AgentfrontError(code=EXIT_ENV_ERROR, message="nope", remediation="fix it")

    app.set_no_command_handler(handler)
    assert app.run_cli([]) == EXIT_ENV_ERROR
    assert "hint: fix it" in capsys.readouterr().err


# --- App.meta_verb ------------------------------------------------------------


def test_meta_verb_decorator_overrides_doctor(app: App) -> None:
    seen: list[argparse.Namespace] = []

    @app.meta_verb("doctor")
    def my_doctor(args: argparse.Namespace) -> int:
        seen.append(args)
        return 1

    assert my_doctor.__name__ == "my_doctor"  # decorator returns the function
    assert app.run_cli(["doctor", "--json"]) == 1
    assert len(seen) == 1
    assert seen[0].json is True


def test_meta_verb_call_form_with_configure(app: App) -> None:
    seen: list[argparse.Namespace] = []

    def configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--deep", action="store_true")

    app.meta_verb("explain", lambda args: seen.append(args), configure=configure)
    assert app.run_cli(["explain", "data", "broken", "--deep"]) == 0
    assert seen[0].path == ["data", "broken"]
    assert seen[0].deep is True
    assert seen[0].json is False


def test_meta_verb_overview_receives_scope(app: App) -> None:
    seen: list[argparse.Namespace] = []
    app.meta_verb("overview", lambda args: seen.append(args) or 0)
    assert app.run_cli(["overview", "some/path", "--json"]) == 0
    assert seen[0].scope == "some/path"
    assert seen[0].json is True


def test_meta_verb_handler_errors_are_structured(app: App, capsys) -> None:
    @app.meta_verb("explain")
    def explain(args: argparse.Namespace) -> int:
        raise AgentfrontError(code=1, message="no such path", remediation="try overview")

    assert app.run_cli(["explain", "zzz", "--json"]) == 1
    assert json.loads(capsys.readouterr().err)["remediation"] == "try overview"


def test_meta_verb_unexpected_exception_has_no_traceback(app: App, capsys) -> None:
    @app.meta_verb("doctor")
    def doctor(args: argparse.Namespace) -> int:
        raise RuntimeError("boom")

    assert app.run_cli(["doctor"]) == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "boom" in err


def test_meta_verb_learn_is_not_overridable(app: App) -> None:
    with pytest.raises(ValueError, match="add_learn_section"):
        app.meta_verb("learn", lambda args: 0)


def test_meta_verb_unknown_name_rejected(app: App) -> None:
    with pytest.raises(ValueError, match="explain"):
        app.meta_verb("search", lambda args: 0)


def test_meta_verb_double_override_rejected(app: App) -> None:
    app.meta_verb("doctor", lambda args: 0)
    with pytest.raises(DuplicateError):
        app.meta_verb("doctor", lambda args: 0)


def test_meta_verb_override_leaves_registry_and_surfaces_untouched(app: App) -> None:
    before = [t.name for t in app.list_tools()]
    app.meta_verb("doctor", lambda args: 0)
    app.meta_verb("explain", lambda args: 0)
    app.meta_verb("overview", lambda args: 0)
    assert [t.name for t in app.list_tools()] == before
    assert surfaces_agree(app)


# --- built-in meta-verbs: --json everywhere, rubric-shaped -------------------


def test_builtin_doctor_accepts_json_with_rubric_shape(app: App) -> None:
    result = harness_run_cli(app, ["doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["healthy"] is True
    assert payload["checks"]
    for check in payload["checks"]:
        assert {"id", "passed", "severity", "message", "remediation"} <= set(check)


def test_builtin_explain_accepts_app_name_as_root(app: App) -> None:
    result = harness_run_cli(app, ["explain", "mytool"])
    assert result.exit_code == 0
    assert "mytool" in result.stdout


def test_builtin_learn_carries_rubric_markers(app: App) -> None:
    out = harness_run_cli(app, ["learn"]).stdout.lower()
    assert len(out) >= 200
    for marker in ("purpose", "commands", "exit", "--json", "explain"):
        assert marker in out
    for code in ("0", "1", "2"):
        assert code in out


def test_builtin_learn_json_keeps_inventory_and_adds_policy(app: App) -> None:
    payload = json.loads(harness_run_cli(app, ["learn", "--json"]).stdout)
    assert {d["slug"] for d in payload["docs"]} == {"intro"}
    assert ["search"] in [t["path"] for t in payload["tools"]]
    assert payload["purpose"] == "A test tool for hooks."
    assert set(payload["exit_codes"]) >= {"0", "1", "2"}
    assert payload["json_support"] is True
    assert payload["explain"] == "mytool explain <path>"
    assert payload["sections"] == []


# --- App.add_learn_section ------------------------------------------------------


def test_add_learn_section_renders_in_text_and_json(app: App) -> None:
    app.add_learn_section("Runtime", "Needs the core daemon on its Unix socket.")
    assert app.learn_sections == (("Runtime", "Needs the core daemon on its Unix socket."),)

    text = harness_run_cli(app, ["learn"]).stdout
    assert "## Runtime" in text
    assert "Needs the core daemon" in text

    payload = json.loads(harness_run_cli(app, ["learn", "--json"]).stdout)
    assert payload["sections"] == [
        {"title": "Runtime", "text": "Needs the core daemon on its Unix socket."}
    ]
    # the inventory the cross-surface agreement check reads is intact
    assert surfaces_agree(app)


def test_add_learn_section_rejects_empty_title(app: App) -> None:
    with pytest.raises(ValueError):
        app.add_learn_section("  ", "body")


# --- back-compat: the private path existing consumers use keeps working --------


def test_legacy_private_parser_patching_still_works(app: App, capsys) -> None:
    """Mirror culture-agents' pre-public-API flow (agentfront 0.21.x) end to end."""
    from agentfront.cli_surface import _CliParser, _dispatch, _propagate_raw_argv

    parser = app.cli()
    parser.add_argument("--version", action="version", version="%(prog)s 7.7")
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    calls: list[str] = []
    for name in ("learn", "explain", "overview", "doctor"):
        verb = subparsers.choices[name]
        if not any("--json" in a.option_strings for a in verb._actions):
            verb.add_argument("--json", action="store_true")
        verb.set_defaults(func=lambda args, n=name: calls.append(n) or 0)

    argv = ["doctor", "--json"]
    _propagate_raw_argv(parser, argv)
    args = parser.parse_args(argv)
    assert _dispatch(args, json_mode=True) == 0
    assert calls == ["doctor"]

    with pytest.raises(_CliParser._Exit) as stop:
        parser.parse_args(["--version"])
    assert stop.value.code == 0
    assert capsys.readouterr().out.strip() == "mytool 7.7"


def test_run_cli_always_returns_an_int(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    @app.meta_verb("doctor")
    def my_doctor(args: argparse.Namespace):
        return "healthy"  # not an exit code

    code = app.run_cli(["doctor"])
    assert code == 0
    assert type(code) is int


def test_a_conflicting_configure_is_a_clean_error_not_a_traceback(
    app: App, capsys: pytest.CaptureFixture[str]
) -> None:
    def configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json")  # conflicts with the built-in --json

    @app.meta_verb("doctor", configure=configure)
    def my_doctor(args: argparse.Namespace) -> int:
        return 0

    assert app.run_cli(["doctor", "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["message"].startswith("this CLI could not be built")
    assert "Traceback" not in captured.err


def test_explain_root_honours_json(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    assert app.run_cli(["explain", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == []
    assert payload["version"] == app.version
