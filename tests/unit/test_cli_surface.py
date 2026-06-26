"""Tests for ``agentfront.cli_surface`` — the host-agnostic CLI surface.

The host writes ZERO argparse code; ``make_cli(app)`` / ``run_cli(app, argv)``
build the CLI from the App's registry.
"""

from __future__ import annotations

import json

import pytest

from agentfront import App
from agentfront.app import Flag
from agentfront.cli_surface import make_cli, run_cli

# --- fixtures -----------------------------------------------------------


@pytest.fixture
def app() -> App:
    """A populated App with one doc and one tool."""
    a = App(name="mytool", version="1.0.0", description="A test tool")
    a.add_doc(slug="intro", title="Introduction", text="# Intro\nbody")
    a.add_doc(slug="usage", title="Usage Guide", text="# Usage\nhow to")

    @a.tool
    def search(query: str) -> str:
        """Search the corpus."""
        return query

    @a.tool(name="index")
    def _index(path: str) -> str:
        """Index a file."""
        return path

    return a


# --- learn ----------------------------------------------------------------


def test_learn_enumerates_doc_slugs(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "intro" in out
    assert "usage" in out


def test_learn_enumerates_tool_names(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "search" in out
    assert "index" in out


def test_learn_json_emits_valid_json(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["learn", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "mytool"
    assert payload["version"] == "1.0.0"
    assert isinstance(payload["docs"], list)
    assert isinstance(payload["tools"], list)


def test_learn_json_docs_match_registry(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(app, ["learn", "--json"])
    payload = json.loads(capsys.readouterr().out)
    doc_slugs = {d["slug"] for d in payload["docs"]}
    assert doc_slugs == {d.slug for d in app.list_docs()}


def test_learn_json_tools_match_registry(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(app, ["learn", "--json"])
    payload = json.loads(capsys.readouterr().out)
    tool_names = {t["name"] for t in payload["tools"]}
    assert tool_names == {t.name for t in app.list_tools()}


# --- doctor ----------------------------------------------------------------


def test_doctor_exits_zero_on_populated_app(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "doc" in out.lower() or "tool" in out.lower()


def test_doctor_exits_zero_on_empty_app(capsys: pytest.CaptureFixture[str]) -> None:
    a = App(name="empty", version="0.1")
    rc = run_cli(a, ["doctor"])
    assert rc == 0


# --- unknown verb --------------------------------------------------------


def test_unknown_verb_exits_nonzero(app: App) -> None:
    rc = run_cli(app, ["bogus"])
    assert rc != 0


# --- bool-annotated params use BooleanOptionalAction ----------------------


def test_bool_param_true_default_with_no_flag(capsys) -> None:
    """bool param with default=True: --no-verbose sets to False, no flag keeps True."""

    app = App(name="t", version="1.0")

    @app.tool
    def t(verbose: bool = True) -> str:
        return str(verbose)

    # --no-verbose should give False
    rc = run_cli(app, ["t", "--no-verbose"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "False" in out

    # No flag should keep default True
    rc = run_cli(app, ["t"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "True" in out


def test_bool_param_false_default_with_flag(capsys) -> None:
    """bool param with default=False: --q sets to True."""

    app = App(name="t", version="1.0")

    @app.tool
    def u(q: bool = False) -> str:
        return str(q)

    # --q should give True
    rc = run_cli(app, ["u", "--q"])
    assert rc == 0
    assert "True" in capsys.readouterr().out


# --- make_cli returns parser ---------------------------------------------


def test_make_cli_returns_parser(app: App):
    parser = make_cli(app)
    assert parser is not None
    # It should have a parse_args method (argparse.ArgumentParser)
    assert hasattr(parser, "parse_args")


# --- structured parse-time errors ----------------------------------------


def test_unknown_verb_json_error(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown verb with --json emits structured JSON on stderr, clean stdout, exit 1."""
    rc = run_cli(app, ["nosuchverb", "--json"])
    assert rc == 1
    stdout, stderr = capsys.readouterr()
    assert stdout == "", f"stdout should be clean, got: {stdout!r}"
    assert stderr != "", "stderr should have content"
    payload = json.loads(stderr)
    assert "code" in payload
    assert "message" in payload
    assert "remediation" in payload
    assert payload["code"] == 1


def test_unknown_verb_text_error(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown verb without --json emits 'error:'/'hint:' lines on stderr."""
    rc = run_cli(app, ["nosuchverb"])
    assert rc == 1
    stdout, stderr = capsys.readouterr()
    assert stdout == "", f"stdout should be clean, got: {stdout!r}"
    assert "error:" in stderr, f"stderr should contain 'error:', got: {stderr!r}"
    assert "hint:" in stderr, f"stderr should contain 'hint:', got: {stderr!r}"


def test_missing_required_positional_json_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Missing required positional with --json emits structured JSON on stderr."""

    a = App(name="t", version="1.0")

    @a.tool
    def needs_arg(path: str) -> str:
        return path

    rc = run_cli(a, ["needs_arg", "--json"])
    assert rc == 1
    stdout, stderr = capsys.readouterr()
    assert stdout == "", f"stdout should be clean, got: {stdout!r}"
    assert stderr != "", "stderr should have content"
    payload = json.loads(stderr)
    assert "code" in payload
    assert "message" in payload
    assert "remediation" in payload
    assert payload["code"] == 1


def test_missing_required_positional_text_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Missing required positional without --json emits 'error:'/'hint:' lines."""

    a = App(name="t", version="1.0")

    @a.tool
    def needs_arg(path: str) -> str:
        return path

    rc = run_cli(a, ["needs_arg"])
    assert rc == 1
    stdout, stderr = capsys.readouterr()
    assert stdout == "", f"stdout should be clean, got: {stdout!r}"
    assert "error:" in stderr, f"stderr should contain 'error:', got: {stderr!r}"
    assert "hint:" in stderr, f"stderr should contain 'hint:', got: {stderr!r}"


# --- choices flags: parse-time rejection through the structured-error path ---


def _checksum_app() -> App:
    """An App with a ``--algo`` choices flag (the colleague call site shape)."""
    a = App(name="t", version="1.0")

    @a.tool(flags=(Flag(names=("--algo",), choices=("sha256", "md5"), default="sha256"),))
    def checksum(target: str) -> str:
        return f"checked {target}"

    return a


def test_choices_flag_accepts_in_set_value(capsys) -> None:
    """An in-set ``--algo`` value parses and the verb runs."""
    rc = run_cli(_checksum_app(), ["checksum", "x", "--algo", "md5"])
    assert rc == 0
    out, _ = capsys.readouterr()
    assert "checked x" in out


def test_choices_flag_rejects_out_of_set_value_text(capsys) -> None:
    """An out-of-set ``--algo`` is rejected at parse time via the structured path."""
    rc = run_cli(_checksum_app(), ["checksum", "x", "--algo", "crc32"])
    assert rc == 1
    stdout, stderr = capsys.readouterr()
    assert stdout == "", f"stdout should be clean, got: {stdout!r}"
    assert "error:" in stderr
    assert "hint:" in stderr


def test_choices_flag_rejects_out_of_set_value_json(capsys) -> None:
    """The same rejection renders as the structured JSON error under --json."""
    rc = run_cli(_checksum_app(), ["checksum", "x", "--algo", "crc32", "--json"])
    assert rc == 1
    stdout, stderr = capsys.readouterr()
    assert stdout == "", f"stdout should be clean, got: {stdout!r}"
    payload = json.loads(stderr)
    assert payload["code"] == 1
    assert "message" in payload
    assert "remediation" in payload
