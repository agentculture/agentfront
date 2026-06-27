"""Unit tests for agentfront.taui.snapshot — write/read quad + faithful."""

from __future__ import annotations

import pytest

from agentfront.taui.events import (
    SkillSuggested,
    Tick,
    UserInput,
    WorkStep,
    dumps_events,
)
from agentfront.taui.mirror import serialize
from agentfront.taui.reducer import replay
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.render.markdown import render_markdown
from agentfront.taui.snapshot import (
    _SUFFIX_ANSI,
    _SUFFIX_EVENTS,
    _SUFFIX_JSON,
    _SUFFIX_MD,
    Snapshot,
    faithful,
    read_snapshot,
    snapshot_paths,
    write_snapshot,
)
from agentfront.taui.state import (
    ConversationLine,
    Header,
    Panel,
    PanelItem,
    Status,
    TAUIState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state() -> TAUIState:
    """A state with a visible panel, two items, and a conversation line."""
    return TAUIState(
        header=Header(title="SnapTest"),
        panels=[
            Panel(
                id="panel.main",
                title="Main",
                visible=True,
                items=[
                    PanelItem(id="main.alpha", label="Alpha", status="available"),
                    PanelItem(id="main.beta", label="Beta", status="available"),
                ],
            ),
        ],
        conversation=[ConversationLine(text="hello")],
        status=Status(severity="info", message="Ready"),
    )


def _mixed_events() -> list:
    """Events spanning multiple types: UserInput, Tick, WorkStep, SkillSuggested."""
    return [
        UserInput(text="step one"),
        Tick(delta=2),
        WorkStep(label="doing work", ok=True),
        SkillSuggested(skill="deep-research", reason="complex query"),
        UserInput(text="step one"),  # consecutive duplicate → collapsed in reducer
    ]


# ---------------------------------------------------------------------------
# snapshot_paths — suffix correctness
# ---------------------------------------------------------------------------


class TestSnapshotPaths:
    """snapshot_paths returns the four expected paths with correct suffixes."""

    def test_suffix_json(self, tmp_path) -> None:
        paths = snapshot_paths(str(tmp_path / "snap"))
        assert str(paths["json"]).endswith(_SUFFIX_JSON)

    def test_suffix_ansi(self, tmp_path) -> None:
        paths = snapshot_paths(str(tmp_path / "snap"))
        assert str(paths["ansi"]).endswith(_SUFFIX_ANSI)

    def test_suffix_events(self, tmp_path) -> None:
        paths = snapshot_paths(str(tmp_path / "snap"))
        assert str(paths["events"]).endswith(_SUFFIX_EVENTS)

    def test_suffix_md(self, tmp_path) -> None:
        paths = snapshot_paths(str(tmp_path / "snap"))
        assert str(paths["md"]).endswith(_SUFFIX_MD)

    def test_stem_is_prefix(self, tmp_path) -> None:
        """Each returned path starts with the stem string."""
        stem = str(tmp_path / "mysnap")
        paths = snapshot_paths(stem)
        for key, path in paths.items():
            assert str(path).startswith(stem), f"key {key!r}: path does not start with stem"

    def test_four_distinct_paths(self, tmp_path) -> None:
        """All four paths are distinct."""
        paths = snapshot_paths(str(tmp_path / "snap"))
        assert len(set(str(p) for p in paths.values())) == 4

    def test_path_object_stem(self, tmp_path) -> None:
        """snapshot_paths accepts a Path object as stem."""
        stem = tmp_path / "mysnap"
        paths = snapshot_paths(stem)
        # .taui.json → last suffix is .json
        assert paths["json"].name.endswith(_SUFFIX_JSON)
        assert paths["md"].name.endswith(_SUFFIX_MD)


# ---------------------------------------------------------------------------
# write_snapshot — file creation and content
# ---------------------------------------------------------------------------


class TestWriteSnapshot:
    """write_snapshot creates all four files with the correct contents."""

    def test_creates_all_four_files(self, tmp_path) -> None:
        state = _base_state()
        paths = write_snapshot(str(tmp_path / "snap"), state)
        for key in ("json", "ansi", "events", "md"):
            assert paths[key].exists(), f"Missing file for key {key!r}"

    def test_json_content_matches_serialize(self, tmp_path) -> None:
        import json as _json

        state = _base_state()
        paths = write_snapshot(str(tmp_path / "snap"), state)
        written = _json.loads(paths["json"].read_text(encoding="utf-8"))
        assert written == serialize(state)

    def test_ansi_content_matches_render(self, tmp_path) -> None:
        state = _base_state()
        paths = write_snapshot(str(tmp_path / "snap"), state)
        assert paths["ansi"].read_text(encoding="utf-8") == render_ansi(state)

    def test_md_content_matches_render(self, tmp_path) -> None:
        state = _base_state()
        paths = write_snapshot(str(tmp_path / "snap"), state)
        assert paths["md"].read_text(encoding="utf-8") == render_markdown(state)

    def test_events_content_matches_dumps(self, tmp_path) -> None:
        state = _base_state()
        events = _mixed_events()
        paths = write_snapshot(str(tmp_path / "snap"), state, events)
        assert paths["events"].read_text(encoding="utf-8") == dumps_events(events)

    def test_events_none_writes_empty_file(self, tmp_path) -> None:
        """events=None writes an empty .events.jsonl file (dumps_events([]) == '')."""
        state = _base_state()
        paths = write_snapshot(str(tmp_path / "snap"), state, events=None)
        assert paths["events"].read_text(encoding="utf-8") == ""

    def test_creates_parent_dirs(self, tmp_path) -> None:
        """write_snapshot creates deeply nested parent directories as needed."""
        stem = str(tmp_path / "deep" / "nested" / "snap")
        paths = write_snapshot(stem, _base_state())
        for key in ("json", "ansi", "events", "md"):
            assert paths[key].exists(), f"Missing file for key {key!r}"

    def test_returns_path_dict(self, tmp_path) -> None:
        """Return value is a dict with exactly the four expected keys."""
        paths = write_snapshot(str(tmp_path / "snap"), _base_state())
        assert set(paths.keys()) == {"json", "ansi", "events", "md"}


# ---------------------------------------------------------------------------
# round-trip: write then read
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """read_snapshot(write_snapshot(...)) reconstructs the full Snapshot faithfully."""

    def test_state_round_trips(self, tmp_path) -> None:
        state = _base_state()
        stem = str(tmp_path / "snap")
        write_snapshot(stem, state)
        assert read_snapshot(stem).state == state

    def test_ansi_round_trips(self, tmp_path) -> None:
        state = _base_state()
        stem = str(tmp_path / "snap")
        write_snapshot(stem, state)
        assert read_snapshot(stem).ansi == render_ansi(state)

    def test_markdown_round_trips(self, tmp_path) -> None:
        state = _base_state()
        stem = str(tmp_path / "snap")
        write_snapshot(stem, state)
        assert read_snapshot(stem).markdown == render_markdown(state)

    def test_events_round_trip_mixed_types(self, tmp_path) -> None:
        """Events round-trip through JSONL: UserInput, Tick, WorkStep, SkillSuggested."""
        state = _base_state()
        events = _mixed_events()
        stem = str(tmp_path / "snap")
        write_snapshot(stem, state, events)
        assert read_snapshot(stem).events == events

    def test_events_none_reads_back_as_empty_list(self, tmp_path) -> None:
        """events=None on write → snap.events == [] on read."""
        stem = str(tmp_path / "snap")
        write_snapshot(stem, _base_state(), events=None)
        assert read_snapshot(stem).events == []

    def test_returns_snapshot_instance(self, tmp_path) -> None:
        stem = str(tmp_path / "snap")
        write_snapshot(stem, _base_state())
        snap = read_snapshot(stem)
        assert isinstance(snap, Snapshot)

    def test_snapshot_is_frozen(self, tmp_path) -> None:
        """Snapshot is a frozen dataclass — attribute assignment raises AttributeError."""
        stem = str(tmp_path / "snap")
        write_snapshot(stem, _base_state())
        snap = read_snapshot(stem)
        with pytest.raises(AttributeError):
            snap.ansi = "mutated"  # type: ignore[misc]

    def test_extra_mirror_keys_ignored_on_read(self, tmp_path) -> None:
        """taui_version and available_actions in .taui.json are silently ignored."""
        state = _base_state()
        stem = str(tmp_path / "snap")
        paths = write_snapshot(stem, state)
        # The json file already contains taui_version / available_actions from
        # serialize(); read_snapshot should reconstruct the same state.
        import json as _json

        raw = _json.loads(paths["json"].read_text(encoding="utf-8"))
        assert "taui_version" in raw  # confirm they're in the file
        assert "available_actions" in raw
        snap = read_snapshot(stem)
        assert snap.state == state  # from_dict silently ignores them


# ---------------------------------------------------------------------------
# replay-from-trail faithfulness
# ---------------------------------------------------------------------------


class TestReplayFromTrail:
    """The event trail written into a snapshot folds back to the snapshotted state."""

    def test_replay_from_trail_matches_snapshot_state(self, tmp_path) -> None:
        """replay(snap.events, initial) == final — the stored trail is faithful."""
        initial = TAUIState(
            header=Header(title="ReplayTest"),
            status=Status(severity="info", message="start"),
        )
        events = [
            UserInput(text="first input"),
            Tick(delta=3),
            WorkStep(label="run step", ok=True),
            UserInput(text="second input"),
        ]
        final = replay(events, initial)

        stem = str(tmp_path / "replay_snap")
        write_snapshot(stem, final, events)
        snap = read_snapshot(stem)

        # Event trail stored in the snapshot must fold back to the same state.
        assert replay(snap.events, initial) == final

    def test_replay_with_skill_suggested(self, tmp_path) -> None:
        """SkillSuggested events survive the round-trip and replay correctly."""
        initial = TAUIState()
        events = [
            SkillSuggested(skill="think", reason="complex problem"),
            Tick(delta=1),
        ]
        final = replay(events, initial)

        stem = str(tmp_path / "skill_snap")
        write_snapshot(stem, final, events)
        snap = read_snapshot(stem)
        assert replay(snap.events, initial) == final

    def test_replay_re_export(self) -> None:
        """replay is re-exported from agentfront.taui.snapshot unchanged."""
        from agentfront.taui.snapshot import replay as snap_replay

        assert snap_replay is replay


# ---------------------------------------------------------------------------
# faithful() — faithfulness checks
# ---------------------------------------------------------------------------


class TestFaithful:
    """faithful(mirror, markdown) detects label/text mismatches."""

    def test_faithful_returns_empty_for_consistent_state(self) -> None:
        """faithful(serialize(state), render_markdown(state)) == [] for valid state."""
        state = _base_state()
        assert faithful(serialize(state), render_markdown(state)) == []

    def test_faithful_detects_missing_panel_label(self) -> None:
        """Removing a panel item label from markdown is detected as a discrepancy."""
        state = _base_state()
        mirror = serialize(state)
        markdown = render_markdown(state).replace("Alpha", "XXXXX")
        discrepancies = faithful(mirror, markdown)
        assert len(discrepancies) > 0
        assert any("Alpha" in d for d in discrepancies)

    def test_faithful_detects_missing_conversation_text(self) -> None:
        """Removing a conversation text from markdown is detected as a discrepancy."""
        state = _base_state()
        mirror = serialize(state)
        markdown = render_markdown(state).replace("hello", "XXXXX")
        discrepancies = faithful(mirror, markdown)
        assert len(discrepancies) > 0
        assert any("hello" in d for d in discrepancies)

    def test_faithful_empty_state_is_vacuously_faithful(self) -> None:
        """A bare TAUIState (no panels, no conversation) passes faithfully."""
        state = TAUIState()
        assert faithful(serialize(state), render_markdown(state)) == []

    def test_faithful_hidden_panel_not_checked(self) -> None:
        """Hidden panel item labels are not required to appear in markdown."""
        state = TAUIState(
            panels=[
                Panel(
                    id="panel.hidden",
                    title="Hidden",
                    visible=False,
                    items=[PanelItem(id="h.x", label="SecretLabel")],
                ),
            ],
        )
        mirror = serialize(state)
        markdown = render_markdown(state)
        # Markdown must not contain the hidden label.
        assert "SecretLabel" not in markdown
        # faithful must not flag it either.
        assert faithful(mirror, markdown) == []

    def test_faithful_multiple_labels_all_must_appear(self) -> None:
        """All visible panel item labels must appear; missing one triggers discrepancy."""
        state = _base_state()
        mirror = serialize(state)
        # Remove "Beta" from the markdown to cause one discrepancy.
        markdown = render_markdown(state).replace("Beta", "XXXXX")
        discrepancies = faithful(mirror, markdown)
        assert any("Beta" in d for d in discrepancies)
        # "Alpha" and "hello" should still be in the truncated markdown.
        assert not any("Alpha" in d for d in discrepancies)
        assert not any("hello" in d for d in discrepancies)

    def test_faithful_both_panel_and_conversation_checked(self) -> None:
        """When both a label and a conversation text are missing, two discrepancies."""
        state = _base_state()
        mirror = serialize(state)
        # Drop both "Alpha" and "hello".
        markdown = render_markdown(state).replace("Alpha", "X1").replace("hello", "X2")
        discrepancies = faithful(mirror, markdown)
        assert any("Alpha" in d for d in discrepancies)
        assert any("hello" in d for d in discrepancies)


def test_faithful_detects_wrong_collapse_count():
    """faithful() must compare the RENDERED form ('text ×N'), so a markdown
    showing the wrong collapse count is flagged (matches the renderer + the
    diagnose_structured RENDER check). Issue #43 review SHOULD-FIX."""
    state = TAUIState(conversation=[ConversationLine(text="retry", count=3)])
    mirror = serialize(state)
    good_md = render_markdown(state)
    assert faithful(mirror, good_md) == []  # "retry ×3" is present

    bad_md = good_md.replace("retry ×3", "retry ×2")
    discrepancies = faithful(mirror, bad_md)
    assert discrepancies, "wrong collapse count should be flagged"
    assert any("retry ×3" in d for d in discrepancies)
