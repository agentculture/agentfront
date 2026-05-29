"""Tests for rubric bundle 3: json output."""

from __future__ import annotations

from pathlib import Path

from agentfront.rubric._types import RunOutput, VerifyContext
from agentfront.rubric.checks import json_output
from tests.unit._fake_runner import FakeRunner


def _ctx(tmp_path: Path, runner: FakeRunner) -> VerifyContext:
    return VerifyContext(tmp_path, "demo", runner)


def test_pass_on_valid_json(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("learn", "--json"): RunOutput(0, '{"ok": true}\n', ""),
            ("explain", "--json"): RunOutput(0, '{"path": [], "markdown": "..."}', ""),
        }
    )
    results = json_output.run(_ctx(tmp_path, runner))
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_fail_on_non_json_learn(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("learn", "--json"): RunOutput(0, "not json at all", ""),
            ("explain", "--json"): RunOutput(0, "{}", ""),
        }
    )
    results = json_output.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["learn_json_parseable"].passed


def test_warn_on_stderr_leak(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("learn", "--json"): RunOutput(0, "{}", "some diagnostic"),
            ("explain", "--json"): RunOutput(0, "{}", ""),
        }
    )
    results = json_output.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["stderr_clean_on_success"].passed
    assert by_name["stderr_clean_on_success"].severity == "warn"


def test_learn_json_check_id_is_stable_on_nonzero_exit(tmp_path: Path) -> None:
    """Non-zero exit reports under the same check id as JSON-parse failure."""
    runner = FakeRunner(
        responses={
            ("learn", "--json"): RunOutput(2, "", "nope"),
            ("explain", "--json"): RunOutput(0, "{}", ""),
        }
    )
    results = json_output.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert "learn_json_parseable" in by_name
    assert not by_name["learn_json_parseable"].passed
    assert "exited with 2" in by_name["learn_json_parseable"].evidence
    # The old split id must NOT appear.
    assert "learn_json_exit_zero" not in by_name


def test_explain_json_check_id_is_stable_on_nonzero_exit(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("learn", "--json"): RunOutput(0, "{}", ""),
            ("explain", "--json"): RunOutput(2, "", "no"),
        }
    )
    results = json_output.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert "explain_json_parseable" in by_name
    assert not by_name["explain_json_parseable"].passed
    assert "explain_json_exit_zero" not in by_name
