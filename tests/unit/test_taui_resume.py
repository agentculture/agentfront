"""Unit tests for ``agentfront.taui.snapshot.resume`` — the handoff primitive (t10).

``resume`` reconstructs a live :class:`~agentfront.taui.session.Session` from
a serialized snapshot (a stem on disk, via ``read_snapshot``) or an
in-memory :class:`~agentfront.taui.snapshot.Snapshot`, so an agent that
paused with ``write_snapshot`` can hand off to a human (or another agent)
who resumes with ``resume`` and keeps folding events on the SAME trail —
nothing lost. This is the honesty condition of the handoff: continuing a
resumed session must be indistinguishable, state-wise, from never having
paused at all.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentfront import App
from agentfront.taui.derive import make_baseline
from agentfront.taui.events import SelectorAction
from agentfront.taui.reducer import replay
from agentfront.taui.session import Session
from agentfront.taui.snapshot import Snapshot, read_snapshot, resume, write_snapshot

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> App:
    """An app with one deterministic tool (no randomness/time) for exact
    state-equality assertions across a real session and its resumed twin."""
    a = App(name="resume-test-app", version="0.1.0")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    return a


@pytest.fixture
def handoff(app: App, tmp_path) -> SimpleNamespace:
    """Perform one full handoff round-trip and return every artifact needed
    to assert on it: the never-paused session A, the snapshot written at the
    midpoint, and a resumed session that folds the SAME post-midpoint events.

    Sequence:
      pre-k:  feed_key("down"); dispatch(add, real tool dispatch); feed_key("up")
      --- write_snapshot at k ---
      post-k (applied to BOTH session_a and resumed, identically):
              feed_key("down"); dispatch(add, deterministic, no side effects)
    """
    stem = str(tmp_path / "handoff")

    session_a = Session(app)
    session_a.feed_key("down")
    session_a.dispatch(SelectorAction(selector="add", args={"x": 2, "y": 3}))
    session_a.feed_key("up")

    state_at_k = session_a.state
    events_up_to_k = session_a.events  # a copy, per Session.events contract

    write_snapshot(stem, state_at_k, events_up_to_k)

    def apply_post_k(session: Session) -> None:
        session.feed_key("down")
        session.dispatch(SelectorAction(selector="add", args={"x": 10, "y": 20}))

    apply_post_k(session_a)
    final_state_a = session_a.state
    full_events_a = session_a.events

    resumed = resume(stem, app)
    apply_post_k(resumed)

    return SimpleNamespace(
        app=app,
        stem=stem,
        state_at_k=state_at_k,
        events_up_to_k=events_up_to_k,
        session_a=session_a,
        final_state_a=final_state_a,
        full_events_a=full_events_a,
        resumed=resumed,
    )


# ---------------------------------------------------------------------------
# resume(stem, app) — basic reconstruction
# ---------------------------------------------------------------------------


class TestResumeFromStem:
    def test_returns_a_session_instance(self, handoff: SimpleNamespace) -> None:
        # resumed was already built + continued by the fixture; re-derive a
        # freshly-resumed (not yet continued) session for this isolated check.
        fresh_resume = resume(handoff.stem, handoff.app)
        assert isinstance(fresh_resume, Session)

    def test_initial_equals_snapshotted_state(self, handoff: SimpleNamespace) -> None:
        fresh_resume = resume(handoff.stem, handoff.app)
        assert fresh_resume.initial == handoff.state_at_k

    def test_state_equals_snapshotted_state_before_any_new_folds(
        self, handoff: SimpleNamespace
    ) -> None:
        fresh_resume = resume(handoff.stem, handoff.app)
        assert fresh_resume.state == handoff.state_at_k

    def test_events_equal_the_snapshotted_trail(self, handoff: SimpleNamespace) -> None:
        fresh_resume = resume(handoff.stem, handoff.app)
        assert fresh_resume.events == handoff.events_up_to_k

    def test_replay_base_index_equals_length_of_snapshotted_trail(
        self, handoff: SimpleNamespace
    ) -> None:
        fresh_resume = resume(handoff.stem, handoff.app)
        assert fresh_resume.replay_base_index == len(handoff.events_up_to_k)


# ---------------------------------------------------------------------------
# Criterion 1 — round-trip handoff: resumed continuation matches the
# never-paused session's final state exactly (dataclass equality).
# ---------------------------------------------------------------------------


def test_round_trip_handoff_matches_never_paused_final_state(handoff: SimpleNamespace) -> None:
    assert handoff.resumed.state == handoff.final_state_a


def test_round_trip_handoff_resumed_events_match_full_trail(handoff: SimpleNamespace) -> None:
    """The resumed session's full trail (prior + newly folded) equals
    session A's own full trail — same events, same order."""
    assert handoff.resumed.events == handoff.full_events_a


# ---------------------------------------------------------------------------
# Criterion 2 — replay equivalence on the RESUMED session after the extra
# folds: replay(new events only, initial=resumed.initial) == resumed.state.
# ---------------------------------------------------------------------------


