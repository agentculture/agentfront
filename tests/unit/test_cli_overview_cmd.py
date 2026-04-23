"""CLI smoke tests for ``afi cli overview`` and ``afi overview``.

Drives afi in-process via :func:`afi.cli.main` (fast, captured via capsys).
Subprocess-level coverage of the same surface lives in
``tests/integration/test_cli_commands.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from afi.cli import main


def test_cli_overview_zero_target_renders(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cli", "overview"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "afi default template" in out
    # Tokens are surfaced as guidance for integrating agents.
    assert "{{slug}}" in out


def test_cli_overview_on_real_target_reports_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Inspect afi itself — rich target with all four sections.
    rc = main(["cli", "overview", str(Path.cwd())])
    out = capsys.readouterr().out
    assert rc == 0
    for heading in ("Project root", "Command surface", "Agent-first triple", "Rubric posture"):
        assert heading in out


def test_cli_overview_json_mode_is_parseable(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cli", "overview", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["subject"] == "cli"
    assert isinstance(payload["sections"], list)


def test_top_level_overview_delegates_and_annotates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["overview"])
    out = capsys.readouterr().out
    assert rc == 0
    # Subject is "all" (the rollup), but currently only cli is implemented.
    assert "overview: all" in out
    assert "mcp and site surfaces" in out


def test_top_level_overview_json_subject_is_all(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["overview", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["subject"] == "all"


def test_cli_overview_missing_path_graceful(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nonexistent-subdir"
    rc = main(["cli", "overview", str(missing)])
    out = capsys.readouterr().out
    # Read-only verbs fall back and succeed; they do NOT hard-fail.
    assert rc == 0
    assert "afi default template" in out
