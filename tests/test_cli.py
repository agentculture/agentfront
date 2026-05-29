"""Smoke tests for the agentfront CLI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest

from agentfront import __version__
from agentfront.cli import main, main_teken_alias


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage: agentfront" in out


def test_learn_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Agent First Interface" in out
    assert "CLI" in out and "MCP" in out and "HTTP" in out


def test_python_dash_m_invocation() -> None:
    """`python -m agentfront --version` exits 0 and prints the version."""
    result = subprocess.run(
        [sys.executable, "-m", "agentfront", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout


def test_afi_alias_warns_on_stderr_and_forwards(capsys: pytest.CaptureFixture[str]) -> None:
    """The deprecated ``teken`` alias forwards to ``main`` and warns on stderr only.

    The note MUST stay off stdout so ``--json`` consumers of the alias keep
    getting clean, parseable output.
    """
    with pytest.raises(SystemExit) as exc:
        main_teken_alias(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out  # forwarded command output
    assert "deprecated" not in captured.out.lower()  # stdout stays clean
    assert "deprecated" in captured.err.lower()
    assert "teken" in captured.err and "agentfront" in captured.err
