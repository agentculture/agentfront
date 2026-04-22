"""Smoke tests for the afi CLI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest

from afi import __version__
from afi.cli import main


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
    assert "usage: afi" in out


def test_learn_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Agent First Interface" in out
    assert "CLI" in out and "MCP" in out and "HTTP" in out


def test_python_dash_m_invocation() -> None:
    """`python -m afi --version` exits 0 and prints the version."""
    result = subprocess.run(
        [sys.executable, "-m", "afi", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
