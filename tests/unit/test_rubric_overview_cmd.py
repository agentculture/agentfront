"""Tests for rubric bundle 6: overview."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentfront.rubric._types import RunOutput, VerifyContext
from agentfront.rubric.checks import overview_cmd
from tests.unit._fake_runner import FakeRunner

# Fixed path used by the FakeRunner keys; `_fresh_missing_path` is monkey-patched
# per test so the check under test hands this exact string to the runner.
_FIXED_MISSING = "/BOGUS-FIXED-FOR-TESTS"

_GOOD_JSON = json.dumps(
    {
        "subject": "all",
        "path": None,
        "sections": [{"heading": "x", "body_md": "", "findings": []}],
        "warnings": [],
        "notes": [],
    }
)


@pytest.fixture(autouse=True)
def _pin_missing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``_fresh_missing_path`` so FakeRunner keys stay stable across tests.

    Production: the helper mints a random path per call (prevents /tmp
    pre-seeding); tests: we need a known value to key FakeRunner against.
    """
    monkeypatch.setattr(overview_cmd, "_fresh_missing_path", lambda: _FIXED_MISSING)


def _ctx(tmp_path: Path, runner: FakeRunner) -> VerifyContext:
    return VerifyContext(tmp_path, "demo", runner)


def test_pass_on_good_overview(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("overview",): RunOutput(0, "# overview\n...", ""),
            ("cli", "overview"): RunOutput(0, "# overview: cli\n...", ""),
            ("overview", "--json"): RunOutput(0, _GOOD_JSON, ""),
            ("overview", _FIXED_MISSING): RunOutput(0, "# fallback\n...", ""),
        }
    )
    results = overview_cmd.run(_ctx(tmp_path, runner))
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_fail_when_global_overview_missing(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("overview",): RunOutput(2, "", "invalid choice"),
            ("cli", "overview"): RunOutput(0, "ok", ""),
            ("overview", "--json"): RunOutput(2, "", ""),
            ("overview", _FIXED_MISSING): RunOutput(2, "", ""),
        }
    )
    by_name = {r.check: r for r in overview_cmd.run(_ctx(tmp_path, runner))}
    assert not by_name["overview_global_exists"].passed
    assert by_name["overview_global_exists"].severity == "error"


def test_fail_when_cli_noun_overview_missing(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("overview",): RunOutput(0, "ok", ""),
            ("cli", "overview"): RunOutput(2, "", "invalid choice: 'overview'"),
            ("overview", "--json"): RunOutput(0, _GOOD_JSON, ""),
            ("overview", _FIXED_MISSING): RunOutput(0, "ok", ""),
        }
    )
    by_name = {r.check: r for r in overview_cmd.run(_ctx(tmp_path, runner))}
    assert not by_name["overview_cli_noun_exists"].passed


def test_fail_when_json_not_parseable(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("overview",): RunOutput(0, "ok", ""),
            ("cli", "overview"): RunOutput(0, "ok", ""),
            ("overview", "--json"): RunOutput(0, "this is not json", ""),
            ("overview", _FIXED_MISSING): RunOutput(0, "ok", ""),
        }
    )
    by_name = {r.check: r for r in overview_cmd.run(_ctx(tmp_path, runner))}
    assert not by_name["overview_json_shape"].passed


def test_fail_when_json_missing_required_keys(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("overview",): RunOutput(0, "ok", ""),
            ("cli", "overview"): RunOutput(0, "ok", ""),
            ("overview", "--json"): RunOutput(0, json.dumps({"foo": "bar"}), ""),
            ("overview", _FIXED_MISSING): RunOutput(0, "ok", ""),
        }
    )
    by_name = {r.check: r for r in overview_cmd.run(_ctx(tmp_path, runner))}
    result = by_name["overview_json_shape"]
    assert not result.passed
    assert "subject" in result.evidence or "sections" in result.evidence


def test_fail_when_bogus_path_hard_fails(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("overview",): RunOutput(0, "ok", ""),
            ("cli", "overview"): RunOutput(0, "ok", ""),
            ("overview", "--json"): RunOutput(0, _GOOD_JSON, ""),
            # overview should fall back gracefully — this is a drift case.
            ("overview", _FIXED_MISSING): RunOutput(1, "", "error: no such path"),
        }
    )
    by_name = {r.check: r for r in overview_cmd.run(_ctx(tmp_path, runner))}
    assert not by_name["overview_graceful_on_bad_path"].passed
    assert "verify" in by_name["overview_graceful_on_bad_path"].remediation


def test_fresh_missing_path_is_not_predictable() -> None:
    """Sanity check: the production helper returns different paths per call.

    Guards against regressing to a hardcoded /tmp/... constant.
    """
    # We have to call the *real* function here, not the monkey-patched one.
    import secrets
    import tempfile
    from pathlib import Path as _P

    def real() -> str:
        return str(
            _P(tempfile.gettempdir()) / f"agentfront-overview-missing-{secrets.token_hex(8)}"
        )

    a, b = real(), real()
    assert a != b
    assert "agentfront-overview-missing-" in a
