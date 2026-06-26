"""End-to-end tests for the ``agentfront doctor`` and ``agentfront cli doctor`` verbs.

These drive agentfront as a subprocess so we exercise the full argparse +
dispatch + doctor + rubric path in a real process.
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 - integration tests need subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_agentfront(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "agentfront", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_global_doctor_no_path_runs_self_diagnosis() -> None:
    """`agentfront doctor` with no path runs the in-process self-doctor."""
    result = _run_agentfront("doctor", cwd=REPO_ROOT)
    assert result.returncode == 0, f"self-doctor failed:\n{result.stderr}"
    # Self-doctor uses the [self] bundle name.
    assert "[self]" in result.stdout
    # Self-mode headline is scoped (issue #13) — bare `healthy:` is reserved
    # for target audits to avoid the "green light is over-confident" framing.
    assert "structural self-check passed" in result.stderr
    assert "Run 'agentfront doctor" in result.stderr


def test_global_doctor_target_headline_unchanged() -> None:
    """Target audits keep the v0.5 `healthy:` headline.

    The self-mode rephrasing in issue #13 must not leak into the target
    audit path — agents that already parse the `healthy:` headline keep
    working unchanged.
    """
    result = _run_agentfront("doctor", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "healthy:" in result.stderr
    assert "structural self-check" not in result.stderr


def test_global_doctor_json_shape_satisfies_bundle_seven() -> None:
    result = _run_agentfront("doctor", "--json", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "agentfront"
    assert payload["healthy"] is True
    assert isinstance(payload["checks"], list)
    # Every check has the bundle-7-required keys.
    for entry in payload["checks"]:
        for key in ("id", "passed", "severity", "message"):
            assert key in entry, f"check missing {key}: {entry}"


def test_global_doctor_with_path_forwards_to_target_audit() -> None:
    """`agentfront doctor <repo>` should produce the same shape as
    `agentfront cli doctor <repo>`."""
    result = _run_agentfront("doctor", str(REPO_ROOT), "--json", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "agentfront"
    bundles = {c["bundle"] for c in payload["checks"]}
    # Target audit hits the rubric, not the self-doctor's "self" bundle.
    assert "doctor" in bundles
    assert "structure" in bundles
    assert "self" not in bundles


def test_cli_doctor_self_passes() -> None:
    result = _run_agentfront("cli", "doctor", str(REPO_ROOT), cwd=REPO_ROOT)
    assert result.returncode == 0, f"cli doctor self failed:\n{result.stderr}"


def test_cli_doctor_dry_run_lists_no_fixes_when_healthy() -> None:
    """When the target is healthy, `--dry-run` says so on stderr."""
    result = _run_agentfront("cli", "doctor", str(REPO_ROOT), "--dry-run", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "no auto-fixable failures" in result.stderr


def test_cli_doctor_fix_no_op_when_healthy() -> None:
    """`--fix` against a healthy target is a no-op and exits 0."""
    result = _run_agentfront("cli", "doctor", str(REPO_ROOT), "--fix", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr


def test_global_doctor_fix_emits_self_doctor_diagnostic() -> None:
    """`agentfront doctor --fix` (no path) emits a "no-op on self-doctor" diagnostic.

    Self-doctor is read-only; the diagnostic is part of the contract so
    users learn where ``--fix`` does apply (target audits).
    """
    result = _run_agentfront("doctor", "--fix", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "self-doctor" in result.stderr.lower()


def test_doctor_fix_and_dry_run_are_mutually_exclusive() -> None:
    """`--fix` and `--dry-run` together must fail at parse time, not silently.

    `--dry-run` is a preview of what `--fix` would do; combining them is
    meaningless. argparse's mutually-exclusive group enforces it so the
    contract is unambiguous (and no traceback leaks through).
    """
    result = _run_agentfront("doctor", "--fix", "--dry-run", cwd=REPO_ROOT)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_cli_doctor_fix_and_dry_run_are_mutually_exclusive() -> None:
    result = _run_agentfront("cli", "doctor", str(REPO_ROOT), "--fix", "--dry-run", cwd=REPO_ROOT)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_doctor_unknown_path_gives_helpful_error() -> None:
    """A non-project path surfaces both escape hatches in the remediation.

    Reproduces the agent-experience trip-up from issue #13: someone types
    `agentfront doctor culture` from outside that repo. Today's error names the
    wrong layer (a deep `culture/culture/pyproject.toml`); the new error
    names both `agentfront doctor .` and `--package` so the agent learns the
    contract from the diagnostic.
    """
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_agentfront("doctor", "culture", cwd=Path(tmp))
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "is not a project root" in result.stderr
    assert "agentfront doctor /path/to/" in result.stderr
    assert "--package" in result.stderr


def test_doctor_package_resolves_editable_install() -> None:
    """`agentfront doctor --package agentfront` from anywhere audits the repo.

    agentfront is editable-installed in the dev environment (and CI runs
    `uv sync` before tests), so this exercises the PEP 610 path
    end-to-end.
    """
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_agentfront("doctor", "--package", "agentfront", "--json", cwd=Path(tmp))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "agentfront"
    # The audit should land at the agentfront source root, not at site-packages.
    assert Path(payload["subject"]).resolve() == REPO_ROOT.resolve()


def test_doctor_path_and_package_mutually_exclusive() -> None:
    """Passing both `<path>` and `--package` errors at the policy layer.

    Argparse alone can't reject this (path positional + optional flag
    can't share a mutually-exclusive group cleanly), so the handler
    raises ``AgentfrontError``. The contract is still: non-zero exit, no
    traceback, named in the diagnostic.
    """
    result = _run_agentfront("doctor", ".", "--package", "agentfront", cwd=REPO_ROOT)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "mutually exclusive" in result.stderr


def test_doctor_unknown_package_gives_helpful_error() -> None:
    """`agentfront doctor --package <unknown>` names the dist and points at next steps."""
    result = _run_agentfront("doctor", "--package", "definitely-not-a-package", cwd=REPO_ROOT)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "no installed distribution named 'definitely-not-a-package'" in result.stderr
    assert "uv pip install -e" in result.stderr


def test_cli_doctor_package_flag_works() -> None:
    """`agentfront cli doctor --package agentfront` mirrors the global verb."""
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_agentfront(
            "cli", "doctor", "--package", "agentfront", "--json", cwd=Path(tmp)
        )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert Path(payload["subject"]).resolve() == REPO_ROOT.resolve()


def test_cli_doctor_path_and_package_mutually_exclusive() -> None:
    result = _run_agentfront("cli", "doctor", ".", "--package", "agentfront", cwd=REPO_ROOT)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "mutually exclusive" in result.stderr


def test_cli_doctor_unknown_path_names_the_cli_verb_in_remediation() -> None:
    """`agentfront cli doctor /bad` must point at `agentfront cli doctor`, not `agentfront doctor`.

    Regression for the Copilot review on PR #14: the diagnostic
    remediation for a non-project-root path used to hardcode the global
    verb (``agentfront doctor ...``), which misleads agents that invoked the
    noun-scoped form.
    """
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_agentfront("cli", "doctor", "culture", cwd=Path(tmp))
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "is not a project root" in result.stderr
    assert "agentfront cli doctor" in result.stderr


def test_cli_doctor_unknown_package_names_the_cli_verb_in_remediation() -> None:
    """`agentfront cli doctor --package <unknown>` remediation names the cli verb.

    Same threading as the path branch: the package-resolver remediations
    must follow the verb the user invoked.
    """
    result = _run_agentfront(
        "cli", "doctor", "--package", "definitely-not-a-package", cwd=REPO_ROOT
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "agentfront cli doctor /path/to/" in result.stderr
