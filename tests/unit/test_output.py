"""Tests for :mod:`agentfront.cli._output`."""

from __future__ import annotations

import io
import json

from agentfront.cli._errors import AfiError
from agentfront.cli._output import emit_diagnostic, emit_error, emit_result


def test_emit_result_text_adds_newline() -> None:
    buf = io.StringIO()
    emit_result("hello", json_mode=False, stream=buf)
    assert buf.getvalue() == "hello\n"


def test_emit_result_text_preserves_existing_newline() -> None:
    buf = io.StringIO()
    emit_result("hello\n", json_mode=False, stream=buf)
    assert buf.getvalue() == "hello\n"


def test_emit_result_json_emits_parseable_json() -> None:
    buf = io.StringIO()
    emit_result({"a": 1, "b": [2, 3]}, json_mode=True, stream=buf)
    assert json.loads(buf.getvalue().strip()) == {"a": 1, "b": [2, 3]}


def test_emit_error_text_includes_error_and_hint_lines() -> None:
    buf = io.StringIO()
    emit_error(AfiError(1, "bad", "try fixing"), json_mode=False, stream=buf)
    out = buf.getvalue()
    assert "error: bad" in out
    assert "hint: try fixing" in out


def test_emit_error_text_without_remediation_has_no_hint_line() -> None:
    buf = io.StringIO()
    emit_error(AfiError(2, "env"), json_mode=False, stream=buf)
    out = buf.getvalue()
    assert "error: env" in out
    assert "hint:" not in out


def test_emit_error_json_is_structured() -> None:
    buf = io.StringIO()
    emit_error(AfiError(1, "bad", "fix"), json_mode=True, stream=buf)
    parsed = json.loads(buf.getvalue().strip())
    assert parsed == {"code": 1, "message": "bad", "remediation": "fix"}


def test_emit_diagnostic_writes_with_newline() -> None:
    buf = io.StringIO()
    emit_diagnostic("processing...", stream=buf)
    assert buf.getvalue() == "processing...\n"
