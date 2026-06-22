"""End-to-end tests for the ``agentfront cli {doctor,verify,overview}`` surface.

These drive agentfront as a subprocess (via ``python -m agentfront``) to exercise the full
argparse + dispatch + rubric code path end-to-end — not via
:func:`agentfront.cli.main`. They do NOT test the built wheel's packaging: the
subprocess imports from the source tree directly.
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 - integration tests need subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_agentfront(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "agentfront", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_doctor_on_non_cli_dir_fails_on_structure(tmp_path: Path) -> None:
    """An empty target is not a CLI project — doctor bails at structure
    (no pyproject.toml) rather than crashing."""
    result = _run_agentfront("cli", "doctor", str(tmp_path), cwd=tmp_path)

    assert result.returncode != 0
    assert "pyproject.toml" in (result.stderr + result.stdout).lower()


def test_doctor_self_passes() -> None:
    """`agentfront cli doctor .` on the agentfront repo passes every bundle."""
    result = _run_agentfront("cli", "doctor", str(REPO_ROOT), cwd=REPO_ROOT)

    assert (
        result.returncode == 0
    ), f"self-doctor failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_doctor_json_mode_emits_structured_report() -> None:
    result = _run_agentfront("cli", "doctor", ".", "--json", cwd=REPO_ROOT)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "agentfront"
    assert payload["healthy"] is True
    assert payload["summary"]["errors"] == 0
    assert payload["summary"]["total"] > 0
    bundles = {c["bundle"] for c in payload["checks"]}
    assert bundles == {
        "structure",
        "learnability",
        "json",
        "errors",
        "explain",
        "overview",
        "doctor",
    }


def test_verify_alias_still_works_with_deprecation_diagnostic() -> None:
    """`agentfront cli verify` is a deprecated alias for `cli doctor`. It must keep
    working for one minor cycle (removed in v0.6.0) and emit a deprecation
    diagnostic to stderr so callers know to migrate.
    """
    result = _run_agentfront("cli", "verify", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, f"verify alias broke:\nstderr:\n{result.stderr}"
    assert "deprecated" in result.stderr.lower()


def test_bogus_verb_exits_with_hint() -> None:
    result = _run_agentfront("bogus-verb-zzz")

    assert result.returncode != 0
    assert "error:" in result.stderr
    assert "hint:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "path",
    [
        "agentfront",
        "learn",
        "explain",
        "overview",
        "doctor",
        "cli",
        "cli doctor",
        "cli verify",  # deprecated alias — entry still present for one cycle.
        "cli overview",
    ],
)
def test_every_registered_path_has_explain_entry(path: str) -> None:
    tokens = path.split()
    result = _run_agentfront("explain", *tokens)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("#")


# --- overview verb (new in v0.3) -----------------------------------------


def test_cli_overview_zero_target_renders_runtime_model() -> None:
    result = _run_agentfront("cli", "overview")
    assert result.returncode == 0, result.stderr
    assert "agentfront runtime model" in result.stdout
    # Zero-target describes the importable App, not a scaffolded tree.
    assert "from agentfront import App" in result.stdout


def test_cli_overview_on_self_shows_universals_context() -> None:
    result = _run_agentfront("cli", "overview", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "Project root" in result.stdout
    assert "Command surface" in result.stdout
    assert "Agent-first universals" in result.stdout


def test_cli_overview_json_mode_has_stable_keys() -> None:
    result = _run_agentfront("cli", "overview", "--json", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload.keys()) == {"subject", "path", "sections", "warnings", "notes"}
    assert payload["subject"] == "cli"


def test_top_level_overview_stub_works() -> None:
    result = _run_agentfront("overview")
    assert result.returncode == 0, result.stderr
    assert "overview: all" in result.stdout


def test_overview_is_graceful_on_missing_path(tmp_path: Path) -> None:
    # Read-only verb: falls back, does NOT hard-fail.
    missing = tmp_path / "does-not-exist"
    result = _run_agentfront("cli", "overview", str(missing))
    assert result.returncode == 0, result.stderr
    assert "agentfront runtime model" in result.stdout
