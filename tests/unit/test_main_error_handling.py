"""Tests that the dispatch layer catches errors and routes through emit_error."""

from __future__ import annotations

import argparse

import pytest

from agentfront.cli import _dispatch
from agentfront.cli._errors import AfiError


def _raising(err: Exception):
    def handler(_args: argparse.Namespace) -> int:
        raise err

    return handler


def test_dispatch_catches_afi_error_and_returns_its_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    err = AfiError(code=2, message="env broken", remediation="run uv sync")
    args = argparse.Namespace(command="fake", func=_raising(err), json=False)

    rc = _dispatch(args)

    assert rc == 2
    captured = capsys.readouterr()
    assert "error: env broken" in captured.err
    assert "hint: run uv sync" in captured.err
    assert captured.out == ""  # stdout stays clean on error


def test_dispatch_wraps_unknown_exceptions(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(command="fake", func=_raising(RuntimeError("kaboom")), json=False)

    rc = _dispatch(args)

    assert rc != 0
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "kaboom" in captured.err
    # Every error carries a remediation — even synthetic wrappers.
    assert "hint:" in captured.err
    # No traceback leak.
    assert "Traceback" not in captured.err


def test_dispatch_json_mode_emits_structured_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json

    err = AfiError(code=1, message="bad", remediation="fix")
    args = argparse.Namespace(command="fake", func=_raising(err), json=True)

    rc = _dispatch(args)

    assert rc == 1
    captured = capsys.readouterr()
    parsed = json.loads(captured.err.strip())
    assert parsed == {"code": 1, "message": "bad", "remediation": "fix"}
    assert captured.out == ""


def test_dispatch_returns_handler_return_code_on_success() -> None:
    def ok(_args: argparse.Namespace) -> int:
        return 0

    args = argparse.Namespace(command="fake", func=ok, json=False)
    assert _dispatch(args) == 0