def test_replay_equivalence_on_resumed_session_after_continuation(
    handoff: SimpleNamespace,
) -> None:
    resumed = handoff.resumed
    new_events = resumed.events[resumed.replay_base_index :]
    assert replay(new_events, initial=resumed.initial) == resumed.state


def test_replay_base_index_unchanged_by_continuation(handoff: SimpleNamespace) -> None:
    """replay_base_index is fixed at construction time; folding more events
    after resume does not move it."""
    assert handoff.resumed.replay_base_index == len(handoff.events_up_to_k)


# ---------------------------------------------------------------------------
# Criterion 3 — resume from an in-memory Snapshot object (no files at all).
# ---------------------------------------------------------------------------


def test_resume_from_in_memory_snapshot_object_no_files(app: App, tmp_path) -> None:
    session_a = Session(app)
    session_a.feed_key("down")
    session_a.dispatch(SelectorAction(selector="add", args={"x": 5, "y": 7}))
    state_at_k = session_a.state
    events_up_to_k = session_a.events

    in_memory_snap = Snapshot(state=state_at_k, ansi="", markdown="", events=events_up_to_k)

    # No write_snapshot call anywhere in this test — nothing touches disk.
    resumed = resume(in_memory_snap, app)

    assert isinstance(resumed, Session)
    assert resumed.initial == state_at_k
    assert resumed.state == state_at_k
    assert resumed.events == events_up_to_k
    assert resumed.replay_base_index == len(events_up_to_k)


def test_resume_from_in_memory_snapshot_behaves_identically_to_stem(app: App, tmp_path) -> None:
    """The same Snapshot content resumed via a Snapshot object or via its
    written stem produce sessions with the same initial/state/events."""
    session_a = Session(app)
    session_a.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 1}))
    state_at_k = session_a.state
    events_up_to_k = session_a.events

    stem = str(tmp_path / "identical")
    write_snapshot(stem, state_at_k, events_up_to_k)

    resumed_from_stem = resume(stem, app)
    snap = read_snapshot(stem)
    resumed_from_snapshot = resume(snap, app)

    assert resumed_from_stem.initial == resumed_from_snapshot.initial
    assert resumed_from_stem.state == resumed_from_snapshot.state
    assert resumed_from_stem.events == resumed_from_snapshot.events
    assert resumed_from_stem.replay_base_index == resumed_from_snapshot.replay_base_index


# ---------------------------------------------------------------------------
# Criterion 4 — resume(stem) with an empty events file.
# ---------------------------------------------------------------------------


def test_resume_from_stem_with_empty_events_file(app: App, tmp_path) -> None:
    stem = str(tmp_path / "empty_events")
    state = make_baseline(app)
    write_snapshot(stem, state, events=None)

    resumed = resume(stem, app)

    assert resumed.events == []
    assert resumed.replay_base_index == 0
    assert resumed.initial == state
    assert resumed.state == state


def test_resume_from_stem_with_empty_events_file_continues_normally(app: App, tmp_path) -> None:
    """A resumed-from-empty-trail session folds new events like any fresh one."""
    stem = str(tmp_path / "empty_events_continue")
    state = make_baseline(app)
    write_snapshot(stem, state, events=None)

    resumed = resume(stem, app)
    resumed.feed_key("down")
    resumed.dispatch(SelectorAction(selector="add", args={"x": 9, "y": 1}))

    assert resumed.replay_base_index == 0
    assert replay(resumed.events, initial=resumed.initial) == resumed.state


# ---------------------------------------------------------------------------
# Criterion 5 — full-trail truth: the unbroken-vs-handoff equivalence. This
# is THE honesty condition of the handoff primitive.
# ---------------------------------------------------------------------------


def test_full_trail_truth_unbroken_session_replays_to_final_state(
    handoff: SimpleNamespace,
) -> None:
    baseline = make_baseline(handoff.app)
    assert replay(handoff.full_events_a, initial=baseline) == handoff.final_state_a


def test_full_trail_truth_resumed_session_replays_to_final_state(
    handoff: SimpleNamespace,
) -> None:
    """The SAME full trail, replayed from the true baseline, reconstructs the
    resumed session's state too — proving the handoff lost nothing: an
    outside observer who only ever sees the merged event trail cannot tell a
    session was ever paused and resumed."""
    baseline = make_baseline(handoff.app)
    assert replay(handoff.resumed.events, initial=baseline) == handoff.resumed.state
    assert replay(handoff.resumed.events, initial=baseline) == handoff.final_state_a


def test_full_trail_truth_unbroken_and_handoff_states_are_equal(
    handoff: SimpleNamespace,
) -> None:
    """The never-paused session and the paused-then-resumed session converge
    on an identical final TAUIState (dataclass equality) — the handoff is
    fully honest."""
    assert handoff.final_state_a == handoff.resumed.state


# ---------------------------------------------------------------------------
# Docstring — resume documents itself as the handoff primitive.
# ---------------------------------------------------------------------------


def test_resume_docstring_names_it_as_the_handoff_primitive() -> None:
    doc = resume.__doc__ or ""
    assert "handoff" in doc.lower() or "hand off" in doc.lower()
