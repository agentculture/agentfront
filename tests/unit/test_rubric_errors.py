"""Tests for rubric bundle 4: error propagation."""

from __future__ import annotations

from pathlib import Path

from agentfront.rubric._types import RunOutput, VerifyContext
from agentfront.rubric.checks import errors as errors_bundle
from agentfront.rubric.checks.errors import BOGUS
from tests.unit._fake_runner import FakeRunner

GOOD_LEARN_WITH_EXIT_CODES = (
    "Purpose: demo. Commands: learn. JSON via --json. explain. "
    "Exit codes: 0, 1, 2 reserved. Documented policy. " * 3
)


def _ctx(tmp_path: Path, runner: FakeRunner) -> VerifyContext:
    return VerifyContext(tmp_path, "demo", runner)


def test_pass_on_good_error_discipline(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            (BOGUS,): RunOutput(1, "", "error: unknown verb\nhint: run demo --help"),
            ("learn",): RunOutput(0, GOOD_LEARN_WITH_EXIT_CODES, ""),
        }
    )
    results = errors_bundle.run(_ctx(tmp_path, runner))
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_fail_if_bogus_verb_exits_zero(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            (BOGUS,): RunOutput(0, "silently ok", ""),
            ("learn",): RunOutput(0, GOOD_LEARN_WITH_EXIT_CODES, ""),
        }
    )
    results = errors_bundle.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["bogus_verb_exits_nonzero"].passed


def test_fail_if_no_hint(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            (BOGUS,): RunOutput(1, "", "error: unknown"),
            ("learn",): RunOutput(0, GOOD_LEARN_WITH_EXIT_CODES, ""),
        }
    )
    results = errors_bundle.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["error_has_hint"].passed


def test_fail_on_traceback_leak(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            (BOGUS,): RunOutput(1, "", "Traceback (most recent call last):\n  ...\nhint: foo"),
            ("learn",): RunOutput(0, GOOD_LEARN_WITH_EXIT_CODES, ""),
        }
    )
    results = errors_bundle.run(_ctx(tmp_path, runner))
    by_name = {r.check: r for r in results}
    assert not by_name["no_traceback"].passed
