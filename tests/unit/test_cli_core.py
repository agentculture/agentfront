"""Tests for :mod:`agentfront._cli_core` — the shared CLI dispatch machinery."""

from __future__ import annotations

import argparse
import importlib
import json
import sys

import pytest

from agentfront import _cli_core
from agentfront._cli_core import (
    StructuredArgumentParser,
    argv_has_json,
    dispatch,
)
from agentfront.errors import AgentfrontError

# ── argv_has_json ──────────────────────────────────────────────────────────


def test_argv_has_json_detects_flag() -> None:
    assert argv_has_json(["--json"]) is True
    assert argv_has_json(["--json=1"]) is True
    assert argv_has_json(["--json", "foo"]) is True


def test_argv_has_json_absent() -> None:
    assert argv_has_json(["--help"]) is False
    assert argv_has_json([]) is False
    assert argv_has_json(None) is False  # uses sys.argv[1:] which won't have --json in tests


# ── StructuredArgumentParser ───────────────────────────────────────────────


def _make_parser(**kwargs) -> StructuredArgumentParser:
    return StructuredArgumentParser(prog="testprog", **kwargs)


def test_parser_error_emits_structured_text(capsys) -> None:
    """Unknown arg → error:/hint: lines on stderr, nonzero exit."""
    parser = _make_parser()
    parser.add_argument("--known")
    StructuredArgumentParser._json_hint = False

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--unknown"])

    assert exc.value.code != 0
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "hint:" in captured.err
    assert captured.out == ""


def test_parser_error_emits_json_when_json_hint(capsys) -> None:
    """--json present → JSON object on stderr."""
    parser = _make_parser()
    parser.add_argument("--known")
    StructuredArgumentParser._json_hint = True

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--unknown"])

    assert exc.value.code != 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.err.strip())
    assert "code" in parsed
    assert "message" in parsed
    assert "remediation" in parsed
    assert captured.out == ""


def test_parser_error_no_json_when_not_hint(capsys) -> None:
    """Without --json, output is error:/hint: lines, not JSON."""
    parser = _make_parser()
    parser.add_argument("--known")
    StructuredArgumentParser._json_hint = False

    with pytest.raises(SystemExit):
        parser.parse_args(["--unknown"])

    captured = capsys.readouterr()
    # Should NOT be valid JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.err.strip())


# ── dispatch ───────────────────────────────────────────────────────────────


def _handler_raising(err: Exception):
    def handler(_args: argparse.Namespace) -> int:
        raise err

    return handler


def test_dispatch_catches_agentfront_error(capsys) -> None:
    err = AgentfrontError(code=2, message="env broken", remediation="run uv sync")
    args = argparse.Namespace(func=_handler_raising(err), json=False)

    rc = dispatch(args, issues_url="https://example.com/issues", json_mode=False)

    assert rc == 2
    captured = capsys.readouterr()
    assert "error: env broken" in captured.err
    assert "hint: run uv sync" in captured.err
    assert captured.out == ""


def test_dispatch_wraps_bare_exception(capsys) -> None:
    """Bare Exception → structured error + nonzero exit, NO traceback."""
    args = argparse.Namespace(
        func=_handler_raising(RuntimeError("kaboom")),
        json=False,
    )

    rc = dispatch(args, issues_url="https://example.com/issues", json_mode=False)

    assert rc != 0
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "kaboom" in captured.err
    assert "hint:" in captured.err
    assert "Traceback" not in captured.err


def test_dispatch_keyboardinterrupt_exits_130() -> None:
    """KeyboardInterrupt → SystemExit(130)."""

    def raise_kbd(_args: argparse.Namespace) -> int:
        raise KeyboardInterrupt

    args = argparse.Namespace(func=raise_kbd, json=False)

    with pytest.raises(SystemExit) as exc:
        dispatch(args, issues_url="https://example.com/issues", json_mode=False)

    assert exc.value.code == 130


def test_dispatch_json_mode_structured_error(capsys) -> None:
    err = AgentfrontError(code=1, message="bad", remediation="fix")
    args = argparse.Namespace(func=_handler_raising(err), json=True)

    rc = dispatch(args, issues_url="https://example.com/issues", json_mode=True)

    assert rc == 1
    captured = capsys.readouterr()
    parsed = json.loads(captured.err.strip())
    assert parsed == {"code": 1, "message": "bad", "remediation": "fix"}
    assert captured.out == ""


def test_dispatch_returns_handler_return_code_on_success() -> None:
    def ok(_args: argparse.Namespace) -> int:
        return 0

    args = argparse.Namespace(func=ok, json=False)
    assert dispatch(args, issues_url="https://example.com/issues", json_mode=False) == 0


def test_dispatch_returns_none_as_zero() -> None:
    def ok(_args: argparse.Namespace) -> None:
        return None

    args = argparse.Namespace(func=ok, json=False)
    assert dispatch(args, issues_url="https://example.com/issues", json_mode=False) == 0


# ── import graph ───────────────────────────────────────────────────────────


def test_cli_core_no_brand_import() -> None:
    """_cli_core must NOT import agentfront._brand."""
    mod = importlib.import_module("agentfront._cli_core")
    source = inspect_source(mod)
    assert "_brand" not in source, "_cli_core must not reference _brand"


def test_cli_core_imports_only_stdlib_and_agentfront() -> None:
    """_cli_core imports must be stdlib or agentfront (no third-party)."""
    mod = importlib.import_module("agentfront._cli_core")
    source = inspect_source(mod)
    # Check there's no import of third-party packages
    # We allow: argparse, sys, typing, agentfront
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            # Extract the module being imported
            if stripped.startswith("from "):
                parts = stripped.split()
                mod_name = parts[1].split(".")[0]
            else:
                parts = stripped.split()
                mod_name = parts[1].split(".")[0]
            # Allow stdlib and agentfront
            allowed = {"argparse", "sys", "typing", "agentfront", "__future__"}
            assert mod_name in allowed, f"Unexpected import: {mod_name}"


def inspect_source(mod) -> str:
    """Get source of a module for inspection."""
    import inspect

    return inspect.getsource(mod)
