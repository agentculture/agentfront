"""Tests for rubric bundle 5: explain."""

from __future__ import annotations

from pathlib import Path

from agentfront.rubric._types import RunOutput, VerifyContext
from agentfront.rubric.checks import explain_cmd
from agentfront.rubric.checks.explain_cmd import BOGUS_PATH
from tests.unit._fake_runner import FakeRunner


def _ctx(tmp_path: Path, runner: FakeRunner) -> VerifyContext:
    return VerifyContext(tmp_path, "demo", runner)


def test_pass_on_good_explain(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("explain",): RunOutput(0, "# demo\n\nroot docs", ""),
            ("explain", "demo"): RunOutput(0, "# demo\n\nself docs", ""),
            ("explain", BOGUS_PATH): RunOutput(1, "", "error: no entry\nhint: explain demo"),
        }
    )
    results = explain_cmd.run(_ctx(tmp_path, runner))
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_fail_when_explain_missing(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("explain",): RunOutput(2, "", "invalid choice"),
            ("explain", "demo"): RunOutput(2, "", ""),
            ("explain", BOGUS_PATH): RunOutput(2, "", ""),
        }
    )
    results = explain_cmd.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["explain_exists"].passed


def test_fail_when_bogus_path_succeeds(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("explain",): RunOutput(0, "# demo", ""),
            ("explain", "demo"): RunOutput(0, "# demo", ""),
            ("explain", BOGUS_PATH): RunOutput(0, "# fake", ""),  # should've failed
        }
    )
    results = explain_cmd.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["explain_bogus_fails"].passed


def test_fail_when_bogus_path_fails_without_hint(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("explain",): RunOutput(0, "# demo", ""),
            ("explain", "demo"): RunOutput(0, "# demo", ""),
            ("explain", BOGUS_PATH): RunOutput(1, "", "error: nope"),  # no hint:
        }
    )
    results = explain_cmd.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["explain_bogus_fails"].passed
