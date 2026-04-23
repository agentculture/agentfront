"""Unit tests for :mod:`afi.overview.cli_surface`.

The inspector is static-only — no subprocesses. Every test is a local file
fixture plus a direct call to :func:`afi.overview.cli_surface.inspect`.
"""

from __future__ import annotations

import json
from pathlib import Path

from afi.overview import to_json_dict, to_markdown
from afi.overview.cli_surface import inspect


def _write_minimal_cli_project(root: Path, *, with_triple: bool = True) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.1"\n'
        '\n[project.scripts]\ndemo = "demo.cli:main"\n'
    )
    pkg = root / "demo" / "cli" / "_commands"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "cli.py").write_text(
        "def register(sub):\n"
        '    p = sub.add_parser("cli")\n'
        "    s = p.add_subparsers()\n"
        '    s.add_parser("cite")\n'
        '    s.add_parser("verify")\n'
    )
    if with_triple:
        (pkg / "learn.py").write_text('def register(sub):\n    sub.add_parser("learn")\n')
        (pkg / "explain.py").write_text('def register(sub):\n    sub.add_parser("explain")\n')
        (pkg / "overview.py").write_text('def register(sub):\n    sub.add_parser("overview")\n')


def test_zero_target_describes_afi_template() -> None:
    report = inspect(None)
    assert report.subject == "cli"
    assert report.path is None
    # Must reference afi's bundled template.
    flat = to_markdown(report)
    assert "afi default template" in flat
    assert "{{slug}}" in flat
    # JSON is well-formed and stable-keyed.
    payload = to_json_dict(report)
    assert payload["subject"] == "cli"
    assert isinstance(payload["sections"], list)
    assert len(payload["sections"]) >= 1


def test_missing_path_falls_back_with_warning(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    report = inspect(missing)
    assert report.path == str(missing)
    assert any("does not exist" in w for w in report.warnings)
    # Still renders the default template in the sections.
    assert any(s.heading == "afi default template" for s in report.sections)


def test_target_mode_enumerates_command_surface(tmp_path: Path) -> None:
    _write_minimal_cli_project(tmp_path, with_triple=True)
    report = inspect(tmp_path)
    assert report.subject == "cli"
    assert report.path == str(tmp_path)
    headings = [s.heading for s in report.sections]
    assert "Project root" in headings
    assert "Command surface" in headings
    assert "Agent-first triple" in headings
    assert "Rubric posture" in headings
    # The command surface finds the noun and its verbs.
    surface = next(s for s in report.sections if s.heading == "Command surface")
    names = {f.get("command") for f in surface.findings}
    assert {"cli", "learn", "explain", "overview"}.issubset(names)
    # Triple is all-present.
    triple = next(s for s in report.sections if s.heading == "Agent-first triple")
    assert all(f["present"] for f in triple.findings)


def test_target_mode_flags_missing_triple(tmp_path: Path) -> None:
    _write_minimal_cli_project(tmp_path, with_triple=False)
    report = inspect(tmp_path)
    triple = next(s for s in report.sections if s.heading == "Agent-first triple")
    present = {f["verb"]: f["present"] for f in triple.findings}
    assert not present["learn"] and not present["explain"] and not present["overview"]


def test_malformed_pyproject_falls_back(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("this is :: not valid toml [[[[")
    report = inspect(tmp_path)
    # Fell back to zero-target because parsing failed.
    assert any(s.heading == "afi default template" for s in report.sections)
    assert report.warnings  # at least one warning emitted


def test_pyproject_without_scripts_falls_back(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.0.1"\n')
    report = inspect(tmp_path)
    assert any(s.heading == "afi default template" for s in report.sections)


def test_json_shape_is_stable(tmp_path: Path) -> None:
    _write_minimal_cli_project(tmp_path)
    report = inspect(tmp_path)
    payload = to_json_dict(report)
    # Stable top-level keys — culture's embed helper depends on these.
    assert set(payload.keys()) == {"subject", "path", "sections", "warnings", "notes"}
    # Sections carry stable per-item keys.
    for section in payload["sections"]:
        assert set(section.keys()) == {"heading", "body_md", "findings"}
    # JSON is round-trippable.
    assert json.loads(json.dumps(payload)) == payload
