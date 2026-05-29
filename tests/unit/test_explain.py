"""Tests for :mod:`agentfront.explain` and the ``agentfront explain`` command."""

from __future__ import annotations

import json

import pytest

from agentfront.cli import main
from agentfront.cli._errors import AfiError
from agentfront.explain import known_paths, resolve


def test_resolve_root_path_returns_markdown() -> None:
    text = resolve(())
    assert text.startswith("# agentfront")


def test_resolve_teken_alias_matches_root() -> None:
    assert resolve(("agentfront",)) == resolve(())


def test_resolve_legacy_afi_alias_matches_root() -> None:
    # Back-compat: the renamed command keeps `teken` as an explain alias.
    assert resolve(("teken",)) == resolve(())


def test_resolve_known_verbs() -> None:
    for path in [("learn",), ("explain",)]:
        assert resolve(path).startswith("#")


def test_resolve_unknown_path_raises_afi_error() -> None:
    with pytest.raises(AfiError) as exc:
        resolve(("nope",))
    assert exc.value.code == 1
    assert "no explain entry" in exc.value.message
    assert "agentfront explain agentfront" in exc.value.remediation


def test_known_paths_covers_core_entries() -> None:
    paths = set(known_paths())
    assert () in paths
    assert ("agentfront",) in paths
    assert ("teken",) in paths  # legacy alias retained
    assert ("learn",) in paths
    assert ("explain",) in paths


def test_cli_explain_root_prints_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain", "agentfront"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("# agentfront")


def test_cli_explain_legacy_afi_alias_prints_root(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain", "teken"])
    assert rc == 0
    assert capsys.readouterr().out.startswith("# agentfront")


def test_cli_explain_learn_prints_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain", "learn"])
    assert rc == 0
    assert "# agentfront learn" in capsys.readouterr().out


def test_cli_explain_json_shape(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain", "learn", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == ["learn"]
    assert payload["markdown"].startswith("# agentfront learn")


def test_cli_explain_unknown_path_exits_nonzero_with_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["explain", "nope"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "error:" in err
    assert "hint:" in err


def test_cli_explain_empty_path_resolves_to_root(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["explain"])
    assert rc == 0
    assert capsys.readouterr().out.startswith("# agentfront")
