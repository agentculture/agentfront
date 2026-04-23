"""Tests for rubric bundle 1: structure."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from afi.rubric._types import RunOutput, VerifyContext
from afi.rubric.checks import structure
from tests.unit._fake_runner import FakeRunner


def _ctx(tmp_path: Path, runner: FakeRunner | None = None) -> VerifyContext:
    return VerifyContext(tmp_path, "demo", runner or FakeRunner())


def _write_pyproject(tmp_path: Path, *, with_scripts: bool = True) -> None:
    body = '[project]\nname = "demo"\nversion = "0.0.1"\n'
    if with_scripts:
        body += '\n[project.scripts]\ndemo = "demo:main"\n'
    (tmp_path / "pyproject.toml").write_text(body)


def _non_probe_checks(results: list) -> list:
    """Drop main_entry_contract — tested separately since it shells out to uv."""
    return [r for r in results if r.check != "main_entry_contract"]


def test_all_pass_on_good_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_pyproject(tmp_path, with_scripts=True)
    (tmp_path / "tests").mkdir()
    # Stub the main-probe subprocess so this test stays hermetic — no uv,
    # no real target module required. The dedicated probe tests below
    # exercise the real subprocess wiring.
    monkeypatch.setattr(
        structure.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="ok\n", stderr=""),
    )
    runner = FakeRunner(responses={("--help",): RunOutput(0, "usage: demo ...\n", "")})
    results = structure.run(_ctx(tmp_path, runner))
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_missing_pyproject_fails(tmp_path: Path) -> None:
    results = structure.run(_ctx(tmp_path))
    by_name = {r.check: r for r in results}
    assert not by_name["pyproject_exists"].passed
    assert by_name["pyproject_exists"].severity == "error"


def test_missing_scripts_fails(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, with_scripts=False)
    results = structure.run(_ctx(tmp_path))
    by_name = {r.check: r for r in results}
    assert not by_name["project_scripts"].passed
    assert "add a [project.scripts] entry" in by_name["project_scripts"].remediation


def test_missing_tests_dir_warns(tmp_path: Path) -> None:
    _write_pyproject(tmp_path)
    results = _non_probe_checks(structure.run(_ctx(tmp_path)))
    by_name = {r.check: r for r in results}
    assert not by_name["tests_dir"].passed
    assert by_name["tests_dir"].severity == "warn"


def test_help_failure_is_error(tmp_path: Path) -> None:
    _write_pyproject(tmp_path)
    (tmp_path / "tests").mkdir()
    runner = FakeRunner(responses={("--help",): RunOutput(2, "", "nope")})
    results = _non_probe_checks(structure.run(_ctx(tmp_path, runner)))
    by_name = {r.check: r for r in results}
    assert not by_name["top_help_runs"].passed
    assert by_name["top_help_runs"].severity == "error"


# --------------------------------------------------------------------------
# main_entry_contract — new in v0.3
# --------------------------------------------------------------------------


def test_main_entry_contract_warns_when_scripts_missing(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, with_scripts=False)
    result = structure._check_main_entry_contract(_ctx(tmp_path))
    assert not result.passed
    assert result.severity == "warn"


def test_main_entry_contract_resolves_first_script(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.1"\n'
        '\n[project.scripts]\nfoo = "foo.cli:main"\n'
    )
    assert structure._resolve_entry_target(_ctx(tmp_path)) == ("foo.cli", "main")


def test_main_entry_contract_prefers_tool_name_match(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.1"\n'
        "\n[project.scripts]\n"
        'other = "other.cli:main"\n'
        'demo = "demo.cli:main"\n'
    )
    assert structure._resolve_entry_target(_ctx(tmp_path)) == ("demo.cli", "main")


def test_main_entry_contract_passes_when_probe_reports_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pyproject(tmp_path)
    monkeypatch.setattr(
        structure.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="ok\n", stderr=""),
    )
    result = structure._check_main_entry_contract(_ctx(tmp_path))
    assert result.passed
    assert "conforms" in result.evidence


def test_main_entry_contract_errors_when_probe_reports_bad_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pyproject(tmp_path)
    monkeypatch.setattr(
        structure.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            returncode=2,
            stdout="",
            stderr="bad_default: argv must default to None, got default=[]\n",
        ),
    )
    result = structure._check_main_entry_contract(_ctx(tmp_path))
    assert not result.passed
    assert result.severity == "error"
    assert "bad_default" in result.evidence
    assert "main(argv" in result.remediation


def test_resolve_entry_target_returns_none_when_matching_script_malformed(
    tmp_path: Path,
) -> None:
    """If ctx.tool_name has an entry but value lacks ``module:func`` shape,
    return None rather than silently falling back to a different script.

    This prevents the probe from validating a *different* entry point than
    the tool actually uses — regression caught in PR #6 review (Qodo Q4).
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.1"\n'
        "\n[project.scripts]\n"
        'other = "other.cli:main"\n'
        'demo = "not-a-valid-entry-shape"\n'
    )
    assert structure._resolve_entry_target(_ctx(tmp_path)) is None


def test_resolve_entry_target_falls_back_when_tool_name_absent(
    tmp_path: Path,
) -> None:
    """When ctx.tool_name is not in scripts at all, the first script is used."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.1"\n'
        "\n[project.scripts]\n"
        'other = "other.cli:main"\n'
    )
    # ctx.tool_name="demo" is not in scripts → falls back to "other" entry.
    assert structure._resolve_entry_target(_ctx(tmp_path)) == ("other.cli", "main")


def test_main_entry_contract_warns_when_probe_cannot_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pyproject(tmp_path)

    def raise_not_found(*_a, **_kw):
        raise FileNotFoundError("uv")

    monkeypatch.setattr(structure.subprocess, "run", raise_not_found)
    result = structure._check_main_entry_contract(_ctx(tmp_path))
    assert not result.passed
    assert result.severity == "warn"
    assert "probe" in result.evidence.lower() or "uv" in result.remediation.lower()


def test_main_entry_contract_warns_on_probe_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pyproject(tmp_path)

    def raise_timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="uv", timeout=1)

    monkeypatch.setattr(structure.subprocess, "run", raise_timeout)
    result = structure._check_main_entry_contract(_ctx(tmp_path))
    assert not result.passed
    assert result.severity == "warn"
