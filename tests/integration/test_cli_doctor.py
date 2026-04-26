"""End-to-end tests for the ``afi doctor`` and ``afi cli doctor`` verbs.

These drive afi as a subprocess so we exercise the full argparse +
dispatch + doctor + rubric path in a real process.
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 - integration tests need subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_afi(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "afi", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_global_doctor_no_path_runs_self_diagnosis() -> None:
    """`afi doctor` with no path runs the in-process self-doctor."""
    result = _run_afi("doctor", cwd=REPO_ROOT)
    assert result.returncode == 0, f"self-doctor failed:\n{result.stderr}"
    # Self-doctor uses the [self] bundle name.
    assert "[self]" in result.stdout
    assert "healthy:" in result.stderr


def test_global_doctor_json_shape_satisfies_bundle_seven() -> None:
    result = _run_afi("doctor", "--json", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "afi"
    assert payload["healthy"] is True
    assert isinstance(payload["checks"], list)
    # Every check has the bundle-7-required keys.
    for entry in payload["checks"]:
        for key in ("id", "passed", "severity", "message"):
            assert key in entry, f"check missing {key}: {entry}"


def test_global_doctor_with_path_forwards_to_target_audit() -> None:
    """`afi doctor <repo>` should produce the same shape as `afi cli doctor <repo>`."""
    result = _run_afi("doctor", str(REPO_ROOT), "--json", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "afi"
    bundles = {c["bundle"] for c in payload["checks"]}
    # Target audit hits the rubric, not the self-doctor's "self" bundle.
    assert "doctor" in bundles
    assert "structure" in bundles
    assert "self" not in bundles


def test_cli_doctor_self_passes() -> None:
    result = _run_afi("cli", "doctor", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, f"cli doctor self failed:\n{result.stderr}"


def test_cli_doctor_dry_run_lists_no_fixes_when_healthy() -> None:
    """When the target is healthy, `--dry-run` says so on stderr."""
    result = _run_afi("cli", "doctor", str(REPO_ROOT), "--dry-run", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "no auto-fixable failures" in result.stderr


def test_cli_doctor_fix_no_op_when_healthy() -> None:
    """`--fix` against a healthy target is a no-op and exits 0."""
    result = _run_afi("cli", "doctor", str(REPO_ROOT), "--fix", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr


def test_global_doctor_fix_emits_self_doctor_diagnostic() -> None:
    """`afi doctor --fix` (no path) emits a "no-op on self-doctor" diagnostic.

    Self-doctor is read-only; the diagnostic is part of the contract so
    users learn where ``--fix`` does apply (target audits).
    """
    result = _run_afi("doctor", "--fix", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "self-doctor" in result.stderr.lower()
