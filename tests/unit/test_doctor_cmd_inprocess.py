"""In-process tests for the ``doctor`` / ``cli doctor`` / ``cli cite`` handlers.

The integration suite drives these verbs as subprocesses (``python -m agentfront``),
which exercises the real entry point but is invisible to coverage (it runs in a
child process). These tests call :func:`agentfront.cli.main` in-process so the
handler dispatch, target resolution, and error/remediation paths are measured —
the same code, observed from the parent process.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentfront.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# --- cheap resolution / error paths (no subprocess) ------------------------


def test_doctor_path_without_pyproject_is_user_error(tmp_path: Path) -> None:
    rc = main(["doctor", str(tmp_path)])
    assert rc == 1  # _resolve_tool_name raises AfiError → EXIT_USER_ERROR


def test_doctor_package_and_path_mutually_exclusive(tmp_path: Path) -> None:
    rc = main(["doctor", "--package", "agentfront", str(tmp_path)])
    assert rc == 1


def test_doctor_unknown_package_is_user_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["doctor", "--package", "definitely-not-a-package-xyz"])
    assert rc == 1
    assert "hint:" in capsys.readouterr().err


def test_cli_doctor_invalid_toml_is_user_error(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("not valid toml [[[[")
    rc = main(["cli", "doctor", str(tmp_path)])
    assert rc == 1


def test_cli_doctor_pyproject_without_scripts_is_user_error(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.1"\n')
    rc = main(["cli", "doctor", str(tmp_path)])
    assert rc == 1


def test_cli_doctor_no_args_audits_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # No path + no --package → audits the current working directory.
    monkeypatch.chdir(tmp_path)
    rc = main(["cli", "doctor"])  # cwd has no pyproject → user error
    assert rc == 1


def test_cli_verify_deprecated_forwards(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cli", "verify", str(tmp_path)])
    assert rc == 1  # forwards to cli doctor; tmp has no pyproject
    assert "deprecated" in capsys.readouterr().err.lower()


# --- cite (in-process) -----------------------------------------------------


def test_cli_cite_writes_dotteken(tmp_path: Path) -> None:
    rc = main(["cli", "cite", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / ".agentfront" / "reference" / "python-cli" / "AGENT.md").is_file()


# --- real audit happy paths (spawn target probes; cover orchestration) -----


def test_doctor_self_json_in_process(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["doctor", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "agentfront"
    assert payload["healthy"] is True


def test_cli_doctor_repo_json_in_process(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cli", "doctor", str(REPO_ROOT), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "agentfront"
    assert set(payload.keys()) == {"tool", "subject", "healthy", "checks", "summary"}


def test_cli_doctor_dry_run_repo(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cli", "doctor", str(REPO_ROOT), "--dry-run", "--json"])
    assert rc == 0
    assert "dry-run" in capsys.readouterr().err.lower()


def test_doctor_package_teken_in_process(capsys: pytest.CaptureFixture[str]) -> None:
    # agentfront is editable-installed in the dev/CI venv; resolves its source root
    # via PEP 610 direct_url and audits it.
    rc = main(["doctor", "--package", "agentfront", "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["tool"] == "agentfront"


def test_doctor_self_text_mode_headline(capsys: pytest.CaptureFixture[str]) -> None:
    # Text mode (no --json) exercises the body renderer + self headline.
    rc = main(["doctor"])
    assert rc == 0
    assert "self-check passed" in capsys.readouterr().err


def test_cli_doctor_repo_text_mode_headline(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cli", "doctor", str(REPO_ROOT)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "passed" in captured.err  # target headline summarises pass/fail counts
