"""Tests for ``agentfront.testing.cli`` — the in-process CLI harness.

``run_cli`` wraps ``agentfront.cli_surface.run_cli`` and captures stdout/stderr
via ``contextlib.redirect_stdout``/``redirect_stderr`` so consumer test suites
get a frozen, inspectable result without shelling out to a subprocess.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess

import pytest

from agentfront import App
from agentfront.testing import CliResult, run_cli

# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def app() -> App:
    """A populated App with one doc and one tool, mirroring test_cli_surface.py."""
    a = App(name="mytool", version="1.0.0", description="A test tool")
    a.add_doc(slug="intro", title="Introduction", text="# Intro\nbody")

    @a.tool
    def search(query: str) -> str:
        """Search the corpus."""
        return query

    return a


# --- CliResult shape ---------------------------------------------------------


def test_cliresult_is_a_frozen_dataclass() -> None:
    assert dataclasses.is_dataclass(CliResult)
    result = CliResult(exit_code=0, stdout="out", stderr="err")
    assert result.exit_code == 0
    assert result.stdout == "out"
    assert result.stderr == "err"
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.exit_code = 1  # type: ignore[misc]


# --- run_cli captures output --------------------------------------------------


def test_run_cli_returns_cliresult_with_captured_stdout(app: App) -> None:
    result = run_cli(app, ["search", "hello"])
    assert isinstance(result, CliResult)
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.stderr == ""


def test_run_cli_captures_stderr_on_unknown_verb(app: App) -> None:
    result = run_cli(app, ["bogus"])
    assert result.exit_code != 0
    assert result.stdout == ""
    assert result.stderr != ""
    assert "error:" in result.stderr


def test_run_cli_json_error_payload_in_stderr(app: App) -> None:
    result = run_cli(app, ["bogus", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["code"] == 1
    assert "message" in payload
    assert "remediation" in payload


def test_run_cli_learn_json_matches_registry(app: App) -> None:
    result = run_cli(app, ["learn", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "mytool"
    doc_slugs = {d["slug"] for d in payload["docs"]}
    assert doc_slugs == {d.slug for d in app.list_docs()}


def test_run_cli_is_in_process_no_subprocess(monkeypatch: pytest.MonkeyPatch, app: App) -> None:
    """run_cli must not shell out — patching subprocess must not affect it."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("run_cli must not invoke subprocess")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)

    result = run_cli(app, ["search", "x"])
    assert result.exit_code == 0
    assert "x" in result.stdout


def test_run_cli_does_not_leak_to_real_stdout(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    """Captured output must not also land on the real stdout/stderr."""
    run_cli(app, ["search", "quiet"])
    leaked = capsys.readouterr()
    assert leaked.out == ""
    assert leaked.err == ""
