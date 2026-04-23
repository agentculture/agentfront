"""End-to-end tests for the ``afi cli {cite,verify,overview}`` surface.

These drive afi as a subprocess (via ``python -m afi``) to exercise the full
argparse + dispatch + cite + rubric code path end-to-end — not via
:func:`afi.cli.main`. They do NOT test the built wheel's packaging: the
subprocess imports from the source tree directly. Packaging-specific
coverage (that the reference tree ships in the wheel with `{{slug}}/`
directories intact) is done at release time via ``uv build`` and a manual
wheel-contents check, not here.
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 - integration tests need subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_afi(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "afi", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_cite_writes_reference_and_gitignore(tmp_path: Path) -> None:
    result = _run_afi("cli", "cite", str(tmp_path), cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    ref = tmp_path / ".afi" / "reference" / "python-cli"
    assert ref.is_dir()
    assert (ref / "AGENT.md").is_file()
    assert (ref / "MANIFEST.json").is_file()
    # Tokens must be literal.
    content = (ref / "{{slug}}" / "cli" / "__init__.py").read_text()
    assert "{{project_name}}" in content
    # gitignore updated.
    assert ".afi/" in (tmp_path / ".gitignore").read_text()


def test_cite_json_mode_emits_parseable_payload(tmp_path: Path) -> None:
    result = _run_afi("cli", "cite", str(tmp_path), "--json", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "out" in payload
    assert payload["gitignore_updated"] is True
    assert len(payload["next_steps"]) == 3


def test_cite_then_verify_round_trip(tmp_path: Path) -> None:
    """Citing into an empty dir makes the reference available, but the
    target project itself isn't a CLI — verify should fail on structure
    (no pyproject.toml). This guards against the reference being a hidden
    scaffolder: cite DOES NOT produce a working CLI; it produces a
    reference for an agent to apply.
    """
    _run_afi("cli", "cite", str(tmp_path), cwd=tmp_path)

    # The empty target is not a CLI project — verify should bail at structure.
    result = _run_afi("cli", "verify", str(tmp_path), cwd=tmp_path)

    assert result.returncode != 0
    assert "pyproject.toml" in (result.stderr + result.stdout).lower()


def test_verify_self_passes() -> None:
    """`afi cli verify .` on the afi-cli repo passes every bundle."""
    result = _run_afi("cli", "verify", str(REPO_ROOT), cwd=REPO_ROOT)

    assert (
        result.returncode == 0
    ), f"self-verify failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_verify_json_mode_emits_structured_report() -> None:
    result = _run_afi("cli", "verify", ".", "--json", cwd=REPO_ROOT)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "afi"
    assert payload["summary"]["errors"] == 0
    assert payload["summary"]["total"] > 0
    assert set(payload["summary"]["bundles"].keys()) == {
        "structure",
        "learnability",
        "json",
        "errors",
        "explain",
        "overview",
    }


def test_bogus_verb_exits_with_hint() -> None:
    result = _run_afi("bogus-verb-zzz")

    assert result.returncode != 0
    assert "error:" in result.stderr
    assert "hint:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "path",
    [
        "afi",
        "learn",
        "explain",
        "overview",
        "cli",
        "cli cite",
        "cli verify",
        "cli overview",
    ],
)
def test_every_registered_path_has_explain_entry(path: str) -> None:
    tokens = path.split()
    result = _run_afi("explain", *tokens)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("#")


# --- overview verb (new in v0.3) -----------------------------------------


def test_cli_overview_zero_target_renders_template() -> None:
    result = _run_afi("cli", "overview")
    assert result.returncode == 0, result.stderr
    assert "afi default template" in result.stdout
    # Tokens are literal in the scaffolded template — overview must surface them.
    assert "{{slug}}" in result.stdout


def test_cli_overview_on_self_shows_six_bundles_context() -> None:
    result = _run_afi("cli", "overview", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "Project root" in result.stdout
    assert "Command surface" in result.stdout
    assert "Agent-first triple" in result.stdout


def test_cli_overview_json_mode_has_stable_keys() -> None:
    result = _run_afi("cli", "overview", "--json", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload.keys()) == {"subject", "path", "sections", "warnings", "notes"}
    assert payload["subject"] == "cli"


def test_top_level_overview_stub_works() -> None:
    result = _run_afi("overview")
    assert result.returncode == 0, result.stderr
    assert "overview: all" in result.stdout


def test_overview_is_graceful_on_missing_path(tmp_path: Path) -> None:
    # Read-only verb: falls back, does NOT hard-fail.
    missing = tmp_path / "does-not-exist"
    result = _run_afi("cli", "overview", str(missing))
    assert result.returncode == 0, result.stderr
    assert "afi default template" in result.stdout
