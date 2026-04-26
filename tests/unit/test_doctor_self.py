"""Tests for the in-process self-doctor checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from afi import __version__
from afi.doctor import _self_checks as sc
from afi.doctor import is_healthy, run_self_diagnosis


def test_run_self_diagnosis_against_live_repo() -> None:
    """The end-to-end self-doctor must report ``healthy=True`` against the source tree.

    This duplicates ``tests/test_self_doctor.py``'s in-process check at
    the unit level so that breaking surface coherence (a verb added
    without a learn / explain entry) shows up in fast feedback.
    """
    diagnosis = run_self_diagnosis()
    failed = [r for r in diagnosis.checks if not r.passed and r.severity == "error"]
    assert diagnosis.healthy, "\n".join(
        f"[{r.bundle}] {r.check}: {r.evidence} — {r.remediation}" for r in failed
    )


def test_is_healthy_only_considers_error_severity() -> None:
    from afi.rubric._types import CheckResult

    warn_only = [
        CheckResult("self", "x", False, "warn", "...", remediation="..."),
    ]
    error = [
        CheckResult("self", "x", False, "error", "...", remediation="..."),
    ]
    assert is_healthy(warn_only) is True
    assert is_healthy(error) is False


def test_version_consistency_passes_when_pyproject_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pp = tmp_path / "pyproject.toml"
    pp.write_text(f'[project]\nname = "afi-cli"\nversion = "{__version__}"\n')
    monkeypatch.setattr(sc, "_find_repo_root", lambda: tmp_path)
    result = sc._check_version_consistency()
    assert result.passed
    assert result.severity == "info"


def test_version_consistency_fails_on_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pp = tmp_path / "pyproject.toml"
    pp.write_text('[project]\nname = "afi-cli"\nversion = "0.0.99-not-real"\n')
    monkeypatch.setattr(sc, "_find_repo_root", lambda: tmp_path)
    result = sc._check_version_consistency()
    assert not result.passed
    assert result.severity == "error"
    assert "pyproject" in result.evidence


def test_version_consistency_info_when_no_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sc, "_find_repo_root", lambda: None)
    result = sc._check_version_consistency()
    assert result.passed
    assert result.severity == "info"


def test_changelog_entry_passes_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "CHANGELOG.md").write_text(f"# CHANGELOG\n\n## [{__version__}] - 2026-04-26\n")
    monkeypatch.setattr(sc, "_find_repo_root", lambda: tmp_path)
    assert sc._check_changelog_entry().passed


def test_changelog_entry_warns_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "CHANGELOG.md").write_text("# CHANGELOG\n\n## [0.0.99] - 2026-04-26\n")
    monkeypatch.setattr(sc, "_find_repo_root", lambda: tmp_path)
    result = sc._check_changelog_entry()
    assert not result.passed
    assert result.severity == "warn"


def test_surface_coherence_learn_against_live_parser() -> None:
    """Live argparse vs. live learn payload — every leaf must be mentioned."""
    result = sc._check_surface_coherence_learn()
    assert result.passed, result.evidence


def test_surface_coherence_explain_against_live_catalog() -> None:
    result = sc._check_surface_coherence_explain()
    assert result.passed, result.evidence


def test_reference_tree_present_against_real_install() -> None:
    result = sc._check_reference_tree_present()
    assert result.passed, result.evidence


def test_rubric_modules_loadable() -> None:
    result = sc._check_rubric_modules_loadable()
    assert result.passed, result.evidence


def test_argparse_leaf_paths_excludes_nouns() -> None:
    """Nouns like ``cli`` are not leaves; their nested verbs are."""
    from afi.cli import _build_parser

    parser = _build_parser()
    leaves = sc._argparse_leaf_paths(parser)
    leaves_set = {tuple(p) for p in leaves}
    # ``cli`` alone is a noun, must not appear; its verbs must.
    assert ("cli",) not in leaves_set
    assert ("cli", "doctor") in leaves_set
    assert ("doctor",) in leaves_set
    assert ("learn",) in leaves_set


def test_doctor_json_payload_has_bundle_seven_required_keys(tmp_path: Path) -> None:
    """The diagnosis emitted by `afi doctor --json` must satisfy bundle 7's contract.

    Renders the doctor verb's JSON shape directly from a fresh diagnosis
    so we don't depend on subprocess invocation; the rendering function
    lives in ``afi.cli._commands.doctor``.
    """
    from afi.cli._commands.doctor import _check_to_dict, _summarize
    from afi.doctor import is_healthy

    diagnosis = run_self_diagnosis()
    payload = {
        "tool": "afi",
        "subject": diagnosis.subject,
        "healthy": is_healthy(diagnosis.checks),
        "checks": [_check_to_dict(r) for r in diagnosis.checks],
        "summary": _summarize(diagnosis.checks),
    }
    # Round-trip through JSON to confirm serialisability.
    payload = json.loads(json.dumps(payload))

    # Bundle 7 top-level requirements.
    assert isinstance(payload["healthy"], bool)
    assert isinstance(payload["checks"], list)
    # Bundle 7 per-check requirements.
    for entry in payload["checks"]:
        for key in ("id", "passed", "severity", "message"):
            assert key in entry, f"check entry missing {key}: {entry}"
    # Failed checks must carry a remediation.
    for entry in payload["checks"]:
        if not entry["passed"]:
            assert entry.get("remediation"), f"failed check has no remediation: {entry}"
