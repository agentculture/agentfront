"""Tests for rubric bundle 2: learnability."""

from __future__ import annotations

from pathlib import Path

from agentfront.rubric._types import RunOutput, VerifyContext
from agentfront.rubric.checks import learnability
from tests.unit._fake_runner import FakeRunner

GOOD_LEARN = (
    "Purpose: demo tool.\n"
    "Commands: learn, explain, do-thing.\n"
    "Machine-readable output via --json.\n"
    "Exit codes: 0 success, 1 user error, 2 env error.\n"
    "Also see: explain <path>.\n"
    "Padded so this text clears the 200-char minimum defined by the learnability "
    "rubric bundle; stay verbose here."
)


def _ctx(tmp_path: Path, runner: FakeRunner) -> VerifyContext:
    return VerifyContext(tmp_path, "demo", runner)


def test_pass_on_good_learn(tmp_path: Path) -> None:
    runner = FakeRunner(responses={("learn",): RunOutput(0, GOOD_LEARN, "")})
    results = learnability.run(_ctx(tmp_path, runner))
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_fail_on_nonzero_exit(tmp_path: Path) -> None:
    runner = FakeRunner(responses={("learn",): RunOutput(1, GOOD_LEARN, "")})
    results = learnability.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["learn_exit_zero"].passed


def test_fail_on_short_output(tmp_path: Path) -> None:
    runner = FakeRunner(responses={("learn",): RunOutput(0, "hi", "")})
    results = learnability.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["learn_min_length"].passed


def test_fail_on_missing_markers(tmp_path: Path) -> None:
    # Long enough but missing the required markers.
    text = "hello " * 60
    runner = FakeRunner(responses={("learn",): RunOutput(0, text, "")})
    results = learnability.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["learn_markers"].passed
    assert "missing markers" in by_name["learn_markers"].evidence
